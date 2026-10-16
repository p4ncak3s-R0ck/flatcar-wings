#!/usr/bin/env python3
"""Build the credential-free, architecture-independent public Ignition profile."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
COREOS = HERE.parent
STAGING = "/var/opt/coreos-wings/provisioning"


def resource(data):
    return {"source": "data:;base64," + base64.b64encode(data).decode("ascii")}


def profile():
    files = []
    for name in ("install.sh", "prepare.sh", "check.sh", "wings.service"):
        files.append({"path": f"{STAGING}/{name}", "mode": 0o644,
                      "contents": resource((COREOS / name).read_bytes())})
    return {
        "ignition": {"version": "3.4.0"},
        "storage": {
            "directories": [{"path": STAGING, "mode": 0o755}],
            "files": files,
        },
        "systemd": {"units": [
            {"name": "docker.service", "enabled": True},
            {"name": "coreos-wings-install.service", "enabled": True,
             "contents": (HERE / "coreos-wings-install.service").read_text()},
        ]},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated files are stale; do not write")
    args = parser.parse_args()
    data = (json.dumps(profile(), indent=2) + "\n").encode()
    digest = hashlib.sha256(data).hexdigest()
    outputs = {HERE / "online.ign": data,
               HERE / "online.ign.sha256": f"{digest}  online.ign\n".encode()}
    for path, contents in outputs.items():
        if args.check:
            if not path.exists() or path.read_bytes() != contents:
                parser.exit(1, f"Stale profile: {path.name}; run python3 coreos/ignition/build.py\n")
        else:
            path.write_bytes(contents)
    print(f"sha256-{digest}")


if __name__ == "__main__":
    main()
