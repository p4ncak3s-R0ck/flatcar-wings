# Online Ignition profile

`online.ign` is an architecture-independent **Ignition 3.4.0** profile for a
fresh Fedora CoreOS host. It embeds the integration's installer, helpers and
Wings service, enables Docker, and runs the installer after networking is ready.
The installer selects AMD64/ARM64 and verifies the pinned upstream Wings binary.

The repository hosting location is:

```text
https://raw.githubusercontent.com/p4ncak3s-R0ck/flatcar-wings/coreos/coreos/ignition/online.ign
```

That URL becomes available only after this change is pushed to the `coreos`
branch. Until then, use a copy of `online.ign` on an HTTPS server you control
with `--profile-url`, or wait for the branch to be published.

The public profile has **no SSH keys, passwords, Panel tokens or disk layout**.
Use the host-config generator below to add SSH access. Ignition runs on first
boot; editing a hosted profile does not reconfigure already-provisioned nodes.

## Generate your host config

On a workstation with Python 3.10+, from the repository root:

```bash
python3 coreos/ignition/make-host.py \
  --ssh-key ~/.ssh/id_ed25519.pub \
  --hostname wings-01 \
  --output host.ign
```

Use a public `.pub` file, not your private SSH key. Repeat `--ssh-key` to include
multiple public-key files. This creates SSH access for the standard `core` user.
It does not enable password or root SSH login.

If your Panel node already exists, provision its generated YAML at the same time:

```bash
python3 coreos/ignition/make-host.py \
  --ssh-key ~/.ssh/id_ed25519.pub \
  --node-config /path/to/config.yml \
  --output host.ign
```

The output is created with mode `0600`, never replaces an existing file, and is
ignored by Git. A host config with node YAML contains plaintext credentials
(base64 is only encoding): keep it private and do not publish it at the public
profile URL. Node TLS certificates and private keys still need separate
provisioning if the YAML references them.

The host config merges the hosted public profile with a SHA-256 check against
your checked-out `online.ign` bytes. A changed remote profile fails verification
rather than silently running different code. For reproducible installations,
use the profile's raw URL at a specific published commit with `--profile-url`:

```bash
python3 coreos/ignition/make-host.py \
  --ssh-key ~/.ssh/id_ed25519.pub \
  --profile-url https://raw.githubusercontent.com/p4ncak3s-R0ck/flatcar-wings/COMMIT_SHA/coreos/ignition/online.ign \
  --output host.ign
```

Replace `COMMIT_SHA` with the actual published commit containing the matching
profile. The generator does not contact the URL; ensure it is reachable from
the new host. The initramfs needs working DNS, HTTPS access and a usable clock
to retrieve it. Wings installation later also needs GitHub download access.

## Install Fedora CoreOS

Boot the official CoreOS live ISO and transfer your private `host.ign` to it.
Identify your target disk before running the following; installing CoreOS
overwrites the selected disk:

```bash
sudo coreos-installer install /dev/REPLACE_WITH_TARGET_DISK --ignition-file host.ign
sudo reboot
```

For providers accepting Ignition user-data, supply the contents of `host.ign`
instead. If your host config itself is available at a private, reachable HTTPS
URL, `coreos-installer install` also supports `--ignition-url URL` and
`--ignition-hash sha256-HEX`. The generic public profile alone supplies no SSH
access and should not be used as a complete bare-metal host configuration.

After first boot:

```bash
ssh core@YOUR_NODE_IP
sudo journalctl -u coreos-wings-install -b --no-pager
sudo bash /var/opt/coreos-wings/check.sh
```

If no Panel YAML was supplied, Wings is installed/enabled but waits for
`/etc/pterodactyl/config.yml`. Add that file, set mode `0600`, and start Wings
as described in the [CoreOS setup guide](../README.md). Configure TLS, firewall,
NAT, allocations, separate storage mounts and maintenance windows there too.

The install unit retries on failure after 30 seconds, allows 15 minutes per
attempt, and writes `/var/opt/coreos-wings/.provisioned` only on success.
It skips installation on later boots. After correcting a provisioning problem,
inspect logs and use `sudo systemctl restart coreos-wings-install` to retry.
Use the normal installer for later Wings upgrades; Ignition does not provide
continuous management or automatically upgrade already-installed Wings.

## Maintain and validate

Regenerate after changing the embedded installer, helpers or service:

```bash
python3 coreos/ignition/build.py
python3 coreos/ignition/build.py --check
python3 -m unittest discover -s coreos/tests -v
ignition-validate coreos/ignition/online.ign
ignition-validate host.ign
```

`online.ign.sha256` covers the exact generated profile, including its embedded
scripts. No Butane installation is required; the generator emits Ignition JSON
directly. The unit and both generated config forms were statically validated;
actual first boot, Docker/game startup and Panel connectivity still require a
CoreOS VM or physical node.

References: [Ignition 3.4.0 specification](https://coreos.github.io/ignition/configuration-v3_4/),
[CoreOS installer options](https://coreos.github.io/coreos-installer/cmd/install/).
