"""Source rules for the translation UI: the QML must keep the promises SECURITY.md makes.

Run from the repository root:   python3 -m unittest discover -s tests -v
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class NothingLeaksToCommandLinesOrTmp(unittest.TestCase):
    def test_the_qml_hands_text_over_on_stdin(self):
        qml = (ROOT / "ui" / "ScribeTranslator.qml").read_text()
        self.assertGreaterEqual(qml.count("stdinEnabled"), 3)
        self.assertGreaterEqual(qml.count("write(input)"), 3)
        for command in re.findall(r"\.command\s*=\s*\[([^\]]*)\]", qml):
            self.assertNotIn("original", command)
            self.assertNotIn("word", command)

    def test_a_link_is_only_opened_after_its_scheme_was_checked(self):
        qml = (ROOT / "ui" / "ScribeTranslator.qml").read_text()
        self.assertIn("safeHref(e.href)", qml)
        self.assertRegex(qml, r"https\?:.*mailto:")
        self.assertEqual(qml.count('"xdg-open"'), 1)


class ReadingQuirks(unittest.TestCase):
    def test_a_sentence_the_reader_split_into_two_paragraphs_is_rejoined(self):
        """Slightly rotated text can start a new paragraph mid-sentence; the halves must not be
        translated apart (that turned 'keep bicycles in the shed and use the side' into nonsense)."""
        qml = (ROOT / "ui" / "ScribeTranslator.qml").read_text()
        body = qml.split("function paragraphs(words, lo, hi) {")[1].split("\n    }\n")[0]
        self.assertIn("(open && lower) ? \" \" : \"\\n\\n\"", body)

    def test_the_enable_card_and_the_settings_warn_that_offline_translation_can_be_wrong(self):
        text = (ROOT / "ui" / "ScribeStrings.qml").read_text()
        self.assertGreaterEqual(text.count("enableAcc:"), 2)
        self.assertGreaterEqual(text.count("offlineCaveat:"), 2)
        settings = (ROOT / "ui" / "ScribeSettings.qml").read_text()
        self.assertIn("ScribeStrings.s.enableAcc", settings)
        self.assertIn("ScribeStrings.s.offlineCaveat", settings)


class TranslationSettings(unittest.TestCase):
    def test_the_settings_panel_asks_before_enabling(self):
        qml = (ROOT / "ui" / "ScribeSettings.qml").read_text()
        self.assertIn("confirmEnable", qml)
        self.assertIn('changeCfg("translate", true)', qml)
        # the switch itself only opens the card, it never enables anything on its own
        self.assertIn("if (v) panel.showEnableCard()", qml)
        self.assertIn("confirmEnable = true;", qml.split("function showEnableCard()")[1].split("}")[0])

    def test_nothing_runs_while_translation_is_off(self):
        qml = (ROOT / "ui" / "ScribeTranslator.qml").read_text()
        self.assertIn("readonly property bool enabled: cfg.translate === true", qml)
        for guard in ("function start(text) {\n        if (!enabled) return;",
                      "if (!enabled || original.trim()", "if (!enabled || !cfg.dictionary",
                      "if (!enabled || installing) return;"):
            self.assertIn(guard, qml)


class SmartActionsAreIndependentOfTranslation(unittest.TestCase):
    """Links, e-mail, phone and IBAN buttons only need the local helper: no model, no network."""

    def test_finding_entities_is_not_gated_by_the_translation_switch(self):
        qml = (ROOT / "ui" / "ScribeTranslator.qml").read_text()
        prepare = qml.split("function prepare(text) {")[1].split("}")[0]
        self.assertNotIn("enabled", prepare)
        self.assertIn("findEntities()", prepare)

    def test_a_late_answer_is_matched_by_generation_not_by_status(self):
        """The answer arrives while the status is still idle (Translate was not pressed yet)."""
        qml = (ROOT / "ui" / "ScribeTranslator.qml").read_text()
        self.assertIn("entProc.gen === tr.gen", qml)
        self.assertNotIn('tr.status !== "idle") tr.entities', qml)

    def test_the_view_is_shown_without_translation_and_the_switch_is_in_behaviour(self):
        lens = (ROOT / "ui" / "ScribeLens.qml").read_text()
        view = lens.split("ScribeTranslateView {")[1].split("tr: win.tr")[0]
        self.assertIn('visible: win.phase === "result" && win.tr !== null\n', view)
        self.assertNotIn("enabled", view)
        settings = (ROOT / "ui" / "ScribeSettings.qml").read_text()
        self.assertLess(settings.index('key: "smartActions"'), settings.index("id: transBody"))

    def test_copying_a_number_closes_the_overlay_like_copying_text(self):
        lens = (ROOT / "ui" / "ScribeLens.qml").read_text()
        self.assertIn("onEntityCopied:", lens)
        self.assertIn("closeTimer.restart()", lens.split("onEntityCopied:")[1].split("\n")[0])


if __name__ == "__main__":
    unittest.main()
