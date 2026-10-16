#!/usr/bin/env bash
# Release packager stamps these values; each script installs its own release.
set -euo pipefail
repository='@@REPOSITORY@@'
tag='@@TAG@@'
sha_amd64='@@SHA256_AMD64@@'
sha_arm64='@@SHA256_ARM64@@'
download_dir=''
forward=()
usage() {
 cat <<'HELP'
Usage: sudo bash install.sh [--config FILE] [--replace] [--no-start]
       bash install.sh --download-only DIRECTORY

Downloads and verifies the matching AMD64/ARM64 installer for this release.
Normal installation requires Flatcar and root. --download-only needs neither
and saves the verified archive without extracting it or changing the host.
HELP
}
while (($#)); do
 case "$1" in
  --config)
   [[ $# -ge 2 && -s "$2" && -r "$2" ]] || { echo '--config requires a readable, nonempty file' >&2; exit 2; }
   forward+=(--config "$2"); shift 2 ;;
  --replace|--no-start) forward+=("$1"); shift ;;
  --download-only)
   [[ $# -ge 2 && -n "$2" ]] || { echo '--download-only requires a directory' >&2; exit 2; }
   download_dir=$2; shift 2 ;;
  -h|--help) usage; exit 0 ;;
  *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
 esac
done
if [[ -n "$download_dir" && ${#forward[@]} -ne 0 ]]; then
 echo '--download-only cannot be combined with installation options' >&2; exit 2
fi
[[ $tag =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Use the install.sh attached to a release, not the source template.' >&2; exit 1; }
case $(uname -m) in
 x86_64) arch=amd64; expected=$sha_amd64 ;;
 aarch64) arch=arm64; expected=$sha_arm64 ;;
 *) echo 'Unsupported architecture; expected x86_64 or aarch64.' >&2; exit 1 ;;
esac
[[ $expected =~ ^[a-f0-9]{64}$ ]] || { echo 'Missing pinned release checksum.' >&2; exit 1; }
if [[ -z "$download_dir" ]]; then
 [[ $EUID -eq 0 ]] || { echo 'Run with sudo, or use --download-only.' >&2; exit 1; }
 # shellcheck disable=SC1091
 . /etc/os-release
 [[ ${ID:-} == flatcar ]] || { echo 'Installation requires Flatcar; use --download-only to fetch elsewhere.' >&2; exit 1; }
fi
for tool in curl sha256sum tar; do
 command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
umask 077
work=$(mktemp -d -t flatcar-wings.XXXXXXXX)
trap 'rm -r -- "$work"' EXIT
asset="flatcar-wings-$tag-$arch.tar.gz"
url="https://github.com/$repository/releases/download/$tag/$asset"
echo "Downloading $tag for $arch..."
curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 \
 --connect-timeout 15 --max-time 600 --retry 3 "$url" -o "$work/$asset"
(cd "$work" && printf '%s  %s\n' "$expected" "$asset" | sha256sum --check)
if [[ -n "$download_dir" ]]; then
 mkdir -p -- "$download_dir"
 [[ ! -e "$download_dir/$asset" && ! -L "$download_dir/$asset" ]] || { echo 'Download destination already exists.' >&2; exit 1; }
 cp -- "$work/$asset" "$download_dir/$asset"
 echo "Verified archive saved to $download_dir/$asset"
 exit 0
fi
tar --extract --gzip --file "$work/$asset" --directory "$work" --no-same-owner
bash "$work/flatcar-wings/scripts/install.sh" "${forward[@]}"
