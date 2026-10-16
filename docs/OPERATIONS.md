# Operations

## Host requirements and installation

Use a current supported Flatcar release with its default Docker and containerd
extensions enabled. Provision persistent game storage before installing Wings.
The installer is for Flatcar only; it rejects other operating systems.

Wings runs as root to manage host Docker. The default `pterodactyl` game-server
account is created with `systemd-sysusers`, using an available system UID/GID.
Existing accounts are preserved. Use `system.username: pterodactyl` in your
Panel-generated node YAML, or provision your custom account separately.
When migrating game files, preserve the old numeric UID/GID rather than blindly
changing ownership or allocating a different identity.

The installer refuses `/etc/systemd/system/wings.service` overrides or runtime
Wings units/masks. Review and move those aside before migrating. Existing unit
drop-ins still apply; inspect them using `systemctl cat wings`.

`--no-start` skips startup during installation. With configuration present,
Wings is started on subsequent boots through a `multi-user.target` drop-in.
Use `sudo systemctl mask wings.service` to keep it disabled persistently;
unmask it before starting again.

## Installed paths

| Path | Purpose |
|---|---|
| `/etc/extensions/wings.raw` | Read-only extension image |
| `/usr/bin/wings` | Binary exposed through the extension overlay |
| `/usr/lib/systemd/system/wings.service` | Root service controlling host Docker |
| `/usr/lib/sysusers.d/flatcar-wings.conf` | Default game-server account |
| `/etc/pterodactyl/config.yml` | Private node configuration, mode 0600 |
| `/var/lib/pterodactyl` | Persistent games, backups, and Wings state |
| `/var/log/pterodactyl` | Wings logs |

The image's `ID=flatcar`, `SYSEXT_LEVEL=1.0`, and architecture metadata are
validated during loading. Static linking avoids coupling the binary to one
Flatcar release's libraries. This does not guarantee compatibility with every
future kernel, Docker, or Wings version.

## TLS and ports

Use the Panel-generated TLS settings. Provision certificates at the paths in
the node configuration; the installer does not issue certificates or disable
certificate verification. Make the configured API port (commonly TCP 8080),
SFTP port (commonly TCP 2022), and each game's allocated TCP/UDP ports reachable
as required. The Panel and users need working routes to the relevant endpoints.
The installer does not modify firewall, DNS, or router rules.

## Persistence and reboots

For a dedicated game disk, mount it at `/var/lib/pterodactyl`. The service uses
`RequiresMountsFor` to wait for configured mounts. Preserve node credentials and
back up game data separately from the extension image.

Flatcar automatically stages OS updates and may reboot to activate them.
Coordinate maintenance reboots with clean game-server shutdowns. The optional
`examples/maintenance-reboots.bu` fragment disables automatic rebooting while
leaving downloads enabled; then you must schedule reboots to apply OS patches.
This extension does not drain games or manage Flatcar update policy.

## Provision new hosts

Build both images and run:

```bash
make examples REPOSITORY=OWNER/REPO TAG=v0.1.0
```

The generated `dist/examples/flatcar-*.bu` fragments reference your GitHub
release images with their actual SHA-256 hashes. Upload/publish those assets
first, or replace the image URL with your own HTTPS artifact host. For private
repositories, arrange authenticated retrieval separately; a plain GitHub URL
will not grant private access automatically.

Merge into the full host provisioning file, preserving SSH and storage setup:

```bash
butane --strict --pretty host.bu > ignition.json
```

Supply Ignition through the hosting platform's normal provisioning mechanism.
After boot, install your private node YAML and start Wings. Do not publish node
tokens in provisioning repositories.

## Update

Wings updates are independent of Flatcar OS updates. First stop game servers
cleanly through the Panel. Extract the new release installer and run:

```bash
sudo bash scripts/install.sh --replace
```

Pass `--config ./new-config.yml` only if you also intend to replace configuration.
The installer backs up the existing image at
`/var/lib/flatcar-wings/wings.previous.raw` and any replaced node YAML at
`/etc/pterodactyl/config.yml.previous`. This is one previous version, not a
backup history. Updating stops/restarts Wings and reloads all sysext overlays;
use a maintenance window. On a load failure, the installer exits and leaves the
previous image available for manual recovery.

Flatcar's `ensure-sysext` integration reloads unit files when the sysext service
restarts. Use `systemctl restart systemd-sysext.service`, not a standalone
`systemd-sysext refresh` that bypasses this integration.

## Roll back

During maintenance, restore the saved image:

```bash
sudo systemctl stop wings.service
sudo cp /var/lib/flatcar-wings/wings.previous.raw /etc/extensions/.wings.raw.restore
sudo mv /etc/extensions/.wings.raw.restore /etc/extensions/wings.raw
sudo systemctl restart systemd-sysext.service
sudo systemctl start wings.service
```

Restore node YAML separately if an upgrade changed it incompatibly. Neither
sysext rollback nor Flatcar OS rollback restores game/database state.

## Remove

Stop games through the Panel, then run:

```bash
sudo systemctl stop wings.service
sudo rm /etc/extensions/wings.raw
sudo systemctl restart systemd-sysext.service
sudo systemctl daemon-reload
```

Credentials, accounts, logs, and game files are retained. Remove any provisioning
rules that would reinstall Wings on a replacement host.

## Troubleshooting

```bash
systemd-sysext status
systemctl status wings.service docker.service
journalctl -u wings.service -b --no-pager
docker info
```

Check the node's configured addresses, certificates, and port allocations.
Redact tokens, authorization headers, and private keys before sharing logs.
Test API access, SFTP, game creation, resource limits, backups, and reboot
recovery on a disposable node before migrating existing workloads.
