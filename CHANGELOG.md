# Changelog

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
