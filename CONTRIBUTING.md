# Contributing

Use Linux with Bash, Python 3.10+, curl, binutils, squashfs-tools, and ShellCheck.
Run `make check` before opening a pull request. This downloads pinned upstream
Wings executables and builds/verifies both architectures without root.

For upstream Wings updates, edit `config/wings.env`: change the version and
both release asset SHA-256 values after checking upstream release metadata.
Delete the ignored `upstream/` cache before rebuilding. Never bypass a digest
mismatch. Keep the upstream license synchronized if its contents change.

Change `VERSION` for an integration release. It is independent of Wings' version.
Use `make package REPOSITORY=OWNER/REPO` to inspect the resulting release assets.
Remove `release/` before packaging again; the packager refuses to mix builds.

Build checks do not verify a running Wings node. Changes to the service,
installer, host paths, networking, or provisioning should also be exercised on
a disposable Flatcar machine with a real Panel. Include Flatcar/Wings versions,
architecture, and results in the pull request.

Never commit node config, credentials, private keys, downloaded executables,
images, or game data. Release images belong in GitHub Releases, not Git history.
