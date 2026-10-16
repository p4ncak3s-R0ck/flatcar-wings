#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -Eeuo pipefail
binary=/var/opt/coreos-wings/bin/wings
[[ -x $binary ]] || { printf 'Wings binary is missing.\n' >&2; exit 1; }
[[ -s /etc/pterodactyl/coreos-label-paths ]] || { printf 'Missing coreos-label-paths.\n' >&2; exit 1; }
selinux=$(getenforce)
if [[ $selinux != Disabled ]]; then
    chcon -t bin_t "$binary"
fi
# The file is root-owned configuration, parsed as data rather than sourced.
while IFS= read -r path || [[ -n $path ]]; do
    [[ -z $path || $path == \#* ]] && continue
    # Refuse system roots, traversal, symlink roots and obviously broad paths.
    [[ $path =~ ^/(var|run|tmp|mnt)/[^/]+(/[^/]+)*$ && $path != *'/..'* && $path != */. && $path != *'/./'* && $path != *//* ]] || {
        printf 'Unsafe label path: %s\n' "$path" >&2; exit 1;
    }
    case "$path" in
        /var/lib|/var/opt|/var/log|/var/home|/var/srv|/var/mnt)
            printf 'Label path is too broad: %s\n' "$path" >&2; exit 1 ;;
    esac
    [[ ! -L $path ]] || { printf 'Use the real directory, not a symlink: %s\n' "$path" >&2; exit 1; }
    mkdir -p -- "$path"
    if [[ $selinux != Disabled ]]; then
        # Reapply at service start, including after a full OS/filesystem relabel.
        # -P and --no-dereference prevent following symlinks in game files.
        chcon -R -P --no-dereference -t container_file_t -l s0 -- "$path"
    fi
done < /etc/pterodactyl/coreos-label-paths
