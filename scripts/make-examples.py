#!/usr/bin/env python3
"""Render provisioning using actual image bytes and the chosen release URL."""
import argparse
import hashlib
from pathlib import Path
import re
from string import Template

BASE = Path(__file__).resolve().parent.parent


def validate_coordinates(repository, tag):
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or any(part in (".", "..") for part in repository.split("/"))):
        raise ValueError("repository must be OWNER/REPO")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("tag must be vMAJOR.MINOR.PATCH")


def render(arch, repository, tag):
    validate_coordinates(repository, tag)
    digest = hashlib.sha256((BASE / 'dist' / arch / 'wings.raw').read_bytes()).hexdigest()
    template = Template((BASE / 'examples' / 'flatcar.bu.in').read_text())
    return template.substitute(
        IMAGE_URL=f'https://github.com/{repository}/releases/download/{tag}/wings-{arch}.raw',
        IMAGE_SHA256=digest,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default='OWNER/flatcar-wings')
    parser.add_argument('--tag', default='v' + (BASE / 'VERSION').read_text().strip())
    parser.add_argument('--output-dir', type=Path, default=BASE / 'dist' / 'examples')
    args = parser.parse_args()
    validate_coordinates(args.repository, args.tag)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for arch in ('amd64', 'arm64'):
        (args.output_dir / f'flatcar-{arch}.bu').write_text(render(arch, args.repository, args.tag))


if __name__ == '__main__':
    main()
