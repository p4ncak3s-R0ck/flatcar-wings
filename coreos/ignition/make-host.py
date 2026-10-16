#!/usr/bin/env python3
"""Build a private host config which verifies and merges the public profile."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
DEFAULT_URL = "https://raw.githubusercontent.com/p4ncak3s-R0ck/flatcar-wings/coreos/coreos/ignition/online.ign"


def public_keys(path):
    keys = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2 or not re.fullmatch(r"(?:ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(?:256|384|521)|sk-ssh-ed25519@openssh.com|sk-ecdsa-sha2-nistp256@openssh.com)", parts[0]):
            raise ValueError(f"Not an OpenSSH public key: {path.name}")
        try:
            blob = base64.b64decode(parts[1], validate=True)
        except ValueError as error:
            raise ValueError(f"Invalid public-key encoding: {path.name}") from error
        size = int.from_bytes(blob[:4], "big")
        if size == 0 or blob[4:4 + size] != parts[0].encode() or len(blob) <= 4 + size:
            raise ValueError(f"Invalid public-key structure: {path.name}")
        if line not in keys:
            keys.append(line)
    if not keys:
        raise ValueError(f"No public keys in {path.name}")
    return keys


def make_config(keys, profile_url, profile_bytes, node_config=None, hostname=None):
    url = urlsplit(profile_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("The public profile URL must use HTTPS without embedded credentials")
    config = {
        "ignition": {"version": "3.4.0", "config": {"merge": [{
            "source": profile_url,
            "verification": {"hash": "sha256-" + hashlib.sha256(profile_bytes).hexdigest()},
        }]}},
        "passwd": {"users": [{"name": "core", "sshAuthorizedKeys": list(dict.fromkeys(keys))}]},
    }
    files = []
    if node_config is not None:
        if not node_config.strip():
            raise ValueError("Node configuration is empty")
        files.append({"path": "/etc/pterodactyl/config.yml", "mode": 0o600,
                      "contents": {"source": "data:;base64," + base64.b64encode(node_config).decode("ascii")}})
        config["storage"] = {"directories": [{"path": "/etc/pterodactyl", "mode": 0o700}]}
    if hostname:
        if len(hostname) > 253 or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                                      for label in hostname.split(".")):
            raise ValueError("Invalid hostname")
        files.append({"path": "/etc/hostname", "mode": 0o644,
                      "contents": {"source": "data:;base64," + base64.b64encode((hostname + "\n").encode()).decode("ascii")}})
    if files:
        config.setdefault("storage", {})["files"] = files
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-key", type=Path, action="append", required=True,
                        help="OpenSSH public-key file; repeat for multiple files")
    parser.add_argument("--node-config", type=Path, help="Optional Panel-generated YAML, embedded privately")
    parser.add_argument("--hostname")
    parser.add_argument("--profile-url", default=DEFAULT_URL, help="Hosted URL for these exact online.ign bytes")
    parser.add_argument("--output", type=Path, required=True, help="New private output file; existing files are never replaced")
    args = parser.parse_args()
    try:
        keys = [key for path in args.ssh_key for key in public_keys(path)]
        config = make_config(keys, args.profile_url, (HERE / "online.ign").read_bytes(),
                             args.node_config.read_bytes() if args.node_config else None, args.hostname)
        data = (json.dumps(config, indent=2) + "\n").encode()
        # O_EXCL also rejects existing symlinks; no output can accidentally replace another file.
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Created {args.output}; keep it private if it includes a node configuration.")


if __name__ == "__main__":
    main()
