#!/usr/bin/env python3
"""Package release images, per-architecture installers, provisioning and hashes."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tarfile

BASE = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True, help='GitHub OWNER/REPO')
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('examples', BASE / 'scripts/make-examples.py')
    examples = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(examples)
    examples.validate_coordinates(args.repository, args.tag)
    version = (BASE / 'VERSION').read_text().strip()
    if args.tag != 'v' + version:
        parser.error('tag must match VERSION')
    for arch in ('amd64', 'arm64'):
        subprocess.run(['sha256sum', '--check', 'SHA256SUMS'], cwd=BASE / 'dist' / arch, check=True)
    out = BASE / 'release'
    # Refuse to mix assets from different runs. Caller can remove this directory.
    out.mkdir(exist_ok=False)
    for arch in ('amd64', 'arm64'):
        image = BASE / 'dist' / arch / 'wings.raw'
        shutil.copyfile(image, out / f'wings-{arch}.raw')
        (out / f'flatcar-{arch}.bu').write_text(examples.render(arch, args.repository, args.tag))
        with tarfile.open(out / f'flatcar-wings-{args.tag}-{arch}.tar.gz', 'w:gz') as archive:
            items = ['README.md', 'LICENSE', 'LICENSE-WINGS', 'VERSION',
                     'scripts/install.sh', f'dist/{arch}/wings.raw', f'dist/{arch}/SHA256SUMS']
            for name in items:
                archive.add(BASE / name, arcname=f'flatcar-wings/{name}')
    # A standalone installer pins this exact release's architecture archives.
    template = (BASE / 'scripts/install-release.sh').read_text()
    replacements = {'@@REPOSITORY@@': args.repository, '@@TAG@@': args.tag}
    for arch in ('amd64', 'arm64'):
        archive = out / f'flatcar-wings-{args.tag}-{arch}.tar.gz'
        replacements['@@SHA256_' + arch.upper() + '@@'] = hashlib.sha256(archive.read_bytes()).hexdigest()
    for token, value in replacements.items():
        template = template.replace(token, value)
    installer = out / 'install.sh'
    installer.write_text(template)
    installer.chmod(0o755)
    assets = sorted(p for p in out.iterdir() if p.is_file())
    (out / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in assets))
    (out / 'RELEASE-NOTES.md').write_text(
        f'Flatcar Wings {args.tag}\n\n'
        'Download the standalone installer and run it on Flatcar:\n\n'
        f'```bash\ncurl -fL https://github.com/{args.repository}/releases/download/{args.tag}/install.sh -o install.sh\n'
        'sudo bash install.sh --config ./config.yml\n```\n\n'
        'The script selects AMD64 or ARM64, downloads this release’s installer archive, '
        'and verifies its pinned SHA-256 before installation. '
        'Use `bash install.sh --download-only ./downloads` to fetch without installing.\n\n'
        'Alternatively, extract the matching installer archive and run '
        '`sudo bash scripts/install.sh --config ./config.yml`.\n\n'
        'Use the Panel-generated node configuration. The standalone .raw images must '
        'be installed as /etc/extensions/wings.raw. The .bu files contain image hashes.\n\n'
        'Build checks do not replace testing on a disposable Flatcar node. '
        'See the README for support status and maintenance requirements.\n')
    print(out)


if __name__ == '__main__':
    main()
