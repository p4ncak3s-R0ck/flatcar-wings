#!/usr/bin/env bash
# Build without root, Docker, loop devices, or a Flatcar build host.
set -euo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=config/wings.env
. "$base/config/wings.env"
arch=${1:-amd64}
case "$arch" in
 amd64) expected=$WINGS_SHA256_AMD64; elf_machine='Advanced Micro Devices X86-64'; sysext_arch=x86-64 ;;
 arm64) expected=$WINGS_SHA256_ARM64; elf_machine=AArch64; sysext_arch=arm64 ;;
 *) echo 'Usage: build.sh [amd64|arm64]' >&2; exit 2 ;;
esac
[[ $WINGS_VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid Wings version" >&2; exit 1; }
[[ $expected =~ ^[a-f0-9]{64}$ ]] || { echo "Invalid pinned digest" >&2; exit 1; }
for tool in mksquashfs readelf sha256sum; do command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }; done
mkdir -p "$base/upstream" "$base/dist/$arch"
binary="$base/upstream/wings_linux_$arch"
if [[ ! -f "$binary" ]]; then
 curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://github.com/pterodactyl/wings/releases/download/$WINGS_VERSION/wings_linux_$arch" -o "$binary.part"
 mv -- "$binary.part" "$binary"
fi
printf '%s  %s\n' "$expected" "$binary" | sha256sum --check
chmod 0755 "$binary"
# SYSEXT_LEVEL=1.0 requires a static binary, not host-linked libraries.
if readelf -lW "$binary" | grep 'INTERP' >/dev/null; then echo 'Refusing dynamically linked Wings binary' >&2; exit 1; fi
readelf -h "$binary" | grep -F "$elf_machine" >/dev/null
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
cp -a "$base/root/." "$work/"
install -D -m 0755 "$binary" "$work/usr/bin/wings"
mkdir -p "$work/usr/lib/extension-release.d"
cat > "$work/usr/lib/extension-release.d/extension-release.wings" <<META
ID=flatcar
SYSEXT_LEVEL=1.0
ARCHITECTURE=$sysext_arch
META
# Fixed timestamps and one compression thread produce repeatable images.
mksquashfs "$work" "$base/dist/$arch/wings.raw" -noappend -all-root \
 -comp xz -processors 1 -mkfs-time 0 -all-time 0 -no-progress
(cd "$base/dist/$arch" && sha256sum wings.raw > SHA256SUMS)
echo "Built dist/$arch/wings.raw (Wings $WINGS_VERSION)"
