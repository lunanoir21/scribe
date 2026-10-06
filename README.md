# scribe

Select and copy text from anywhere on your screen, the way Google Lens does it. A Quickshell module for Hyprland.

[Website](https://lunanoir21.github.io/scribe/) · [Türkçe](README.tr.md) · [Changelog](CHANGELOG.md)

Press a key, drag a box around any text (a video, an image, a PDF, a terminal, a locked-down app) and scribe reads it. The text stays exactly where it is on screen. Drag over it to select, then press **Copy** in the small toolbar that appears above the selection.

## Screenshots

Captured on an empty workspace with a clean Firefox profile, reading the Hyprland article on Wikipedia.

![](docs/assets/en/03-select-text.webp)

| | |
|---|---|
| ![](docs/assets/en/01-select.webp) | ![](docs/assets/en/02-scan.webp) |
| ![](docs/assets/en/04-settings.webp) | ![](docs/assets/en/05-install-options.webp) |

## Features

- **Lens-style selection.** Your original text is left untouched. Dragging over words draws a translucent highlight per line, like selecting real text.
- **Fast.** The selection is cut into strips at blank rows and the strips are read by parallel Tesseract processes. A 1000×600 region takes about 0.6 s, a full 1080p screen about 1 s.
- **One window.** Region picker, scanning animation and result all live in a single layer-shell window, so nothing is created or torn down between steps.
- **Language packs from the settings panel.** After a scan, the gear in the bottom-right corner opens settings. For a missing language you choose: download it straight into your home folder (no password), or install it with your distro's package manager (pacman, apt, dnf, apk), which needs a password. The second option shows the exact command, with buttons to copy it or run it in a terminal.
- **Keyboard and mouse.** `Ctrl+A` selects everything, `Ctrl+C` or `Enter` copies, `Esc` closes.
- **Quiet UI.** Monochrome, JetBrains Mono, Hyprland's own animation curve. The highlight colour is configurable. English and Turkish interface, switchable in settings.

## Requirements

- Hyprland and [Quickshell](https://quickshell.org)
- `grim`, `wl-clipboard`
- `tesseract` with at least one language pack
- Python 3 with `numpy` and `pillow`

## Install

```sh
git clone https://github.com/lunanoir21/scribe
cd scribe
./install.sh --patch
```

`--patch` copies the module to `~/.config/quickshell/vendor/scribe`, adds the import and `ScribeHost {}` to your `Shell.qml`, and appends the key bind to `hyprland.conf`. Edited files are backed up once as `<file>.scribe.bak`, and every edit sits between marker comments. Without `--patch` the script only copies the files and prints the lines to add.

```sh
./install.sh --help
  --dest DIR    folder that will hold scribe/        (default ~/.config/quickshell/vendor)
  --shell FILE  your Quickshell Shell.qml            (default <dest>/../Shell.qml)
  --hypr FILE   your hyprland.conf                   (default ~/.config/hypr/hyprland.conf)
  --key KEYS    bind modifiers and key               (default "SUPER SHIFT, T")
  --uninstall   remove the module and the added lines
```

The bind it adds:

```
bind = SUPER SHIFT, T, exec, qs -p /path/to/Shell.qml ipc call scribe start
```

## Use

1. Press `Super+Shift+T`. The screen freezes.
2. Drag a box around the text. A sweeping line shows it is being read.
3. Drag over the words you want. A toolbar appears above the selection: **Copy** or **Select all**.

| Key | Action |
|---|---|
| `Ctrl+A` | select all text |
| `Ctrl+C` / `Enter` | copy the selection |
| `Esc` | close (closes the settings panel first when it is open) |
| right click | clear the selection |

## Settings

The gear in the bottom-right corner (shown after a scan) opens the panel:

- **Reading languages.** Tick the languages to read with. Languages you do not have show a **Download** button, which offers two ways to install (see below).
- **Behaviour.** Close after copy, copy everything right after reading, join the lines of a paragraph.
- **Highlight colour.**

Everything is stored in `~/.config/scribe/settings.json` (created on first change, mode 600, so upgrades never overwrite it):

| Key | Default | Meaning |
|---|---|---|
| `langs` | `"tur+eng"` | Tesseract language codes joined with `+` |
| `autoCopy` | `false` | copy all text as soon as the read finishes |
| `closeAfterCopy` | `true` | close the overlay shortly after copying |
| `joinLines` | `true` | join the lines of a paragraph with spaces instead of newlines |
| `minConfidence` | `60` | below this average confidence the result is flagged as unsure |
| `highlight` | `"#8ab4f8"` | selection colour |
| `ui` | `"auto"` | interface language: `auto` (follows `$LANG`), `tr` or `en` |

### Language packs

Pressing **Download** next to a language opens a small card with two options:

1. **Download directly.** Fetches `<code>.traineddata` from `tesseract-ocr/tessdata_fast` into `~/.local/share/scribe/tessdata`. No password, works on any distro.
2. **Install with the package manager.** Needs a password, so scribe does not run it behind your back. It shows the command and gives you **Copy command** and **Run in terminal** (kitty, foot, alacritty, wezterm, konsole, gnome-terminal, xfce4-terminal or xterm, whichever you have; `$TERMINAL` wins). The list refreshes when the terminal closes.

| Distro family | Command shown |
|---|---|
| Arch, CachyOS, Manjaro, EndeavourOS | `sudo pacman -S --needed tesseract-data-<code>` |
| Debian, Ubuntu, Mint, Pop!_OS | `sudo apt-get install -y tesseract-ocr-<code>` |
| Fedora, RHEL, Nobara | `sudo dnf install -y tesseract-langpack-<code>` |
| Alpine | `sudo apk add tesseract-ocr-data-<code>` |

On any other distro only the direct download is offered. Packs in `~/.local/share/scribe/tessdata` win over system ones. The same logic is on the command line: `python3 langs.py info`, `install <code>` (direct download), `command <code>` and `term <code>`.

## How it works

```
key bind ─▶ qs ipc call scribe start
            grim            freeze the focused output
            ScribeLens      drag a region (one full-screen layer window)
            ocr.py          crop, invert dark themes, cut into strips at blank rows,
                            one tesseract process per strip, merge word boxes
            ScribeLens      draw the words where they are, select by dragging
            wl-copy         copy
```

`scribe.sh read` prints one record per word (`W par line x y w h text`, logical pixels) and a final `CONF n`, so the engine can be used on its own.

## Development helpers

These answer only while the file `$XDG_RUNTIME_DIR/scribe-dev` exists (`touch` it first), so they are inert for normal users.

```sh
qs -p Shell.qml ipc call scribe test 340 120 700 260        # read a region, skip the drag
qs -p Shell.qml ipc call scribe testsel 340 120 700 260 3 9 # same, with words 3..9 pre-selected
qs -p Shell.qml ipc call scribe devopen                      # open the settings panel
qs -p Shell.qml ipc call scribe cancel                       # close everything
```

## Limits

- Handwriting and very small text (under about 10 px) are not read reliably.
- Reading a whole 1080p screen full of text still takes around a second.

## Security and privacy

scribe takes a screenshot of one monitor, so it is built to leave nothing behind: the screenshot lives in an owner-only runtime directory and is deleted when the overlay closes, nothing is sent anywhere, and the only network request is a language pack download you start yourself. It never runs a privileged command. See [SECURITY.md](SECURITY.md) for the full list of what it reads, writes and limits.

```sh
python3 -m unittest discover -s tests -v
```

## License

[MIT](LICENSE)
