"""Exercise the downloaded release installer using a local network fixture."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parent.parent


class ReleaseInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.fixture = self.root / 'fixture'
        self.fixture.mkdir()
        text = (BASE / 'scripts/install-release.sh').read_text()
        text = text.replace('@@REPOSITORY@@', 'example/project').replace('@@TAG@@', 'v1.2.3')
        for arch in ('amd64', 'arm64'):
            data = f'verified installer archive for {arch}'.encode()
            (self.fixture / f'flatcar-wings-v1.2.3-{arch}.tar.gz').write_bytes(data)
            text = text.replace('@@SHA256_' + arch.upper() + '@@', hashlib.sha256(data).hexdigest())
        self.script = self.root / 'install.sh'
        self.script.write_text(text)
        curl = self.bin / 'curl'
        curl.write_text('''#!/usr/bin/env python3
import os, pathlib, sys
args = sys.argv[1:]
url = next(arg for arg in args if arg.startswith('https://'))
pathlib.Path(os.environ['FIXTURE_LOG']).write_text(url)
source = pathlib.Path(os.environ['FIXTURE_ROOT']) / url.rsplit('/', 1)[-1]
pathlib.Path(args[args.index('-o') + 1]).write_bytes(source.read_bytes())
''')
        curl.chmod(0o755)
        uname = self.bin / 'uname'
        uname.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$FIXTURE_MACHINE"\n')
        uname.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        FIXTURE_ROOT=str(self.fixture), FIXTURE_MACHINE='x86_64',
                        FIXTURE_LOG=str(self.root / 'download-url'))

    def run_installer(self, *args):
        return subprocess.run(['bash', str(self.script), *map(str, args)],
                              env=self.env, capture_output=True, text=True)

    def test_both_architectures_fetch_the_pinned_release_without_installing(self):
        for machine, arch in (('x86_64', 'amd64'), ('aarch64', 'arm64')):
            with self.subTest(machine=machine):
                self.env['FIXTURE_MACHINE'] = machine
                dest = self.root / f'downloads {arch}'
                result = self.run_installer('--download-only', dest)
                self.assertEqual(result.returncode, 0, result.stderr)
                asset = f'flatcar-wings-v1.2.3-{arch}.tar.gz'
                self.assertEqual((dest / asset).read_bytes(), (self.fixture / asset).read_bytes())
                self.assertEqual((self.root / 'download-url').read_text(),
                                 f'https://github.com/example/project/releases/download/v1.2.3/{asset}')

    def test_corrupt_download_is_rejected_without_saving(self):
        (self.fixture / 'flatcar-wings-v1.2.3-amd64.tar.gz').write_bytes(b'corrupt')
        dest = self.root / 'downloads'
        result = self.run_installer('--download-only', dest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAILED', result.stdout + result.stderr)
        self.assertFalse(dest.exists())

    def test_existing_download_is_not_overwritten(self):
        dest = self.root / 'downloads'
        dest.mkdir()
        target = dest / 'flatcar-wings-v1.2.3-amd64.tar.gz'
        target.write_bytes(b'keep me')
        result = self.run_installer('--download-only', dest)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), b'keep me')

    def test_unsupported_architecture_never_downloads(self):
        self.env['FIXTURE_MACHINE'] = 'riscv64'
        result = self.run_installer('--download-only', self.root / 'downloads')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unsupported architecture', result.stderr)
        self.assertFalse((self.root / 'download-url').exists())

    def test_download_only_rejects_installation_flags(self):
        result = self.run_installer('--download-only', self.root / 'downloads', '--replace')
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / 'download-url').exists())

    def test_missing_config_is_rejected_before_network(self):
        result = self.run_installer('--config', self.root / 'missing.yml')
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / 'download-url').exists())


if __name__ == '__main__':
    unittest.main()
