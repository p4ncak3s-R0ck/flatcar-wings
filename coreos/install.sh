#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -Eeuo pipefail
umask 077

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
usage() {
    cat <<'HELP'
Usage: sudo bash install.sh [--config FILE] [--version v1.X.Y --sha256 HEX]

Installs Pterodactyl Wings on Fedora CoreOS. Default: v1.13.4.
An existing /etc/pterodactyl/config.yml is never overwritten.
Without a node configuration, the service is enabled but not started.
Future versions require the SHA-256 of the matching upstream release asset.
HELP
}

version=v1.13.4
checksum=''
config=''
while (($#)); do
    case "$1" in
        --config|--version|--sha256)
            (($# >= 2)) || die "Missing value for $1"
            case "$1" in
                --config) config=$2 ;;
                --version) version=$2 ;;
                --sha256) checksum=$2 ;;
            esac
            shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown argument: $1" ;;
    esac
done
[[ $EUID == 0 ]] || die 'Run with sudo.'
[[ $version =~ ^v1\.[0-9]+\.[0-9]+$ ]] || die 'Use a stable Wings 1.x tag such as v1.13.4.'
[[ -r /etc/os-release ]] || die 'Missing /etc/os-release.'
# os-release is a trusted, root-owned operating system configuration file.
. /etc/os-release
[[ ${ID:-} == fedora && ${VARIANT_ID:-} == coreos ]] || die 'This installer targets Fedora CoreOS only.'
for tool in curl sha256sum install mktemp cmp cp mv systemctl flock chcon getenforce grep chmod chown uname sleep rm; do
    command -v "$tool" >/dev/null || die "Required host tool is missing: $tool"
done
case "$(uname -m)" in
    x86_64) arch=amd64 ;;
    aarch64) arch=arm64 ;;
    *) die 'Supported architectures: x86_64 and aarch64.' ;;
esac
if [[ -z $checksum && $version == v1.13.4 ]]; then
    case "$arch" in
        amd64) checksum=7e763389bb5d386a7d32ccdd46cffcf1ab9ed697e5c2aca7fe44183b527cd4c0 ;;
        arm64) checksum=516cc0b86fec092feb9893bacab2e1bf478b5477a5459ad9d722676c7549faa5 ;;
    esac
fi
[[ $checksum =~ ^[a-fA-F0-9]{64}$ ]] || die 'Provide --sha256 with the upstream release asset digest for this architecture.'
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for file in wings.service prepare.sh check.sh; do
    [[ -r $source_dir/$file ]] || die "Bundle is incomplete: $file is missing."
done
if [[ -n $config ]]; then
    [[ -s $config && -f $config ]] || die 'The node config must be a nonempty regular file.'
    if [[ -e /etc/pterodactyl/config.yml ]]; then
        cmp -s -- "$config" /etc/pterodactyl/config.yml || die 'A different config.yml already exists; replace it explicitly outside this installer.'
    fi
fi
if [[ -e /etc/systemd/system/wings.service ]]; then
    grep -q '^# Managed by coreos-wings$' /etc/systemd/system/wings.service || die 'An unmanaged wings.service exists. Review and back it up before replacing it.'
fi
systemctl cat docker.service >/dev/null 2>&1 || die 'docker.service is missing. This bundle requires a CoreOS image with Docker/Moby; it does not substitute Podman or change OS packages.'
exec 9>/run/coreos-wings-install.lock
flock -n 9 || die 'Another installer is running.'

install -d -m 0755 /var/opt/coreos-wings/bin
work=$(mktemp -d /var/opt/coreos-wings/.install.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
printf 'Downloading Wings %s for %s...\n' "$version" "$arch"
curl --fail --location --silent --show-error --retry 3 --connect-timeout 15 \
    --max-time 300 --proto '=https' --proto-redir '=https' \
    "https://github.com/pterodactyl/wings/releases/download/$version/wings_linux_$arch" \
    --output "$work/wings"
printf '%s  %s\n' "$checksum" "$work/wings" | sha256sum --check --status || die 'Wings checksum verification failed; installed binary was not changed.'
chmod 0755 "$work/wings"
if [[ $(getenforce) != Disabled ]]; then
    chcon -t bin_t "$work/wings"
fi
"$work/wings" version

install -d -m 0700 /etc/pterodactyl
if [[ -n $config && ! -e /etc/pterodactyl/config.yml ]]; then
    install -m 0600 -- "$config" /etc/pterodactyl/config.yml
fi
if [[ -e /etc/pterodactyl/config.yml ]]; then
    chown root:root /etc/pterodactyl/config.yml
    chmod 0600 /etc/pterodactyl/config.yml
fi
install -m 0755 "$source_dir/prepare.sh" /var/opt/coreos-wings/prepare.sh
install -m 0755 "$source_dir/check.sh" /var/opt/coreos-wings/check.sh
install -m 0644 "$source_dir/wings.service" /etc/systemd/system/wings.service
if [[ ! -e /etc/pterodactyl/coreos-label-paths ]]; then
    cat > /etc/pterodactyl/coreos-label-paths <<'PATHS'
# Container bind-mount directories. Add custom Wings data/mount paths here.
# Only dedicated paths beneath /var, /run, /tmp or /mnt are accepted.
/var/lib/pterodactyl
/run/wings
/tmp/pterodactyl
PATHS
    chmod 0600 /etc/pterodactyl/coreos-label-paths
fi
had_previous=false
if [[ -f /var/opt/coreos-wings/bin/wings ]]; then
    cp -p -- /var/opt/coreos-wings/bin/wings "$work/wings.previous"
    mv -f -- "$work/wings.previous" /var/opt/coreos-wings/bin/wings.previous
    had_previous=true
fi
if [[ -f /var/opt/coreos-wings/VERSION ]]; then
    cp -p /var/opt/coreos-wings/VERSION /var/opt/coreos-wings/VERSION.previous
fi
mv -f -- "$work/wings" /var/opt/coreos-wings/bin/wings
printf '%s\n' "$version" > /var/opt/coreos-wings/VERSION
systemctl daemon-reload
systemctl enable --now docker.service
systemctl enable wings.service
if [[ -s /etc/pterodactyl/config.yml ]]; then
    failed=false
    systemctl restart wings.service || failed=true
    sleep 3
    systemctl is-active --quiet wings.service || failed=true
    if [[ $failed == true ]]; then
        systemctl stop wings.service || true
        if [[ $had_previous == true ]]; then
            cp -p -- /var/opt/coreos-wings/bin/wings.previous "$work/wings.restore"
            mv -f -- "$work/wings.restore" /var/opt/coreos-wings/bin/wings
            if [[ -f /var/opt/coreos-wings/VERSION.previous ]]; then
                cp -p /var/opt/coreos-wings/VERSION.previous /var/opt/coreos-wings/VERSION
            fi
            systemctl start wings.service || true
            printf 'Restored the previous binary. Unit/config/label-path changes were retained.\n' >&2
        fi
        die 'Wings did not stay active. Inspect: journalctl -u wings -n 100 --no-pager'
    fi
    printf '\nWings is running. Run: sudo bash /var/opt/coreos-wings/check.sh\n'
else
    printf '\nInstalled. Save your Panel node config as /etc/pterodactyl/config.yml, then run:\n'
    printf '  sudo chmod 600 /etc/pterodactyl/config.yml\n  sudo systemctl start wings\n'
fi
printf 'Configure node TLS, firewall/NAT and game allocation ports as described in README.md.\n'
