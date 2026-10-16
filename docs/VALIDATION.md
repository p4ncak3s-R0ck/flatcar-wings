# GitHub repository validation

Checked locally on 2026-10-15:

- `make check`: ShellCheck and Bash syntax checks, six input/failure tests,
  AMD64/ARM64 image builds, independent image inspection, and native executable
  version check all passed.
- `make package REPOSITORY=example-owner/flatcar-wings`: created both installer
  archives, standalone images, provisioning fragments, and checksums.
- `tests/verify_release.py`: checked actual release hashes, archive member paths,
  installer image bytes, and generated provisioning hashes.
- All release Butane files passed strict transpilation with Butane v0.29.0.
- Both workflows passed actionlint v1.7.12 with ShellCheck integration.
- GitHub action references were resolved to full commit SHAs, and each pinned
  action's `action.yml` was retrieved from the official upstream repository.
- `git diff --cached --check` passed. Git excludes build outputs, download caches,
  images, archives, and the named private node configuration files.

These checks do not execute GitHub Actions, create a GitHub release, or boot
Flatcar. Confirm the first CI/tag workflow runs after pushing. Runtime testing
still requires a disposable Flatcar machine and an authenticated Panel.
