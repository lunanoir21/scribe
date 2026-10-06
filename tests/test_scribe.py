"""Tests for scribe: input validation, safety limits, the installer and a few source rules.

Run from the repository root:   python3 -m unittest discover -s tests -v
Needs only numpy and pillow (ocr.py imports them); tesseract, grim and Quickshell are not needed.
"""
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import config  # noqa: E402
import langs  # noqa: E402
import numpy as np  # noqa: E402
import ocr  # noqa: E402


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kw)


class ConfigTests(unittest.TestCase):
    def test_unknown_keys_and_bad_values_are_dropped(self):
        out = config.clean({
            "langs": "deu+eng", "highlight": "#ffffff", "ui": "tr", "minConfidence": 70,
            "autoCopy": True, "evil": "x",
        })
        self.assertEqual(out["langs"], "deu+eng")
        self.assertNotIn("evil", out)
        for bad in ({"langs": "x;rm -rf /"}, {"langs": "tur+"}, {"highlight": "red"},
                    {"highlight": "#12345"}, {"ui": "de"}, {"minConfidence": 500},
                    {"minConfidence": True}, {"autoCopy": "yes"}, {"langs": 5}):
            self.assertEqual(config.clean(bad), {}, bad)
        self.assertEqual(config.clean("not a dict"), {})

    def test_write_is_private_atomic_and_merged(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": home}):
            merged = config.save({"ui": "en", "highlight": "#8ab4f8", "bogus": 1})
            self.assertEqual(merged["ui"], "en")
            path = Path(config.config_path())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            config.save({"langs": "tur"})                       # a second write keeps the first
            self.assertEqual(json.loads(path.read_text())["ui"], "en")
            self.assertEqual([p.name for p in path.parent.iterdir()], ["settings.json"])  # no temp files

    def test_symlinked_settings_dir_is_refused(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": home}):
            target = Path(home) / "elsewhere"
            target.mkdir()
            os.symlink(target, Path(home) / "scribe")
            with self.assertRaises(OSError):
                config.save({"ui": "en"})

    def test_oversized_or_symlinked_file_reads_as_defaults(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": home}):
            d = Path(home) / "scribe"
            d.mkdir()
            (d / "settings.json").write_text(json.dumps({"ui": "tr"}) + " " * (config.MAX_FILE_BYTES + 1))
            self.assertEqual(config.load(), {})


class LangTests(unittest.TestCase):
    def test_code_validation(self):
        for good in ("tur", "eng", "chi_sim", "ab"):
            self.assertTrue(langs.valid_code(good), good)
        for bad in ("", "TUR", "tu1", "../etc", "tur;ls", "a" * 20, "tur+eng", None, 5, "chi_"):
            self.assertFalse(langs.valid_code(bad), bad)

    def test_package_commands(self):
        cases = {
            "arch": "sudo pacman -S --needed tesseract-data-deu",
            "debian": "sudo apt-get install -y tesseract-ocr-deu",
            "fedora": "sudo dnf install -y tesseract-langpack-deu",
            "alpine": "sudo apk add tesseract-ocr-data-deu",
        }
        for fam, expected in cases.items():
            with mock.patch.object(langs, "family", return_value=fam):
                self.assertEqual(langs.pm_command("deu"), expected)
        with mock.patch.object(langs, "family", return_value="debian"):
            self.assertEqual(langs.pm_command("chi_sim"), "sudo apt-get install -y tesseract-ocr-chi-sim")
        with mock.patch.object(langs, "family", return_value=None):
            self.assertIsNone(langs.pm_command("deu"))
        with mock.patch.object(langs, "family", return_value="arch"):
            self.assertIsNone(langs.pm_command("deu; rm -rf ~"))

    def test_redirects_stay_on_https_github(self):
        handler = langs._HttpsOnly()
        req = mock.Mock()
        for url in ("http://raw.githubusercontent.com/x", "https://evil.example/x",
                    "https://github.com.evil.example/x", "file:///etc/passwd"):
            with self.assertRaises(urllib.error.URLError, msg=url):
                handler.redirect_request(req, None, 302, "Found", {}, url)

    def test_messages_exist_in_both_languages(self):
        for key, texts in langs.MESSAGES.items():
            self.assertEqual(set(texts), {"tr", "en"}, key)


class OcrTests(unittest.TestCase):
    def test_region_validation(self):
        self.assertIsNotNone(ocr.parse_region(["10", "20", "300", "100", "1"]))
        for bad in (["nan", "0", "10", "10", "1"], ["0", "0", "0", "10", "1"], ["0", "0", "10", "10", "99"],
                    ["x", "0", "10", "10", "1"], ["0", "0", "inf", "10", "1"]):
            self.assertIsNone(ocr.parse_region(bad), bad)

    def test_only_the_private_screenshot_is_readable(self):
        with tempfile.TemporaryDirectory() as rt:
            private = Path(rt) / "scribe"
            private.mkdir()
            shot = private / "shot.png"
            shot.write_bytes(b"x")
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": rt}, clear=False):
                os.environ.pop("SCRIBE_DEV", None)
                self.assertTrue(ocr.allowed_image(str(shot)))
                self.assertFalse(ocr.allowed_image("/etc/passwd"))
                self.assertFalse(ocr.allowed_image(str(private / ".." / "other.png")))
                link = private / "link.png"
                os.symlink("/etc/passwd", link)
                self.assertFalse(ocr.allowed_image(str(link)))      # a symlink out of the dir is refused

    def test_strips_are_cut_at_blank_rows(self):
        img = np.full((600, 200), 255, dtype=np.uint8)
        for top in (20, 140, 260, 380, 500):                         # five "text lines"
            img[top:top + 40, 10:190] = 0
        cuts = ocr.split_rows(img, 3)
        self.assertEqual(cuts[0], 0)
        self.assertEqual(cuts[-1], 600)
        for cut in cuts[1:-1]:
            self.assertTrue((img[cut] == 255).all(), f"cut at {cut} goes through text")
        self.assertEqual(ocr.split_rows(img, 1), [0, 600])

    def test_word_text_is_sanitised(self):
        self.assertEqual(ocr.clean_word("he\x00llo\t\n"), "hello")
        self.assertEqual(len(ocr.clean_word("a" * 1000)), ocr.MAX_WORD_CHARS)


class ScriptTests(unittest.TestCase):
    def sh(self, *args, rt):
        env = {"PATH": os.environ["PATH"], "XDG_RUNTIME_DIR": rt} if rt else {"PATH": os.environ["PATH"]}
        return run(["bash", str(ROOT / "scribe.sh"), *args], env=env)

    def test_refuses_to_run_without_a_private_runtime_dir(self):
        r = self.sh("clean", rt=None)
        self.assertEqual(r.returncode, 70)
        self.assertIn("norundir", r.stdout)

    def test_runtime_dir_is_created_private(self):
        with tempfile.TemporaryDirectory() as rt:
            self.assertEqual(self.sh("clean", rt=rt).returncode, 0)
            self.assertEqual(stat.S_IMODE((Path(rt) / "scribe").stat().st_mode), 0o700)

    def test_loose_old_directory_is_tightened(self):
        with tempfile.TemporaryDirectory() as rt:
            d = Path(rt) / "scribe"
            d.mkdir(mode=0o755)
            d.chmod(0o755)
            self.sh("clean", rt=rt)
            self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700)

    def test_output_names_are_validated(self):
        with tempfile.TemporaryDirectory() as rt:
            for bad in ("; touch pwned", "$(id)", "a b", "../x", "x" * 80):
                r = self.sh("shot", bad, rt=rt)
                self.assertEqual(r.returncode, 64, bad)
                self.assertIn("badoutput", r.stdout)

    def test_clean_removes_only_its_own_files(self):
        with tempfile.TemporaryDirectory() as rt:
            d = Path(rt) / "scribe"
            d.mkdir(mode=0o700)
            for name in ("shot.png", "crop.png", "prep.png", "keep.txt"):
                (d / name).write_text("x")
            self.sh("clean", rt=rt)
            self.assertEqual(sorted(p.name for p in d.iterdir()), ["keep.txt"])

    def test_read_needs_all_arguments(self):
        with tempfile.TemporaryDirectory() as rt:
            self.assertEqual(self.sh("read", "a", "b", rt=rt).returncode, 64)


class InstallerTests(unittest.TestCase):
    def test_patch_rerun_and_uninstall_restore_the_originals(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            shell, hypr = t / "qs" / "Shell.qml", t / "hyprland.conf"
            shell.parent.mkdir()
            shell.write_text('import QtQuick\nimport Quickshell\n\nShellRoot {\n    Main {}\n}\n')
            hypr.write_text("# mine\nbind = SUPER, Q, killactive\n")
            before = (shell.read_text(), hypr.read_text())
            base = ["bash", str(ROOT / "install.sh"), "--dest", str(t / "qs" / "vendor"), "--shell", str(shell),
                    "--hypr", str(hypr), "--no-deps-check"]
            self.assertEqual(run(base + ["--patch"]).returncode, 0)
            self.assertIn("ScribeHost", shell.read_text())
            self.assertIn("ipc call scribe start", hypr.read_text())
            self.assertTrue((t / "qs" / "vendor" / "scribe" / "ui" / "ScribeHost.qml").is_file())
            self.assertTrue((t / "qs" / "vendor" / "scribe" / "config.py").is_file())
            run(base + ["--patch"])                                  # idempotent
            self.assertEqual(shell.read_text().count("ScribeHost"), 1)
            self.assertEqual(hypr.read_text().count("ipc call scribe start"), 1)
            self.assertEqual(run(base + ["--uninstall"]).returncode, 0)
            self.assertEqual((shell.read_text(), hypr.read_text()), before)
            self.assertFalse((t / "qs" / "vendor" / "scribe").exists())

    def test_uninstall_refuses_folders_that_are_not_a_scribe_install(self):
        with tempfile.TemporaryDirectory() as t:
            victim = Path(t) / "other" / "scribe"
            victim.mkdir(parents=True)
            (victim / "important.txt").write_text("keep")
            r = run(["bash", str(ROOT / "install.sh"), "--dest", str(victim.parent), "--shell", str(Path(t) / "none.qml"),
                     "--hypr", str(Path(t) / "none.conf"), "--uninstall"])
            self.assertEqual(r.returncode, 0)
            self.assertTrue((victim / "important.txt").exists())

    def test_key_spec_cannot_inject_lines(self):
        r = run(["bash", str(ROOT / "install.sh"), "--no-deps-check", "--key", "SUPER, T\nexec = evil"])
        self.assertEqual(r.returncode, 64)


class SourceRuleTests(unittest.TestCase):
    """Cheap guards for the things reviewers look for first."""

    def files(self, *suffixes):
        for p in ROOT.rglob("*"):
            if p.is_file() and p.suffix in suffixes and ".git" not in p.parts and "tests" not in p.parts:
                yield p

    def test_no_shell_strings_or_eval_in_python(self):
        for p in self.files(".py"):
            text = p.read_text()
            for pattern in (r"shell\s*=\s*True", r"os\.system\(", r"\beval\(", r"\bexec\(", r"pickle\.loads?\(",
                            r"os\.popen\("):
                self.assertIsNone(re.search(pattern, text), f"{p.name}: {pattern}")

    def test_no_download_and_execute(self):
        for p in self.files(".py", ".sh", ".qml"):
            text = p.read_text()
            self.assertIsNone(re.search(r"\b(curl|wget)\b[^\n]*\|\s*(ba)?sh", text), p.name)
            self.assertNotIn("XMLHttpRequest", text, p.name)
            self.assertNotIn("openUrlExternally", text, p.name)

    def test_qml_runs_only_expected_programs(self):
        allowed_sh_c = 0              # no QML code runs a shell at all
        count = 0
        for p in self.files(".qml"):
            text = p.read_text()
            count += len(re.findall(r'\["sh",\s*"-c"', text))
            for call in re.findall(r"execDetached\(\[([^\]]*)\]", text):
                self.assertTrue(call.strip().startswith('"notify-send"'), f"{p.name}: {call}")
        self.assertLessEqual(count, allowed_sh_c)

    def test_copied_text_never_reaches_a_command_line(self):
        """Screen text must go to wl-copy through stdin: arguments are readable by other users."""
        host = (ROOT / "ui" / "ScribeHost.qml").read_text()
        self.assertIn('command: ["wl-copy"]', host)
        self.assertIn("stdinEnabled", host)
        self.assertIn("write(host.pendingCopy)", host)
        self.assertNotIn("printf", host)
        for p in self.files(".qml"):
            for command in re.findall(r"\.command\s*=\s*\[([^\]]*)\]", p.read_text()):
                self.assertNotIn("text", command.replace("context", ""), f"{p.name}: {command}")

    def test_every_tesseract_run_has_a_timeout_and_every_download_a_size_cap(self):
        self.assertIn("timeout=STRIP_TIMEOUT", (ROOT / "ocr.py").read_text())
        self.assertIn("MAX_BYTES", (ROOT / "langs.py").read_text())

    def test_strings_exist_in_both_languages(self):
        text = (ROOT / "ui" / "ScribeStrings.qml").read_text()
        tr_block = text.split("readonly property var tr:")[1].split("readonly property var en:")[0]
        en_block = text.split("readonly property var en:")[1]
        key = re.compile(r"^\s{8}([A-Za-z_]+):", re.M)
        self.assertEqual(sorted(key.findall(tr_block)), sorted(key.findall(en_block)))

    def test_no_claude_attribution_or_agent_files_in_the_repo(self):
        self.assertFalse((ROOT / "AGENTS.md").exists())
        self.assertFalse((ROOT / "CLAUDE.md").exists())


if __name__ == "__main__":
    unittest.main()
