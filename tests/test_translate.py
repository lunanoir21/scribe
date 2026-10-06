"""Tests for translate.py and the translation settings: no network, no model, no Quickshell.

Run from the repository root:   python3 -m unittest discover -s tests -v
No network, no model and no Quickshell are needed: downloads are replaced by fakes.
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import config  # noqa: E402
import translate  # noqa: E402


class Entities(unittest.TestCase):
    def kinds(self, text):
        return [(e["type"], e["value"]) for e in translate.find_entities(text)]

    def test_all_kinds_in_reading_order(self):
        t = ("Bak https://example.com/a?id=1. Mail: ali@site.org Tel: +90 532 123 45 67 "
             "IBAN: TR33 0006 1005 1978 6457 8413 26")
        self.assertEqual(self.kinds(t), [
            ("url", "https://example.com/a?id=1"), ("email", "ali@site.org"),
            ("phone", "+90 532 123 45 67"), ("iban", "TR330006100519786457841326")])

    def test_invalid_iban_is_not_reported(self):
        self.assertEqual(self.kinds("TR33 0006 1005 1978 6457 8413 27"), [])

    def test_digits_inside_an_iban_are_not_a_phone(self):
        kinds = [k for k, _ in self.kinds("TR33 0006 1005 1978 6457 8413 26")]
        self.assertNotIn("phone", kinds)

    def test_www_gets_an_https_href(self):
        self.assertEqual(translate.find_entities("www.example.org/x")[0]["href"],
                         "https://www.example.org/x")


class Masking(unittest.TestCase):
    def test_round_trip(self):
        t = "Visit https://example.com/x or write to a@b.co now."
        masked, values = translate.mask_entities(t)
        self.assertNotIn("example", masked)
        self.assertEqual(translate.unmask_entities(masked, values), t)

    def test_a_grammatical_suffix_survives(self):
        masked, values = translate.mask_entities("see https://a.io")
        self.assertEqual(translate.unmask_entities(masked + "'i", values), "see https://a.io'i")

    def test_an_unknown_placeholder_is_left_alone(self):
        self.assertEqual(translate.unmask_entities("X9X", ["a"]), "X9X")

    def test_text_without_entities_is_untouched(self):
        self.assertEqual(translate.mask_entities("plain text"), ("plain text", []))


class Language(unittest.TestCase):
    def test_english(self):
        self.assertEqual(translate.detect_lang("The compositor applies the layout when it is committed"), "en")

    def test_turkish(self):
        self.assertEqual(translate.detect_lang("Pencere yöneticisi yeni yerleşimi uygular"), "tr")

    def test_no_evidence_uses_the_default(self):
        self.assertIsNone(translate.detect_lang("xyz qrs", default=None))
        self.assertEqual(translate.detect_lang("xyz qrs"), "en")


class Pairs(unittest.TestCase):
    def cfg(self, **kw):
        return {"engine": "offline", "source": "auto", "target": "tr", "onlineEmail": "", **kw}

    def test_same_language_flips_the_target(self):
        en = "The layout is applied when the frame is committed"
        tr = "Yeni yerleşim bir sonraki karede uygulanır ve gösterilir"
        self.assertEqual(translate.resolve_pair(self.cfg(), en), ("en", "tr"))
        self.assertEqual(translate.resolve_pair(self.cfg(), tr), ("tr", "en"))

    def test_online_leaves_an_unknown_source_to_the_service(self):
        self.assertEqual(translate.resolve_pair(self.cfg(engine="online"), "zzz")[0], "auto")

    def test_chunks_respect_the_online_limit(self):
        text = " ".join(f"This is a sentence number {i}." for i in range(60))
        for chunk in translate._chunks(text, 450):
            self.assertLessEqual(len(chunk), 450)


class InstallIsPinnedAndVerified(unittest.TestCase):
    """What the offline pack installs cannot change underneath the user."""

    def test_packages_are_pinned_to_exact_versions(self):
        for req in translate.PIP_REQUIREMENTS:
            self.assertRegex(req, r"^[A-Za-z0-9_.-]+==\d+(\.\d+)*$")

    def test_models_are_https_on_the_allowed_host_with_a_checksum(self):
        for pair, spec in translate.MODELS_INDEX.items():
            self.assertRegex(pair, r"^[a-z]{2}-[a-z]{2}$")
            self.assertTrue(spec["url"].startswith("https://"))
            self.assertIn(spec["url"].split("/")[2], translate.ALLOWED_HOSTS)
            self.assertRegex(spec["sha256"], r"^[0-9a-f]{64}$")
            self.assertLess(spec["size"], translate.MAX_MODEL_BYTES)

    def test_redirects_may_only_stay_on_the_host_over_https(self):
        handler = translate._HttpsOnly()
        req = mock.Mock(full_url="https://argos-net.com/x")
        for bad in ("http://argos-net.com/x", "https://evil.example/x", "ftp://argos-net.com/x"):
            with self.assertRaises(urllib.error.URLError):
                handler.redirect_request(req, None, 302, "Found", {}, bad)

    def fake_opener(self, payload, length=None):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.headers = {"Content-Length": str(len(payload) if length is None else length)}
        stream = io.BytesIO(payload)
        response.read.side_effect = stream.read
        opener = mock.Mock()
        opener.open.return_value = response
        return opener

    def test_a_download_with_the_wrong_checksum_is_refused(self):
        payload = b"not the model"
        spec = {"url": "https://argos-net.com/m", "size": len(payload), "sha256": "0" * 64}
        with (
            tempfile.TemporaryDirectory() as d,
            mock.patch.dict(translate.MODELS_INDEX, {"aa-bb": spec}),
            mock.patch("urllib.request.build_opener", return_value=self.fake_opener(payload)),
            self.assertRaisesRegex(RuntimeError, "checksum"),
        ):
            translate._download_model("aa-bb", os.path.join(d, "m"), 0, lambda *a: None)

    def test_a_download_with_the_right_checksum_is_accepted(self):
        import hashlib
        payload = b"the model"
        spec = {"url": "https://argos-net.com/m", "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest()}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(translate.MODELS_INDEX, {"aa-bb": spec}), \
                mock.patch("urllib.request.build_opener", return_value=self.fake_opener(payload)):
            dest = os.path.join(d, "m")
            translate._download_model("aa-bb", dest, 0, lambda *a: None)
            self.assertEqual(Path(dest).read_bytes(), payload)

    def test_a_download_larger_than_the_cap_is_refused(self):
        spec = {"url": "https://argos-net.com/m", "size": 1, "sha256": "0" * 64}
        opener = self.fake_opener(b"x", length=translate.MAX_MODEL_BYTES + 1)
        with (
            tempfile.TemporaryDirectory() as d,
            mock.patch.dict(translate.MODELS_INDEX, {"aa-bb": spec}),
            mock.patch("urllib.request.build_opener", return_value=opener),
            self.assertRaisesRegex(RuntimeError, "larger"),
        ):
            translate._download_model("aa-bb", os.path.join(d, "m"), 0, lambda *a: None)

    def test_an_archive_cannot_write_outside_its_folder(self):
        with tempfile.TemporaryDirectory() as d:
            archive = os.path.join(d, "a.zip")
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("../evil.txt", "x")
            with self.assertRaisesRegex(RuntimeError, "escapes"):
                translate._safe_extract(archive, os.path.join(d, "out"))
            self.assertFalse(os.path.exists(os.path.join(d, "evil.txt")))

    def test_an_archive_that_unpacks_too_large_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            archive = os.path.join(d, "a.zip")
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("big.bin", b"0" * 4096)
            with mock.patch.object(translate, "MAX_UNPACKED_BYTES", 1024), \
                    self.assertRaisesRegex(RuntimeError, "more than expected"):
                translate._safe_extract(archive, os.path.join(d, "out"))

    def test_a_normal_archive_unpacks(self):
        with tempfile.TemporaryDirectory() as d:
            archive = os.path.join(d, "a.zip")
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("model/model.bin", b"1")
            translate._safe_extract(archive, os.path.join(d, "out"))
            self.assertTrue(os.path.exists(os.path.join(d, "out", "model", "model.bin")))


class NothingLeaksToCommandLinesOrTmp(unittest.TestCase):
    def test_text_is_not_a_command_line_option(self):
        for sub in ("translate", "lookup"):
            for flag in ("--text", "--word"):
                r = subprocess.run([sys.executable, "-I", str(ROOT / "translate.py"), sub, flag, "secret"],
                                   capture_output=True, text=True, check=False)
                self.assertEqual(r.returncode, 2, f"{sub} {flag}")

    def test_there_is_no_tmp_fallback(self):
        self.assertNotIn('"/tmp"', (ROOT / "translate.py").read_text())
        with mock.patch.object(translate, "RUNTIME_DIR", ""):
            self.assertFalse(translate.runtime_dir_ok())


class TranslationSettings(unittest.TestCase):
    def test_translation_is_off_until_the_user_switches_it_on(self):
        self.assertIs(config.DEFAULTS["translate"], False)
        self.assertIs(config.DEFAULTS["autoTranslate"], False)

    def test_values_are_validated(self):
        ok = config.clean({"translate": True, "tView": "inplace", "tEngine": "online", "tTarget": "de",
                           "tSource": "auto", "tEmail": "a@b.co", "smartActions": False})
        self.assertEqual(ok, {"translate": True, "tView": "inplace", "tEngine": "online", "tTarget": "de",
                              "tSource": "auto", "tEmail": "a@b.co", "smartActions": False})
        for bad in ({"tView": "wide"}, {"tEngine": "cloud"}, {"tTarget": "xx"}, {"tSource": "xx"},
                    {"tEmail": "a b"}, {"tEmail": "x" * 300}, {"translate": "yes"}):
            self.assertEqual(config.clean(bad), {}, bad)


if __name__ == "__main__":
    unittest.main()
