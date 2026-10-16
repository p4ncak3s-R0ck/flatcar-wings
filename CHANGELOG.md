# Changelog

## 0.1.1

- Attach a standalone `install.sh` to releases, with architecture detection,
  pinned archive verification, install-option forwarding, and download-only mode.
- Build draft releases automatically when VERSION changes on main or through
  manual workflow dispatch; retain matching version-tag releases.
- Check release installer downloads, corruption rejection, and packaged hashes.

## 0.1.0

- Package unmodified Wings v1.13.4 as AMD64 and ARM64 Flatcar system extensions.
- Add systemd service, account provisioning, installer, and maintenance guidance.
- Add pinned builds, image checks, provisioning templates, and GitHub release automation.
