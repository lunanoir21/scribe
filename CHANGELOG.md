# Changelog

## 0.1.0

First release.

- Region picker on a frozen frame, with a sweeping scan line while the text is read.
- Lens-style result: the original text stays untouched, dragging over words draws a merged highlight per line, a floating toolbar copies the selection or selects everything.
- Parallel OCR: the crop is cut into strips at blank pixel rows and each strip is read by its own Tesseract process. Dark themes are inverted, small selections are read at 2x, a low-confidence read is retried once upscaled.
- Settings panel behind a gear in the bottom-right corner: reading languages, behaviour toggles, highlight colour.
- Language pack manager that detects the distro and installs through pacman, apt, dnf or apk (via `pkexec`), falling back to a direct `tessdata_fast` download into `~/.local/share/scribe/tessdata`.
- `install.sh` with `--patch` and `--uninstall`, backups and marker comments.
