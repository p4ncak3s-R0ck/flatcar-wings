"""Installer control-flow tests in a disposable fake host; no real systemd/Docker.

Run: python3 -m unittest discover -s tests -v
All host paths in a COPY of the installer are redirected below TemporaryDirectory.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


BUNDLE = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="coreos-wings-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        shutil.copytree(BUNDLE, self.bundle, ignore=shutil.ignore_patterns("tests"))
        script = (self.bundle / "install.sh").read_text()
        script = re.sub(r"/(?:etc|var|run|tmp)/", lambda match: str(self.root) + match[0], script)
        script = script.replace("[[ $EUID == 0 ]]", "[[ 1 == 1 ]]")
        (self.bundle / "install.sh").write_text(script)
        for directory in ("etc/systemd/system", "run", "mockbin"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "etc/os-release").write_text("ID=fedora\nVARIANT_ID=coreos\n")
        self.payload = self.root / "payload"
        self.payload.write_text("#!/usr/bin/env bash\n[[ ${1:-} == version ]]\n")
        self.payload.chmod(0o755)
        self.digest = hashlib.sha256(self.payload.read_bytes()).hexdigest()
        mocks = {
            "curl": '#!/bin/bash\nwhile (($#)); do if [[ $1 == --output ]]; then cp "$PAYLOAD" "$2"; exit; fi; shift; done\nexit 1\n',
            "getenforce": "#!/bin/bash\necho Enforcing\n",
            "chcon": "#!/bin/bash\nexit 0\n",
            "chown": "#!/bin/bash\nexit 0\n",
            "sleep": "#!/bin/bash\nexit 0\n",
            "systemctl": '''#!/bin/bash
case "$1" in
    cat|daemon-reload|enable) exit 0 ;;
    restart) [[ ! -e "$FAKE_HOST/fail-start" ]] ;;
    is-active) [[ ! -e "$FAKE_HOST/fail-start" ]] ;;
    start|stop) exit 0 ;;
    *) exit 1 ;;
esac
''',
        }
        for name, data in mocks.items():
            executable = self.root / "mockbin" / name
            executable.write_text(data)
            executable.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root / "mockbin") + os.pathsep + os.environ["PATH"],
                        FAKE_HOST=str(self.root), PAYLOAD=str(self.payload))

    def run_install(self, *args):
        return subprocess.run(["bash", str(self.bundle / "install.sh"), *args],
                              env=self.env, text=True, capture_output=True)

    def install(self, *args):
        return self.run_install("--sha256", self.digest, *args)

    def test_stages_without_configuration(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "var/opt/coreos-wings/bin/wings").read_bytes(), self.payload.read_bytes())
        self.assertFalse((self.root / "etc/pterodactyl/config.yml").exists())
        self.assertIn("Installed. Save", result.stdout)

    def test_bad_checksum_preserves_installed_binary(self):
        self.assertEqual(self.install().returncode, 0)
        binary = self.root / "var/opt/coreos-wings/bin/wings"
        before = binary.read_bytes()
        self.payload.write_text("untrusted replacement")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum verification failed", result.stderr)
        self.assertEqual(binary.read_bytes(), before)

    def test_config_is_private_and_never_silently_replaced(self):
        config = self.root / "node.yml"
        config.write_text("token: fixture\n")
        result = self.install("--config", str(config))
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.root / "etc/pterodactyl/config.yml"
        self.assertEqual(installed.stat().st_mode & 0o777, 0o600)
        config.write_text("token: other-fixture\n")
        result = self.install("--config", str(config))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(installed.read_text(), "token: fixture\n")

    def test_early_start_failure_restores_previous_binary(self):
        self.assertEqual(self.install().returncode, 0)
        binary = self.root / "var/opt/coreos-wings/bin/wings"
        old = binary.read_bytes()
        config = self.root / "etc/pterodactyl/config.yml"
        config.write_text("token: fixture\n")
        self.payload.write_text("#!/usr/bin/env bash\n# new version\n[[ ${1:-} == version ]]\n")
        self.digest = hashlib.sha256(self.payload.read_bytes()).hexdigest()
        (self.root / "fail-start").touch()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Restored the previous binary", result.stderr)
        self.assertEqual(binary.read_bytes(), old)

    def test_refuses_unmanaged_service(self):
        (self.root / "etc/systemd/system/wings.service").write_text("# operator owned\n")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unmanaged wings.service", result.stderr)

    def test_refuses_non_coreos(self):
        (self.root / "etc/os-release").write_text("ID=debian\n")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "var/opt/coreos-wings").exists())

    def test_refuses_version_path_injection(self):
        result = self.run_install("--version", "../../other-project")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "var/opt/coreos-wings").exists())

    def run_prepare(self, path):
        labels = self.root / "label-paths"
        labels.write_text(str(path) + "\n")
        script = (BUNDLE / "prepare.sh").read_text()
        script = script.replace("/var/opt/coreos-wings/bin/wings", str(self.payload))
        script = script.replace("/etc/pterodactyl/coreos-label-paths", str(labels))
        prepare = self.root / "prepare.sh"
        prepare.write_text(script)
        return subprocess.run(["bash", str(prepare)], env=self.env, text=True, capture_output=True)

    def test_prepare_creates_dedicated_data_directory(self):
        data = self.root / "game-data"
        result = self.run_prepare(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(data.is_dir())

    def test_prepare_rejects_symlink_root(self):
        target = self.root / "target"
        target.mkdir()
        link = self.root / "game-link"
        link.symlink_to(target, target_is_directory=True)
        result = self.run_prepare(link)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a symlink", result.stderr)

    def test_prepare_rejects_broad_and_traversal_paths(self):
        for path in ("/var/lib", "/", "/tmp/../etc"):
            with self.subTest(path=path):
                self.assertNotEqual(self.run_prepare(path).returncode, 0)


if __name__ == "__main__":
    unittest.main()
