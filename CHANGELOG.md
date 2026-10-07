# Changelog

## Unreleased

**New: scan animation**
- Pick the animation shown while a region is being read, in the settings panel (**Scan animation**): **Line** (the old sweep, still the default), **Row by row**, **Shine**, **Pixels**, **Outline** or **Focus**. A small preview plays in the panel, and picking one replays it over the region on screen. New settings key `scanAnim`, validated by `config.py`.

## 0.3.0

Translation, a dictionary, smart actions, and better reading of hard backgrounds.

**New: translation (off by default)**
- Switch it on in the settings panel (**Translation > Enable translation**). A card says what it will do first: the one-time download, what is sent where, memory and disk use. While it is off nothing is downloaded, loaded or sent for translation, and the **Translate** button does not exist.
- **Translate** button under the read region, and in the selection toolbar to translate only the selected words. Optional **Translate right after reading**.
- Two views, picked in settings: **Card** (original and translation side by side, the original is editable and the translation refreshes after you stop typing) and **In place** (the translation painted over the text, sized to fit, with a bar to switch to the original, copy, or edit).
- **Dictionary:** hover a word while a translation is open for its translation and alternatives. Click the bubble to copy.
- **Smart actions:** links, e-mail addresses, phone numbers and IBANs found in the text become buttons under the read region, with or without translation (a **Smart actions** switch under Behaviour, on by default). Links and e-mail open (only `http(s)` and `mailto:`, checked again before `xdg-open` runs), phone numbers and IBANs are copied with one click and scribe closes afterwards like after **Copy**. IBANs are validated with their mod 97 checksum. In a translation they are kept out of the text. Finding them only runs a small local helper: no model and no network.
- **Offline engine** (English ↔ Turkish): CTranslate2 with Argos Translate models in an isolated environment under `~/.local/share/scribe-translate`. Installed, reinstalled and removed from the settings panel. The model is loaded when you press Translate and released after two idle minutes, so nothing stays in memory otherwise.
- **Online engine** through MyMemory, any language pair. scribe asks before the text leaves your computer: **Send once**, **Always allow** or **Cancel**.
- New helper `translate.py`. It takes text on **stdin only** (never a command line argument) and answers with one line of JSON.
- New settings keys: `translate`, `autoTranslate`, `tView`, `tEngine`, `tTarget`, `tSource`, `tOnline`, `tEmail`, `smartActions`, `dictionary`, `editable`. Everything is validated by `config.py` like the existing keys.
- A documentation page on the website, in English and Turkish.

**Honesty about quality**
- The settings panel and the card shown before translation is enabled now say that offline translation is a small model and can be wrong (it may take a word for the subject or leave it untranslated), with a real example.
- A sentence that the reader split into two paragraphs (slightly rotated text) is rejoined before it is translated.
- A measured **Accuracy** section on the documentation page: character and word accuracy of the reader for 11 fonts, 9 colour schemes and 3 sizes (792 runs), for images damaged like a photo, for tilted text and for two sample photos, with the weak spots stated plainly (tilted text and strong uneven light). `tools/accuracy.py`, `tools/sample_photos.py` and `tools/translation_check.py` reproduce every number; links, e-mail addresses, phone numbers and IBANs came through translation unchanged 104 times out of 104.

**Security**
- The offline pack is pinned: exact package versions installed as wheels only (`--only-binary`, `--isolated`), models from one host over HTTPS with a hard size cap and a SHA-256 that must match, archives unpacked only after every entry was checked (no path escape, no unpack bomb).
- The translation service listens on a socket in `$XDG_RUNTIME_DIR` (mode 600). Like the screenshot there is no `/tmp` fallback.
- `SECURITY.md` now lists what changes when translation is on: the network requests, the new directory, the service socket and the one extra program the QML starts (`xdg-open`).
- New tests (`tests/test_translate.py`) cover the entity detection, the pinning and verification of downloads, the unpack guards, the stdin rule and the "off means off" guards.

**Reading**
- `ocr.py` reads hard crops (gradients, busy backgrounds, huge or script type, mixed light and dark text) with extra passes at two scales and both polarities, and keeps the fast single pass for plain pages.

**Installer**
- `install.sh` also installs `translate.py`.

## 0.2.1

- **Privacy fix:** the Copy path handed the recognised screen text to `sh -c 'printf %s "$1" | wl-copy'` as a command-line argument, which other local users can read from `/proc/<pid>/cmdline`. The text now goes to `wl-copy` through its stdin only, and no shell is started at all. A test fails if screen text ever reaches a command line again. (Thanks to the marketplace reviewer who traced this.)

## 0.2.0

Security and robustness review, English interface, real screenshots.

**New**
- English and Turkish interface. The `ui` setting is `auto` (follows `$LANG`), `tr` or `en`, and the settings panel has a selector. The helper scripts speak the same language.
- `SECURITY.md`, a unit test suite (27 tests) and CI (`ruff`, `shellcheck`, tests).
- Screenshots of the real overlay on the Hyprland Wikipedia article, in both languages. The website swaps them when you change language (`?lang=en` / `?lang=tr` also works).
- `scribe.sh check` and a start-up dependency check: a missing `grim`, `wl-copy`, `tesseract`, `python-numpy` or `python-pillow` is reported by name instead of failing silently.

**Security and memory**
- Settings moved to `~/.config/scribe/settings.json`, written by `config.py` (strict keys, types and ranges, mode 600, atomic rename). The module folder is never written to.
- The screenshot lives only in `$XDG_RUNTIME_DIR/scribe` (mode 700, enforced even on a directory an older version created), is deleted when the overlay closes, and there is no `/tmp` fallback.
- `ocr.py` only opens scribe's own screenshot, caps the selection (36 MP) and the decoder (120 MP), times every tesseract run out (60 s), returns at most 4000 words of at most 120 sanitised characters, and `scribe.sh read` cuts its output at 4 MiB.
- Language downloads: HTTPS and GitHub hosts only (redirects included), 64 MiB cap, minimum size, private temp file renamed into place.
- The package manager path no longer exists in the code: scribe only shows the command or types it into your terminal. `install --pm` and `pkexec` are gone.
- `install.sh` validates `--key`, refuses to delete a folder that is not a scribe install, and keeps working in locales where `[A-Z]` is not plain ASCII (it failed with `LANG=tr_TR`).
- Developer IPC helpers answer only while `$XDG_RUNTIME_DIR/scribe-dev` exists.

**Fixed**
- A read cancelled with Esc could finish later and bring the overlay back. Cancel now stops the process and late output is ignored; a read that never ends is cancelled after 90 s.
- The install-method card could still be open the next time the overlay was shown.
- English strings no longer clip in the install card.

## 0.1.1

- Installing a language no longer asks for a password behind your back. The **Download** button opens a card with two options: download directly (no password), or install with the package manager, which shows the command with **Copy command** and **Run in terminal** buttons.
- `langs.py`: `install` is a direct download by default, `--pm` keeps the `pkexec` route, new `command` and `term` subcommands.

## 0.1.0

First release.

- Region picker on a frozen frame, with a sweeping scan line while the text is read.
- Lens-style result: the original text stays untouched, dragging over words draws a merged highlight per line, a floating toolbar copies the selection or selects everything.
- Parallel OCR: the crop is cut into strips at blank pixel rows and each strip is read by its own Tesseract process. Dark themes are inverted, small selections are read at 2x, a low-confidence read is retried once upscaled.
- Settings panel behind a gear in the bottom-right corner: reading languages, behaviour toggles, highlight colour.
- Language pack manager that detects the distro and installs through pacman, apt, dnf or apk (via `pkexec`), falling back to a direct `tessdata_fast` download into `~/.local/share/scribe/tessdata`.
- `install.sh` with `--patch` and `--uninstall`, backups and marker comments.
