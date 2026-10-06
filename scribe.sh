#!/usr/bin/env bash
# scribe.sh — helper for the scribe OCR module (OCR itself is ocr.py).
#   scribe.sh shot [output]                       grab one output, print the png path
#   scribe.sh read <png> <x> <y> <w> <h> <scale> <langs>
#       Crop (logical px * scale), clean up, run tesseract.
#       stdout, one record per line:
#         W<TAB>par<TAB>line<TAB>x<TAB>y<TAB>w<TAB>h<TAB>word    (logical px, relative to the crop)
#         CONF<TAB><0-100>                                        (last line)
#       Exit 2 + "ERR<TAB>nolang" when no requested language pack is installed.
set -u
RT="${XDG_RUNTIME_DIR:-/tmp}/scribe"
mkdir -p "$RT"

case "${1:-}" in
shot)
    out="$RT/shot.png"
    if [ -n "${2:-}" ]; then
        grim -l 0 -o "$2" "$out" || exit 1
    else
        grim -l 0 "$out" || exit 1
    fi
    echo "$out"
    ;;
read)
    # the real work (crop, strips read in parallel, tesseract) lives in ocr.py
    exec python3 -I "$(dirname "$0")/ocr.py" "$2" "$3" "$4" "$5" "$6" "$7" "$8"
    ;;
*)
    echo "usage: scribe.sh shot|read ..." >&2
    exit 64
    ;;
esac
