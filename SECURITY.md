# Security

scribe is a screen reader: it takes a screenshot of one monitor, so it is treated as sensitive code.
This page says what it touches, what it never does, and how to report a problem.

## What it reads and writes

| What | Where | Notes |
|---|---|---|
| Screenshot of the focused monitor | `$XDG_RUNTIME_DIR/scribe/shot.png` | Directory mode `700`, file mode `600`, in RAM (tmpfs). Deleted when the overlay closes. There is deliberately no fallback to `/tmp`: without an owner-only runtime directory scribe refuses to run. |
| Temporary crops for tesseract | a private `tempfile` directory | Removed as soon as the read ends. |
| Settings | `~/.config/scribe/settings.json` | Mode `600`, atomic write. Only known keys with strict types and ranges are ever read or written. |
| Language packs you download | `~/.local/share/scribe/tessdata/` | Only when you press **Download directly**. |
| Offline translation pack | `~/.local/share/scribe-translate/` | Only after you turned translation on and pressed install: an isolated Python environment (pinned packages) and two models, about 470 MB. **Remove** in the settings panel deletes it. |
| Translation service socket | `$XDG_RUNTIME_DIR/scribe-translate.sock` | Mode `600`, only while the model is loaded (it quits after two idle minutes). No `/tmp` fallback: without an owner-only runtime directory the service does not start. |
| Clipboard | through `wl-copy` | Only the text you copy, handed to `wl-copy` on its **stdin**. It never appears on a command line, where other local users could read it (`/proc/<pid>/cmdline`). |

scribe never reads any other file of yours, never writes outside the places above, and `ocr.py` refuses to open an image that is not scribe's own screenshot.

## Network

With translation **off** (the default) the only network request scribe makes is the language pack download, and only when you ask for it:

- HTTPS only, to `github.com` / `raw.githubusercontent.com` (`tesseract-ocr/tessdata_fast`). Redirects to any other host or to plain HTTP are refused.
- 30 second timeout, a hard cap of 64 MiB, and a minimum size so an error page cannot pass as a language pack.
- The file is downloaded to a private temporary name and renamed into place only when complete.

Turning translation **on** (settings panel, behind a warning card) adds exactly these, each only when you ask for it:

- **Installing the offline pack.** Python packages from PyPI at pinned versions, installed as wheels only (`pip --only-binary=:all: --isolated`), so no `setup.py` runs. The two Argos Translate models from `argos-net.com` over HTTPS: one host, redirects to anything else refused, a 200 MiB cap, and the SHA-256 of each file is compared with the value in the code before anything is unpacked. A mismatch discards the download.
- **The online engine.** The text you translate is sent over HTTPS to `api.mymemory.translated.net`, and only after you chose **Send once** or **Always allow** (or set the engine to online and allowed it). Links, e-mail addresses and IBANs are replaced by placeholders first and never leave your computer. An optional e-mail from the settings is added to the request (it raises the service's daily quota) and is visible in the process list while the request runs.

Translated text and dictionary words are handed to `translate.py` on its stdin, never on a command line. The read text also goes to `translate.py entities` on stdin to find links, e-mail addresses, phone numbers and IBANs. That runs locally with no model and no network, **even when translation is off** (switch it off with **Smart actions** in the settings).

There is no telemetry, no update check and no account.

## Privileges

scribe never runs a privileged command. The translation pack installs into your own home directory and needs no root. For a package manager install it only **shows** the command (`sudo pacman -S ...` and equivalents) and offers to type it into **your** terminal, where you enter the password. Nothing is piped to a shell, nothing is downloaded and executed.

## Resource limits

Every stage that handles unbounded data has a limit, so a huge selection or a hostile image cannot exhaust memory:

- the selection is capped at 36 megapixels and the image decoder at 120 megapixels;
- every tesseract run has a 60 second timeout, and the whole read has a 90 second watchdog in the shell;
- at most 4000 words are returned, each at most 120 characters, control characters stripped;
- the output of `scribe.sh read` is cut at 4 MiB before the shell collects it (`StdioCollector` has no limit of its own), and every other helper prints a few lines;
- a cancelled or timed-out read is stopped, and its late output is ignored;
- translation input is cut at 256 KiB, a word lookup at 80 characters, a model download at 200 MiB and an unpacked model at 400 MiB, and the translation service unloads the model after two idle minutes.

## Inputs

Language codes, output names, settings and key specs are validated before they reach a command line: language codes must match `^[a-z]{2,3}(_[a-z]{2,8})?$`, output names `^[A-Za-z0-9._:-]{1,64}$`, the installer's `--key` only letters, digits, space, comma, `+` and `_`. Commands are always argument lists, never shell strings, and no shell is started anywhere in the QML code. Text that came from the screen is never part of a command line. The only program besides `notify-send` that the QML starts is `xdg-open`, for a link or an e-mail address found in the text, and only after its scheme was checked (`http://`, `https://` or `mailto:`, no whitespace or control characters, so it can neither become an option nor another scheme).

## Developer helpers

The `devopen`, `devchoose`, `devdrag`, `devread`, `test` and `testsel` IPC functions only answer while the file `$XDG_RUNTIME_DIR/scribe-dev` exists. They are meant for documentation screenshots and are inert otherwise.

## Tests

`python3 -m unittest discover -s tests` checks the validation rules, the translation helper (entity detection, pinned and verified downloads, unpack guards, text on stdin only, nothing running while translation is off), the file modes, the installer (patch, re-run, uninstall, refusing to delete a folder that is not a scribe install) and a few source rules (no `shell=True`, no download-and-execute, a timeout on every tesseract run, a size cap on every download). CI also runs `ruff` and `shellcheck`.

## Reporting

Please open a private security advisory on GitHub (**Security > Report a vulnerability**) rather than a public issue. You will get an answer within a week.
