#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -uo pipefail
failures=0
check() {
    local label=$1
    shift
    if "$@"; then printf 'PASS: %s\n' "$label"; else printf 'FAIL: %s\n' "$label"; failures=$((failures + 1)); fi
}
check 'Wings executable' test -x /var/opt/coreos-wings/bin/wings
check 'Nonempty node configuration' test -s /etc/pterodactyl/config.yml
check 'Docker active' systemctl is-active --quiet docker.service
check 'Wings active' systemctl is-active --quiet wings.service
if command -v docker >/dev/null; then
    check 'Docker daemon reachable' docker info --format 'Docker {{.ServerVersion}}; cgroups {{.CgroupVersion}}; security {{json .SecurityOptions}}'
else
    printf 'FAIL: docker CLI missing\n'
    failures=$((failures + 1))
fi
if command -v getenforce >/dev/null; then
    printf 'SELinux: %s\n' "$(getenforce)"
    ls -Zd /var/lib/pterodactyl /run/wings /var/opt/coreos-wings/bin/wings 2>/dev/null || true
fi
printf '\nConfigured listener/firewall/TLS and actual game startup still need testing from the Panel.\n'
printf 'Logs: sudo journalctl -u wings -n 100 --no-pager\n'
((failures == 0))
