#!/usr/bin/env bash
set -euo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
config='' replace=0 start=1
while (($#)); do
 case "$1" in
  --config) [[ $# -ge 2 ]] || { echo '--config requires a file' >&2; exit 2; }; config=$2; shift 2 ;;
  --replace) replace=1; shift ;;
  --no-start) start=0; shift ;;
  -h|--help) echo 'sudo bash scripts/install.sh [--config PANEL-GENERATED.yml] [--replace] [--no-start]'; exit 0 ;;
  *) echo "Unknown argument: $1" >&2; exit 2 ;;
 esac
done
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
# shellcheck disable=SC1091
. /etc/os-release
[[ ${ID:-} == flatcar ]] || { echo 'This installer only runs on Flatcar.' >&2; exit 1; }
case $(uname -m) in x86_64) arch=amd64 ;; aarch64) arch=arm64 ;; *) echo 'Unsupported architecture' >&2; exit 1 ;; esac
(cd "$base/dist/$arch" && sha256sum --check SHA256SUMS)
if [[ -e /run/systemd/system/wings.service || -L /run/systemd/system/wings.service ]]; then
 echo "A runtime Wings unit or mask exists. Review it before installing." >&2; exit 1
fi
if [[ -e /etc/systemd/system/wings.service || -L /etc/systemd/system/wings.service ]]; then
 echo 'An /etc/systemd/system/wings.service override exists. Review and move it aside before installing.' >&2; exit 1
fi
if [[ -e /etc/extensions/wings.raw || -L /etc/extensions/wings.raw ]]; then
 [[ $replace == 1 ]] || { echo 'Extension exists. Use --replace to update it.' >&2; exit 1; }
fi
if [[ -n "$config" ]]; then
 [[ -s "$config" ]] || { echo 'Configuration is missing or empty.' >&2; exit 1; }
 [[ ! -e /etc/pterodactyl/config.yml || $replace == 1 ]] || { echo 'Configuration exists. Use --replace to replace it.' >&2; exit 1; }
fi
# Start the bundled Flatcar Docker daemon; no Docker installation script needed.
systemctl start docker.service
docker info >/dev/null
install -d -m 0755 /etc/extensions /var/lib/flatcar-wings
install -d -m 0700 /etc/pterodactyl
if systemctl is-active --quiet wings.service; then systemctl stop wings.service; fi
if [[ -f /etc/extensions/wings.raw ]]; then
 cp --dereference -- /etc/extensions/wings.raw /var/lib/flatcar-wings/wings.previous.raw
fi
if [[ -n "$config" ]]; then
 if [[ -f /etc/pterodactyl/config.yml ]]; then
  install -m 0600 /etc/pterodactyl/config.yml /etc/pterodactyl/config.yml.previous
 fi
 install -m 0600 "$config" /etc/pterodactyl/config.yml.new
 mv -f -- /etc/pterodactyl/config.yml.new /etc/pterodactyl/config.yml
fi
install -m 0644 "$base/dist/$arch/wings.raw" /etc/extensions/.wings.raw.new
mv -f -- /etc/extensions/.wings.raw.new /etc/extensions/wings.raw
# Flatcar's ensure-sysext integration discovers new units. Do not use a bare
# `systemd-sysext refresh`, which skips that integration.
# Runtime merge can pull in wings.service through multi-user.target; mask it
# temporarily so --no-start is respected and replacement is controlled.
masked=0
cleanup() { if [[ $masked == 1 ]]; then systemctl unmask --runtime wings.service >/dev/null; fi; }
trap cleanup EXIT
systemctl mask --runtime wings.service >/dev/null
masked=1
systemctl restart systemd-sysext.service
systemctl daemon-reload
systemctl unmask --runtime wings.service >/dev/null
masked=0
systemctl daemon-reload
systemctl reset-failed wings.service || true
/usr/bin/wings version
if [[ $start == 1 && -s /etc/pterodactyl/config.yml ]]; then
 systemctl start wings.service
 systemctl --no-pager --full status wings.service
else
 echo 'Installed. Add the Panel-generated /etc/pterodactyl/config.yml (mode 0600), then run: sudo systemctl start wings'
fi
