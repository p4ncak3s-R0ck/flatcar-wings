#!/usr/bin/env python3
"""Check a built image independently of the staging tree."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arch', choices=('amd64', 'arm64'))
    args = parser.parse_args()
    arch = args.arch
    pins = dict(line.split('=', 1) for line in (BASE / 'config/wings.env').read_text().splitlines()
                if line and not line.startswith('#'))
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=BASE / 'dist' / arch, check=True)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / 'root'
        subprocess.run(['unsquashfs', '-no-progress', '-d', str(root),
                        str(BASE / 'dist' / arch / 'wings.raw')], check=True, stdout=subprocess.DEVNULL)
        binary = root / 'usr/bin/wings'
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == pins['WINGS_SHA256_' + arch.upper()]
        assert binary.stat().st_mode & 0o111
        expected_arch = {'amd64': 'x86-64', 'arm64': 'arm64'}[arch]
        release = (root / 'usr/lib/extension-release.d/extension-release.wings').read_text()
        assert release == f'ID=flatcar\nSYSEXT_LEVEL=1.0\nARCHITECTURE={expected_arch}\n'
        assert not (root / 'etc').exists(), 'Private configuration must stay outside the image'
        assert not list(root.rglob('config.yml'))
        assert 'INTERP' not in subprocess.check_output(['readelf', '-lW', str(binary)], text=True)
        for item in ('usr/lib/systemd/system/wings.service',
                     'usr/lib/sysusers.d/flatcar-wings.conf',
                     'usr/lib/systemd/system/multi-user.target.d/50-flatcar-wings.conf',
                     'usr/share/licenses/flatcar-wings/WINGS-LICENSE'):
            assert (root / item).is_file(), item
    print(f'{arch}: extension content, metadata, pinned binary, and static linkage verified')


if __name__ == '__main__':
    main()
