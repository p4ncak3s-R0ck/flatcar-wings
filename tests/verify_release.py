#!/usr/bin/env python3
"""Verify actual release assets and installer archive contents after packaging."""
import hashlib
from pathlib import Path
import subprocess
import tarfile

BASE = Path(__file__).resolve().parent.parent
out = BASE / 'release'
version = (BASE / 'VERSION').read_text().strip()
subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=out, check=True)
for arch in ('amd64', 'arm64'):
    raw = (out / f'wings-{arch}.raw').read_bytes()
    with tarfile.open(out / f'flatcar-wings-v{version}-{arch}.tar.gz') as archive:
        names = archive.getnames()
        assert all(name.startswith('flatcar-wings/') and '..' not in Path(name).parts for name in names)
        assert archive.extractfile(f'flatcar-wings/dist/{arch}/wings.raw').read() == raw
        checksums = archive.extractfile(f'flatcar-wings/dist/{arch}/SHA256SUMS').read().decode()
        assert checksums == hashlib.sha256(raw).hexdigest() + '  wings.raw\n'
        assert 'flatcar-wings/scripts/install.sh' in names
        assert 'flatcar-wings/LICENSE-WINGS' in names
        assert not any(name.endswith('/config.yml') for name in names)
    assert f'sha256-{hashlib.sha256(raw).hexdigest()}' in (out / f'flatcar-{arch}.bu').read_text()
print('Release checksums, tar paths, installer images, and provisioning hashes verified.')
