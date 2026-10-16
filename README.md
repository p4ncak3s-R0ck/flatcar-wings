# Flatcar Wings

**Fedora CoreOS:** this branch also includes the native Wings installer in
[`coreos/`](coreos/README.md). On a CoreOS host, download this branch and run:

```bash
curl -fL https://github.com/p4ncak3s-R0ck/flatcar-wings/archive/refs/heads/coreos.tar.gz -o flatcar-wings-coreos.tar.gz
tar -xzf flatcar-wings-coreos.tar.gz
cd flatcar-wings-coreos/coreos
sudo bash install.sh
```

Follow the [CoreOS setup instructions](coreos/README.md) to add your Panel node
configuration, TLS and firewall rules. The Flatcar extension instructions below
apply to Flatcar hosts.

For automated first boot, see the [CoreOS online Ignition profile](coreos/ignition/README.md).

Run a **Pterodactyl Wings node on Flatcar Container Linux** using a systemd
extension. Static upstream Wings binaries are overlaid into `/usr`; node
credentials and game data stay on writable, persistent storage.

- AMD64 and ARM64 images; pinned upstream Wings **v1.13.4**.
- Uses Flatcar's existing Docker/containerd extensions.
- Includes a root systemd service, game-server account provisioning, and installer.
- CI builds and inspects both images; version tags create draft GitHub Releases.

**Status:** experimental integration. Build and structural checks pass; live
Flatcar/Panel operation has not been verified. Flatcar is not on Wings' official
supported OS list. A Pterodactyl Panel must already exist.

## Install a release

From this repository's **Releases** page, download **install.sh**. Save the
Panel-generated node Configuration YAML as `config.yml`, then run on Flatcar:

```bash
sudo bash install.sh --config ./config.yml
sudo journalctl -u wings -f
```

The script detects AMD64/ARM64, downloads its matching release archive, verifies
a SHA-256 pinned into the script, and runs the bundled installer. It supports
`--replace` and `--no-start`. To fetch the verified archive on another Linux
machine without installing:

```bash
bash install.sh --download-only ./downloads
```

Alternatively, download `flatcar-wings-vVERSION-amd64.tar.gz` or
`flatcar-wings-vVERSION-arm64.tar.gz` from Releases. Extract it, enter
`flatcar-wings/`, and run `sudo bash scripts/install.sh --config ./config.yml`.

The release installer includes a prebuilt image. No compiler or package manager
is needed on the Flatcar machine. Installation without starting Wings:

```bash
sudo bash install.sh --no-start
sudo install -m 0600 ./config.yml /etc/pterodactyl/config.yml
sudo systemctl start wings.service
```

The automatic GitHub **Source code** archives contain source only. Build these
on a Linux workstation first, or download an installer archive from Releases.
If no release is published yet, use the source-build instructions below.

See [operations](docs/OPERATIONS.md) for TLS, ports, persistence, reboot policy,
upgrades, rollback, removal, and provisioning. Credentials are never generated
or embedded in extension images.

## Build from source

On a Debian/Ubuntu workstation or WSL with Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y binutils curl make python3 shellcheck squashfs-tools
make check
```

`make check` runs guard tests and lint checks, downloads checksum-pinned Wings
executables, builds both images, and inspects their contents. Building requires
no root, Docker, or loop devices. To build just one architecture:

```bash
bash scripts/build.sh amd64
```

Copy this project, including `dist/amd64/` (or `dist/arm64/`), to the Flatcar
host before using `scripts/install.sh`. Build outputs and downloaded binaries
are ignored by Git.

## Provisioning and release assets

Generate Butane files with actual image hashes and your repository's release URLs:

```bash
make examples REPOSITORY=YOUR-USERNAME/flatcar-wings
make package REPOSITORY=YOUR-USERNAME/flatcar-wings
```

`make package` requires both images to be built. It creates `release/` with:

| Asset | Use |
|---|---|
| `install.sh` | Standalone architecture-detecting installer with pinned archive hashes |
| `flatcar-wings-vVERSION-ARCH.tar.gz` | Installer bundle for one architecture |
| `wings-ARCH.raw` | Standalone image; install as `/etc/extensions/wings.raw` |
| `flatcar-ARCH.bu` | Provisioning fragment with a release URL and actual image hash |
| `SHA256SUMS` | Checksums for images, installers, and provisioning |

Use `sha256sum -c SHA256SUMS` after downloading all referenced assets into one
folder. Checksums detect corruption; they are not publisher signatures.
Merge provisioning into your complete host configuration, then transpile it
using the official Butane tool. Maintain SSH access and your storage mounts.

## Put this repository on GitHub

Upload this folder's **contents**, including `.github/`, into a new repository,
or use Git from this folder:

```bash
git init -b main
git add .
git commit -m "Initial Flatcar Wings extension"
git remote add origin https://github.com/YOUR-USERNAME/flatcar-wings.git
git push -u origin main
```

The CI workflow runs on pushes, pull requests, and manual dispatch. The release
workflow runs when you change `VERSION` on `main`, push a matching
`vMAJOR.MINOR.PATCH` tag, or use **Actions → Release → Run workflow**.
A version bump on `main` needs no separate tag command. For a tag release:

```bash
git tag v0.1.1
git push origin v0.1.1
```

After successful checks, it creates a **draft release** with `install.sh` and
both architecture builds. Rerunning the same commit refreshes its draft assets;
published releases and drafts from different commits are not overwritten. Review
and publish the draft in GitHub. No personal access token is required; the
publish job uses the repository-scoped `GITHUB_TOKEN` with `contents: write`.
Repository/organization policy must permit the configured GitHub Actions.
The draft's public download URLs work after publishing (subject to repository
visibility). Forks automatically use their own owner/repository in asset URLs.

See [contributing](CONTRIBUTING.md), [security reporting](SECURITY.md), and the
[changelog](CHANGELOG.md). `VERSION` controls the integration release;
`config/wings.env` controls the upstream Wings version and both binary digests.

## Validation and license

Current checks exercise input rejection, checksum failure, image metadata,
static binary identity, and packaged release integrity. They do not boot Flatcar,
contact an authenticated Panel, or run games. See [repository validation](docs/VALIDATION.md) for the checks performed.
The original build's additional checks are recorded in [initial validation](docs/INITIAL-VALIDATION.md).
GitHub workflow execution itself must be confirmed after pushing the repository.

Integration code is [MIT licensed](LICENSE). Upstream Wings' [MIT license](LICENSE-WINGS)
is also included inside each extension image.

References: [Flatcar sysext documentation](https://www.flatcar.org/docs/latest/sys-ext/),
[Wings installation](https://docs.pterodactyl.io/v1/wings/installing), and
[upstream Wings](https://github.com/pterodactyl/wings).
