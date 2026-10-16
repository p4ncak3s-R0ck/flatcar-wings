# Pterodactyl Wings for Fedora CoreOS

Install Wings as a native systemd service while game servers run in the host's
Docker/Moby engine. This is a community integration, not an official Pterodactyl
or Fedora CoreOS distribution. It does not build a new OS image.

The default Wings version is **v1.13.4**. It targets the stable **Panel 1.x** line;
check upstream Panel/Wings version compatibility before installation. Supported
CPU architectures: x86_64 and aarch64. The installer downloads the corresponding
official release binary and verifies its pinned SHA-256 before executing it.

For a fresh host, use the [online Ignition profile](ignition/README.md) to
install Wings automatically on first boot. The public profile stays free of
node credentials; a local host config adds your SSH key and optional Panel YAML.

## Install on an existing CoreOS host

To install from this repository's `coreos` branch:

```bash
curl -fL https://github.com/p4ncak3s-R0ck/flatcar-wings/archive/refs/heads/coreos.tar.gz -o flatcar-wings-coreos.tar.gz
tar -xzf flatcar-wings-coreos.tar.gz
cd flatcar-wings-coreos/coreos
sudo bash install.sh
```

Alternatively, copy the standalone `coreos-wings.tar.gz` bundle to the host:

```bash
tar -xzf coreos-wings.tar.gz
cd coreos-wings
sudo bash install.sh
```

This enables Docker and enables Wings for future boots. Wings waits until a
nonempty `/etc/pterodactyl/config.yml` exists. Use a dedicated CoreOS node with
the built-in Docker/Moby service. The installer stops with an explanation if
Docker is absent. It does not install Docker using a generic Fedora/DNF script
and does not treat Podman as a compatible replacement.

In your Pterodactyl Panel, create a Location and Node, then open the node's
**Configuration** tab. Save the complete generated YAML on the host. The Panel
is a separate application; this bundle only installs Wings.

```bash
sudo vi /etc/pterodactyl/config.yml
sudo chmod 600 /etc/pterodactyl/config.yml
sudo systemctl start wings
sudo bash /var/opt/coreos-wings/check.sh
```

Alternatively, supply a node configuration you already downloaded:

```bash
sudo bash install.sh --config ./my-node-config.yml
```

The installer does not overwrite an existing configuration. Configurations
contain node credentials: do not commit them to a repository or paste them into
public logs. Use the explicit Wings binary path if using the Panel's generated
`wings configure` command:

```bash
sudo /var/opt/coreos-wings/bin/wings configure --help
```

## Persistence and paths

| Item | Path |
|---|---|
| Wings executable | `/var/opt/coreos-wings/bin/wings` |
| Service preparation helper | `/var/opt/coreos-wings/prepare.sh` |
| Node configuration | `/etc/pterodactyl/config.yml` |
| Service unit | `/etc/systemd/system/wings.service` |
| Default game files | `/var/lib/pterodactyl/volumes` |
| Default backups | `/var/lib/pterodactyl/backups` |
| Docker images and layers | `/var/lib/docker` |
| Wings application log | `/var/log/pterodactyl/wings.log` |
| Additional service logs | `journalctl -u wings` |

CoreOS retains `/var` and local configuration in `/etc` across OS updates. The
installer does not modify the protected OS tree or layer additional RPMs.
Wings uses root and the real Docker socket, as needed for normal host-level
server management. It is not run in a nested Docker container.

## SELinux and custom storage

SELinux remains enabled. Before Wings starts, the preparation helper labels its
binary `bin_t` and its container bind-mount directories `container_file_t:s0`.
This includes the generated machine-id/passwd files beneath `/run/wings` and
the installation temporary directory. These labels are reapplied at each Wings
start because CoreOS does not include `semanage` by default.

The defaults match upstream Wings paths. For custom storage, edit
`/etc/pterodactyl/coreos-label-paths` to contain dedicated real directories,
one per line, matching your `config.yml`. Include custom `system.data`,
`system.tmp_directory`, `system.machine_id.directory`, `system.passwd.directory`
when enabled, and any additional host mounts passed to containers. Use their
resolved `/var/...` paths instead of `/srv` or `/mnt` symlinks. The helper does
not follow symlinks inside game files.

Only list dedicated container-data directories. Relabeling is recursive and
can take time on large nodes. Do not list directories belonging to another
application. Shared `s0` labeling is used because Wings does not assign its own
per-server MCS labels; Docker namespaces, mounts, dropped capabilities and file
permissions still provide their usual isolation. This bundle does not add
per-server SELinux categories.

For a separate data disk, configure its mount before running the installer and
add its mount path with `sudo systemctl edit wings`:

```ini
[Unit]
RequiresMountsFor=/var/mnt/game-data
```

Keep that override alongside the matching Wings paths and SELinux label paths.
The included unit already waits for the default Docker and Wings data mounts.

## Networking, TLS and storage capacity

Set the node FQDN and protocol correctly in the Panel. For direct HTTPS, provide
the certificate/key paths referenced in `config.yml` and arrange renewal. With
an HTTPS reverse proxy, configure the upstream connection and trusted proxy
settings according to Pterodactyl's documentation. This bundle does not obtain
certificates or configure a proxy.

Allow the configured Wings API port (commonly TCP 8080), SFTP port (commonly TCP
2022), and each game's allocation ports/protocols through your upstream firewall
and NAT. Do not expose Docker's API. The installer does not replace existing
firewall rules or assume firewalld is installed. Docker-published ports require
Docker-aware firewall policy, not just a rule for the host's API listener.

The node needs sufficient persistent space for both game data and Docker images.
Set up allocation IPs in the Panel using addresses actually assigned to the host.

## Update and recover

CoreOS OS updates do not update this separately installed Wings binary.
Re-running the installer re-downloads its pinned version. To install another
stable Wings 1.x release, supply the matching architecture's official asset
SHA-256 (GitHub's release asset API exposes a `digest` field):

```bash
sudo bash install.sh --version v1.X.Y --sha256 REPLACE_WITH_64_HEX_DIGITS
```

An update restarts Wings, so use a maintenance window. The installer retains
one previous binary. If the service fails immediately, it attempts to restore
that binary. This is only an early process-liveness check; it is not a complete
Panel/API/game-server health check. Unit, configuration permissions and label
path changes are not rolled back.

For manual recovery, first back up your current binary and config, then:

```bash
sudo systemctl stop wings
sudo cp -p /var/opt/coreos-wings/bin/wings.previous /var/opt/coreos-wings/bin/wings
sudo systemctl start wings
sudo journalctl -u wings -n 100 --no-pager
```

Rolling back CoreOS itself does not roll back Wings, Docker data, game files,
or Panel state. Back those up separately. Keep CoreOS automatic updates enabled,
but configure Zincati maintenance/reboot windows for your workload: an OS reboot
interrupts game servers on a standalone node.

## Validate on your host

```bash
sudo bash /var/opt/coreos-wings/check.sh
sudo journalctl -u wings -f
```

Then check that the Panel sees the node online, install and launch a small game
server, connect to it and SFTP, stop/start it through the Panel, and reboot the
host to verify recovery. An unauthenticated request to Wings may return an
authorization error; process liveness alone does not prove Panel connectivity.
For SELinux failures, inspect `sudo journalctl -k -g 'avc:.*denied'` and review
the bind-mount paths and labels before changing policy.

## Validation performed for this bundle

Shell syntax; ten isolated tests of installer/config preservation, checksum
failure, early rollback, and label-path validation; upstream amd64 binary
download, SHA-256 verification, executable version/help checks; and static
systemd unit validation with fixture dependencies. The isolated tests mock
systemd, downloads and SELinux operations; they do not exercise the real host
policy or daemon. Run them with `python3 -m unittest discover -s tests -v`.
No Fedora CoreOS VM, Docker daemon or Pterodactyl Panel
was available in the build environment. The arm64 digest was obtained from the
official GitHub asset metadata; the arm64 executable was not run.

## Sources

- https://docs.pterodactyl.io/v1/wings/installing
- https://docs.pterodactyl.io/v1/guides/wings-installation/centos8
- https://github.com/pterodactyl/wings/releases/tag/v1.13.4
- https://docs.fedoraproject.org/en-US/fedora-coreos/storage/
- https://docs.fedoraproject.org/en-US/fedora-coreos/selinux/
- https://docs.fedoraproject.org/en-US/fedora-coreos/auto-updates/

Installer integration code: MIT license. Wings itself is downloaded separately
from upstream and retains its upstream license.
