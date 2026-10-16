# Validation — 2026-10-15

Bundle v0.1.0; pinned upstream Wings v1.13.4.

Completed on an x86-64 Ubuntu 24.04 build host:

- Downloaded both upstream release executables and matched their SHA-256 digests
  against GitHub's release asset metadata (recorded in the original installer bundle's `upstream/release.json`;
  this repository keeps the pinned values in `config/wings.env`).
- Inspected ELF headers for AMD64 / ARM64 architecture and static linking.
- Built both SquashFS images with squashfs-tools 4.6.1.
- Extracted both images with `unsquashfs`; binary bytes matched the pinned
  upstream executables. Verified image SHA-256 files and provisioning hashes.
- Executed the AMD64 binary's version and configure-help commands successfully.
- Checked Bash syntax and ShellCheck 0.9.0: no warnings/errors.
- Checked the service with `systemd-analyze verify` in an extracted root.
  The root contained host systemd targets and a test-only Docker service stub;
  no Docker daemon or Wings service was started by this check.
- Ran systemd-sysusers against the extracted root in dry-run mode. It correctly
  planned creation of the pterodactyl group/user without modifying the host.
- Compiled all three Butane examples with Butane v0.29.0 in strict mode.
- Exercised install help and the non-Flatcar OS rejection guard on Ubuntu.
- Rebuilt the AMD64 image and confirmed the output was byte-identical.

Not tested here:

- Extension merge and reboot on a live Flatcar host.
- Authenticated communication with a Pterodactyl Panel.
- Creating games, resource limits, networking, TLS, SFTP, backup/restore,
  actual upgrade/rollback, automatic reboot handling, or ARM64 execution.

These are build and structural checks, not an end-to-end deployment test.
Start with a disposable Flatcar node and test those operations before migration.
