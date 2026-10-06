#!/usr/bin/env bash
# scribe installer.
#
#   ./install.sh                  copy the module and print what to add to your config
#   ./install.sh --patch          also add the import to Shell.qml and the key bind to hyprland.conf
#   ./install.sh --uninstall      remove the module and the lines --patch added
#
# Options:
#   --dest DIR    folder that will hold the scribe/ module   (default: ~/.config/quickshell/vendor)
#   --shell FILE  your Quickshell Shell.qml                  (default: <dest>/../Shell.qml)
#   --hypr FILE   your hyprland.conf                         (default: ~/.config/hypr/hyprland.conf)
#   --key KEYS    Hyprland bind modifiers and key            (default: "SUPER SHIFT, T")
#   --no-deps-check   skip the check for grim, tesseract and friends
#
# Nothing outside --dest, --shell and --hypr is touched. Files that get edited are backed up
# once as <file>.scribe.bak, and every edit is wrapped in marker comments so it can be undone.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.config/quickshell/vendor"
SHELLQML=""
HYPR="$HOME/.config/hypr/hyprland.conf"
KEYS="SUPER SHIFT, T"
PATCH=0
UNINSTALL=0
CHECK_DEPS=1

while [ $# -gt 0 ]; do
    case "$1" in
        --patch) PATCH=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --no-deps-check) CHECK_DEPS=0 ;;
        --dest) DEST="$2"; shift ;;
        --shell) SHELLQML="$2"; shift ;;
        --hypr) HYPR="$2"; shift ;;
        --key) KEYS="$2"; shift ;;
        -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 64 ;;
    esac
    shift
done

# the key spec is written into hyprland.conf: allow only what a bind line needs
KEY_RE='^[A-Za-z0-9_ +,]+$'
# LC_ALL=C: in some locales (Turkish, for one) [A-Z] is not plain ASCII
if ! ( export LC_ALL=C; [[ "$KEYS" =~ $KEY_RE ]] ); then
    echo "--key may only contain letters, digits, space, comma, + and _" >&2
    exit 64
fi

DEST="${DEST/#\~/$HOME}"
TARGET="$DEST/scribe"
[ -n "$SHELLQML" ] || SHELLQML="$(dirname "$DEST")/Shell.qml"
BEGIN="# >>> scribe (managed) >>>"          # hyprland.conf comments
END="# <<< scribe (managed) <<<"
QBEGIN="// >>> scribe (managed) >>>"        # QML comments
QEND="// <<< scribe (managed) <<<"

backup() { [ -f "$1" ] && [ ! -f "$1.scribe.bak" ] && cp "$1" "$1.scribe.bak" || true; }

# ── uninstall ────────────────────────────────────────────────────────────────
if [ "$UNINSTALL" = 1 ]; then
    python3 - "$SHELLQML" "$QBEGIN" "$QEND" "$HYPR" "$BEGIN" "$END" <<'PY'
import re, sys
args = sys.argv[1:]
for path, begin, end in zip(args[0::3], args[1::3], args[2::3]):
    try:
        s = open(path).read()
    except OSError:
        continue
    s2 = re.sub(r"(?:(?<=\n)\n)?[ \t]*" + re.escape(begin) + r".*?" + re.escape(end) + r"[ \t]*\n?", "", s, flags=re.S)
    if s2 != s:
        open(path, "w").write(s2)
        print("cleaned", path)
PY
    # only ever delete a folder that really is a scribe install: named scribe, with our files in it
    if [ -d "$TARGET" ] && [ ! -L "$TARGET" ] && [ "$(basename "$TARGET")" = "scribe" ] \
        && [ -f "$TARGET/scribe.sh" ] && [ -f "$TARGET/ui/ScribeHost.qml" ]; then
        rm -r -- "$TARGET"
        echo "removed $TARGET"
    elif [ -e "$TARGET" ]; then
        echo "refusing to remove $TARGET: it does not look like a scribe install" >&2
    fi
    echo "Done. Your settings (~/.config/scribe) and downloaded language packs (~/.local/share/scribe) stay."
    exit 0
fi

# ── dependency check ─────────────────────────────────────────────────────────
missing=()
if [ "$CHECK_DEPS" = 1 ]; then
    for bin in grim wl-copy tesseract python3; do command -v "$bin" >/dev/null || missing+=("$bin"); done
    command -v qs >/dev/null || command -v quickshell >/dev/null || missing+=("quickshell")
    python3 -c "import numpy, PIL" 2>/dev/null || missing+=("python numpy + pillow")
fi
if [ ${#missing[@]} -gt 0 ]; then
    echo "Missing: ${missing[*]}" >&2
    echo "  Arch:   sudo pacman -S grim wl-clipboard tesseract python-numpy python-pillow" >&2
    echo "  Debian: sudo apt install grim wl-clipboard tesseract-ocr python3-numpy python3-pil" >&2
    echo "  Fedora: sudo dnf install grim wl-clipboard tesseract python3-numpy python3-pillow" >&2
    echo "(Quickshell: https://quickshell.org)" >&2
    exit 1
fi

# ── copy ─────────────────────────────────────────────────────────────────────
mkdir -p "$TARGET/ui"
install -m 755 "$HERE/scribe.sh" "$HERE/ocr.py" "$HERE/langs.py" "$HERE/config.py" "$TARGET/"
install -m 644 "$HERE"/ui/*.qml "$HERE/ui/qmldir" "$TARGET/ui/"
# a leftover settings.json from 0.1.x lived inside the module and is no longer read
rm -f -- "$TARGET/settings.json"
echo "Installed to $TARGET"

REL="$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$TARGET/ui" "$(dirname "$SHELLQML")")"
IMPORT_LINE="import \"$REL\" as ScribeModule"
HOST_LINE="ScribeModule.ScribeHost {}"
BIND_LINE="bind = $KEYS, exec, qs -p $SHELLQML ipc call scribe start"

if [ "$PATCH" = 0 ]; then
    cat <<EOF

Add this to $SHELLQML (the import near the other imports, the host inside ShellRoot):

    $IMPORT_LINE
    $HOST_LINE

and this to $HYPR:

    $BIND_LINE

or run again with --patch to do it for you.
EOF
    exit 0
fi

# ── patch ────────────────────────────────────────────────────────────────────
[ -f "$SHELLQML" ] || { echo "Shell.qml not found: $SHELLQML (use --shell)" >&2; exit 1; }
if grep -q "ScribeHost" "$SHELLQML"; then
    echo "Shell.qml already loads scribe, left alone"
else
    backup "$SHELLQML"
    python3 - "$SHELLQML" "$IMPORT_LINE" "$HOST_LINE" "$QBEGIN" "$QEND" <<'PY'
import re, sys
path, imp, host, begin, end = sys.argv[1:6]
s = open(path).read()
lines = s.split("\n")
last_import = max((i for i, l in enumerate(lines) if re.match(r"\s*import\s", l)), default=-1)
lines[last_import + 1:last_import + 1] = [begin, imp, end]
s = "\n".join(lines)
close = s.rstrip().rfind("}")
if close < 0:
    sys.exit("could not find the closing brace of ShellRoot")
s = s[:close] + f"    {begin}\n    {host}\n    {end}\n" + s[close:]
open(path, "w").write(s)
PY
    echo "Patched $SHELLQML"
fi

if [ -f "$HYPR" ] && grep -q "ipc call scribe start" "$HYPR"; then
    echo "$HYPR already has the bind, left alone"
elif [ -f "$HYPR" ]; then
    backup "$HYPR"
    printf '\n%s\n%s\n%s\n' "$BEGIN" "$BIND_LINE" "$END" >> "$HYPR"
    echo "Patched $HYPR"
else
    echo "hyprland.conf not found ($HYPR), add the bind yourself:  $BIND_LINE"
fi
echo "Quickshell reloads on its own. Press ${KEYS#*, } with ${KEYS%%,*} held to try it."
