"""Exercise inputs that must fail before downloading or touching a host."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('examples', BASE / 'scripts/make-examples.py')
EXAMPLES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXAMPLES)


class GuardTests(unittest.TestCase):
    def test_bad_architecture_fails_before_download(self):
        result = subprocess.run(['bash', str(BASE / 'scripts/build.sh'), 'riscv64'], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'Usage:', result.stderr)

    def test_corrupt_cached_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(BASE / 'scripts', root / 'scripts')
            shutil.copytree(BASE / 'config', root / 'config')
            (root / 'upstream').mkdir()
            (root / 'upstream/wings_linux_amd64').write_bytes(b'corrupted binary')
            result = subprocess.run(['bash', str(root / 'scripts/build.sh'), 'amd64'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'FAILED', result.stdout + result.stderr)
            self.assertFalse((root / 'dist/amd64/wings.raw').exists())

    def test_release_tag_must_match_version(self):
        result = subprocess.run(['python3', str(BASE / 'scripts/package.py'),
                                 '--repository', 'owner/repo', '--tag', 'v999.0.0'], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'tag must match VERSION', result.stderr)

    def test_url_coordinates_cannot_inject_yaml_or_paths(self):
        for repository, tag in [('owner/repo\nfiles:', 'v0.1.0'), ('../repo', 'v0.1.0'),
                                ('owner/repo', '../latest'), ('owner/repo', 'v1.0.0\n')]:
            with self.subTest(repository=repository, tag=tag):
                with self.assertRaises(ValueError):
                    EXAMPLES.validate_coordinates(repository, tag)

    def test_installer_help_needs_no_root_or_flatcar(self):
        result = subprocess.run(['bash', str(BASE / 'scripts/install.sh'), '--help'], capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b'--config', result.stdout)

    def test_missing_configuration_argument(self):
        result = subprocess.run(['bash', str(BASE / 'scripts/install.sh'), '--config'], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'requires a file', result.stderr)


if __name__ == '__main__':
    unittest.main()
