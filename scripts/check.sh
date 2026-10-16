#!/usr/bin/env bash
set -euo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$base"
shellcheck -x scripts/*.sh
for script in scripts/*.sh; do bash -n "$script"; done
python3 -m unittest discover -s tests -v
shellcheck -x coreos/*.sh
for script in coreos/*.sh; do bash -n "$script"; done
python3 -m unittest discover -s coreos/tests -v
python3 coreos/ignition/build.py --check
for arch in amd64 arm64; do
 bash scripts/build.sh "$arch"
 python3 scripts/verify-image.py "$arch"
done
python3 scripts/make-examples.py
# Execute only the native architecture's binary.
case $(uname -m) in
 x86_64) ./upstream/wings_linux_amd64 version ;;
 aarch64) ./upstream/wings_linux_arm64 version ;;
esac
