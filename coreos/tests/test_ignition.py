"""Credential boundaries and integrity checks for online provisioning."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

COREOS = Path(__file__).resolve().parents[1]
IGNITION = COREOS / "ignition"
spec = importlib.util.spec_from_file_location("make_host", IGNITION / "make-host.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def public_key():
    def field(value):
        return struct.pack(">I", len(value)) + value
    blob = field(b"ssh-ed25519") + field(bytes(range(32)))
    return "ssh-ed25519 " + base64.b64encode(blob).decode() + " test-fixture"


class IgnitionTests(unittest.TestCase):
    def test_generated_profile_is_current_and_checksum_matches(self):
        result = subprocess.run(["python3", str(IGNITION / "build.py"), "--check"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = hashlib.sha256((IGNITION / "online.ign").read_bytes()).hexdigest()
        self.assertEqual((IGNITION / "online.ign.sha256").read_text(), expected + "  online.ign\n")

    def test_public_profile_embeds_only_integration_files(self):
        profile = json.loads((IGNITION / "online.ign").read_bytes())
        self.assertNotIn("passwd", profile)
        self.assertNotIn("disks", profile["storage"])
        files = profile["storage"]["files"]
        self.assertEqual(len(files), 4)
        for file in files:
            name = Path(file["path"]).name
            self.assertIn(name, {"install.sh", "prepare.sh", "check.sh", "wings.service"})
            encoded = file["contents"]["source"].split(",", 1)[1]
            self.assertEqual(base64.b64decode(encoded), (COREOS / name).read_bytes())

    def test_host_pins_remote_profile_and_keeps_node_config_private(self):
        profile = (IGNITION / "online.ign").read_bytes()
        private = b"token: fixture-only\n"
        config = host.make_config([public_key()], host.DEFAULT_URL, profile, private, "wings-01")
        merge = config["ignition"]["config"]["merge"][0]
        self.assertEqual(merge["verification"]["hash"], "sha256-" + hashlib.sha256(profile).hexdigest())
        node = next(item for item in config["storage"]["files"] if item["path"].endswith("config.yml"))
        self.assertEqual(node["mode"], 0o600)
        self.assertEqual(base64.b64decode(node["contents"]["source"].split(",", 1)[1]), private)

    def test_requires_https_and_valid_hostname(self):
        for url in ("http://example.com/online.ign", "https://user:password@example.com/online.ign", "file:///profile"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                host.make_config([public_key()], url, b"{}")
        with self.assertRaises(ValueError):
            host.make_config([public_key()], host.DEFAULT_URL, b"{}", hostname="../node")

    def test_cli_refuses_private_keys_and_does_not_overwrite_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "key.pub"
            output = root / "host.ign"
            key.write_text(public_key() + "\n")
            command = ["python3", str(IGNITION / "make-host.py"), "--ssh-key", str(key), "--output", str(output)]
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            before = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), before)
            output.unlink()
            key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n")
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
