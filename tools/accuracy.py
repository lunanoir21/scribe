#!/usr/bin/env python3
"""How accurately does scribe read text in different fonts, colours and sizes?

Renders a known paragraph (English and Turkish) with many fonts, colour schemes and sizes, reads
every image with scribe's own reader (`ocr.py`, the real pipeline) and compares the result with
the text that was drawn.

    python3 tools/accuracy.py [--out DIR] [--text eng|tur] [--stress-only | --skip-stress] [--quick]

Writes DIR/results.json with every run. Fonts that are not installed are skipped.

Two sets of runs:

- the clean set: every font, colour scheme and size, with scribe's default languages (tur+eng) and,
  at 16 px, with the single matching language;
- the stress set: the same renders damaged the way a photo is (rotation, blur, grain, JPEG, low
  resolution, uneven light), so the numbers are not only the easy case.

The score is character accuracy, 1 - edit distance / length after collapsing whitespace, and word
accuracy, the share of the drawn words that were read back in order. These are synthetic renders,
not photographs: real photos are usually somewhat worse, and handwriting is not covered at all.
"""

import argparse
import difflib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent

TEXTS = {
    "eng": (
        "The courtyard garden will be closed for planting from Monday to Friday. Please keep "
        "bicycles in the shed and use the side entrance while the work is done. Thank you for "
        "your patience while the new flower beds are prepared. Questions? Write to "
        "hello@example.org or call 0532 123 45 67."
    ),
    "tur": (
        "Avlu bahçesi, Pazartesi gününden Cuma gününe kadar ekim çalışması nedeniyle kapalı "
        "olacaktır. Lütfen bisikletlerinizi kulübeye bırakın ve çalışma sürerken yan girişi "
        "kullanın. Yeni çiçek tarhları hazırlanırken gösterdiğiniz sabır için teşekkür ederiz. "
        "Sorularınız için hello@example.org adresine yazın."
    ),
}
# (family, style, label)
FONTS = [
    ("Noto Sans", "Regular", "Noto Sans"),
    ("Noto Sans", "Bold", "Noto Sans Bold"),
    ("Noto Serif", "Regular", "Noto Serif"),
    ("Noto Serif", "Italic", "Noto Serif Italic"),
    ("Noto Serif Display", "Regular", "Noto Serif Display"),
    ("Liberation Sans", "Regular", "Liberation Sans"),
    ("Cantarell", "Regular", "Cantarell"),
    ("DejaVu Sans Mono", "Book", "DejaVu Sans Mono"),
    ("JetBrains Mono", "Regular", "JetBrains Mono"),
    ("Hack", "Regular", "Hack"),
    ("Iosevka", "Regular", "Iosevka"),
]
# (label, text colour, background)  the background may be "noise"
SCHEMES = [
    ("black on white", (0, 0, 0), (255, 255, 255)),
    ("white on black", (255, 255, 255), (0, 0, 0)),
    ("light on dark theme", (230, 230, 230), (30, 30, 30)),
    ("dark grey on light grey", (60, 60, 60), (220, 220, 220)),
    ("green on black (terminal)", (0, 200, 0), (0, 0, 0)),
    ("yellow on dark blue", (255, 230, 100), (20, 30, 90)),
    ("red on white", (200, 0, 0), (255, 255, 255)),
    ("grey on white (low contrast)", (150, 150, 150), (255, 255, 255)),
    ("white on a busy background", (255, 255, 255), "noise"),
]
SIZES = [12, 16, 22]
WIDTH = 1100
MARGIN = 24


def font_file(family, style):
    r = subprocess.run(
        ["fc-match", "-f", "%{file}", f"{family}:style={style}"],
        capture_output=True,
        text=True,
        check=False,
    )
    path = r.stdout.strip()
    return path if path and Path(path).exists() else None


def luminance(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(fg, bg):
    if bg == "noise":
        bg = (90, 90, 90)
    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def background(kind, size):
    if kind != "noise":
        return Image.new("RGB", size, kind)
    import random

    rnd = random.Random(3)  # noqa: S311  (a repeatable background, not a secret)
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(size[1]):
        for x in range(size[0]):
            base = 70 + int(60 * (x / size[0])) + rnd.randint(-28, 28)
            px[x, y] = (max(0, base - 20), max(0, base - 10), min(255, base + 15))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def render(text, path, px, fg, bg, width=WIDTH):
    font = ImageFont.truetype(path, px)
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if font.getlength(trial) > width - 2 * MARGIN and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    step = int(px * 1.45)
    size = (width, 2 * MARGIN + step * len(lines))
    img = background(bg, size)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((MARGIN, MARGIN + i * step), line, font=font, fill=fg)
    return img


def levenshtein(a, b):
    if not a:
        return len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def score(truth, read):
    t, r = " ".join(truth.split()), " ".join(read.split())
    chars = max(0.0, 1 - levenshtein(t, r) / max(len(t), 1))
    tw, rw = t.split(), r.split()
    blocks = difflib.SequenceMatcher(None, tw, rw, autojunk=False).get_matching_blocks()
    words = sum(b.size for b in blocks) / max(len(tw), 1)
    return chars, words


def read_image(img, langs):
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "img.png"
        img.save(path)
        env = {**os.environ, "SCRIBE_DEV": "1"}
        r = subprocess.run(
            [
                sys.executable,
                "-I",
                str(ROOT / "ocr.py"),
                str(path),
                "0",
                "0",
                str(img.width),
                str(img.height),
                "1",
                langs,
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            check=False,
        )
    words = [
        ln.split("\t", 7)[7]
        for ln in r.stdout.splitlines()
        if ln.startswith("W\t") and len(ln.split("\t")) >= 8
    ]
    return " ".join(words)


# damage that a photo of text has and a clean render does not: (label, function)
def _noise(img, sigma):
    import random

    rnd = random.Random(5)  # noqa: S311  (repeatable grain, not a secret)
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b = px[x, y]
            n = int(rnd.gauss(0, sigma))
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    return out


def _jpeg(img, quality):
    import io

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def _light(img, low):
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            k = low + (1 - low) * (x / out.width)
            r, g, b = px[x, y]
            px[x, y] = (int(r * k), int(g * k), int(b * k))
    return out


def _rotate(img, deg):
    fill = img.getpixel((2, 2))
    return img.rotate(deg, expand=True, resample=Image.BICUBIC, fillcolor=fill)


STRESS = [
    ("rotated 3 degrees", lambda i: _rotate(i, 3)),
    ("rotated 8 degrees", lambda i: _rotate(i, 8)),
    ("blurred (radius 1.2)", lambda i: i.filter(ImageFilter.GaussianBlur(1.2))),
    ("grain (noise 20)", lambda i: _noise(i, 20)),
    ("JPEG quality 25", lambda i: _jpeg(i, 25)),
    (
        "low resolution (55%)",
        lambda i: i.resize((int(i.width * 0.55), int(i.height * 0.55)), Image.BILINEAR),
    ),
    ("uneven light", lambda i: _light(i, 0.4)),
    (
        "photo-like (all together)",
        lambda i: _jpeg(
            _light(_noise(_rotate(i.filter(ImageFilter.GaussianBlur(0.8)), 2.5), 12), 0.6), 40
        ),
    ),
]
STRESS_FONTS = ["Noto Sans", "Noto Serif", "DejaVu Sans Mono"]
STRESS_SCHEMES = ["black on white", "light on dark theme"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "assets" / "accuracy"))
    ap.add_argument("--text", choices=sorted(TEXTS), help="only this text (to split a long run)")
    ap.add_argument(
        "--quick", action="store_true", help="fewer fonts and schemes, for a smoke test"
    )
    ap.add_argument("--stress-only", action="store_true", help="only the damaged-image set")
    ap.add_argument("--skip-stress", action="store_true", help="skip the damaged-image set")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    fonts = [(f, s, lbl, font_file(f, s)) for f, s, lbl in FONTS]
    missing = [lbl for _, _, lbl, p in fonts if not p]
    fonts = [(f, s, lbl, p) for f, s, lbl, p in fonts if p]
    schemes = SCHEMES[:3] if args.quick else SCHEMES
    if args.quick:
        fonts = fonts[:2]
    runs = []
    for lang, text in TEXTS.items():
        if (args.text and lang != args.text) or args.stress_only:
            continue
        for _fam, _style, label, path in fonts:
            for sname, fg, bg in schemes:
                for px in SIZES:
                    img = render(text, path, px, fg, bg)
                    # scribe's default is tur+eng; the matching single language too, at 16 px
                    modes = ["tur+eng"] + ([lang] if px == 16 else [])
                    for mode in modes:
                        read = read_image(img, mode)
                        chars, words = score(text, read)
                        runs.append(
                            {
                                "text": lang,
                                "font": label,
                                "scheme": sname,
                                "size": px,
                                "langs": mode,
                                "chars": round(chars, 4),
                                "words": round(words, 4),
                                "contrast": round(contrast(fg, bg), 2),
                            }
                        )
                        print(
                            f"{lang} {label:20s} {sname:30s} {px:2d}px {mode:8s} "
                            f"chars {chars:6.1%} words {words:6.1%}",
                            flush=True,
                        )
    if not args.skip_stress:
        files = {lbl: font_file(f, st) for f, st, lbl in FONTS}
        scheme_by = {n: (fg, bg) for n, fg, bg in SCHEMES}
        for lang, text in TEXTS.items():
            if args.text and lang != args.text:
                continue
            for label in STRESS_FONTS:
                if not files.get(label):
                    continue
                for sname in STRESS_SCHEMES:
                    fg, bg = scheme_by[sname]
                    clean = render(text, files[label], 16, fg, bg)
                    for dname, fn in STRESS:
                        read = read_image(fn(clean), "tur+eng")
                        chars, words = score(text, read)
                        runs.append(
                            {
                                "kind": "stress",
                                "text": lang,
                                "font": label,
                                "scheme": sname,
                                "damage": dname,
                                "size": 16,
                                "langs": "tur+eng",
                                "chars": round(chars, 4),
                                "words": round(words, 4),
                            }
                        )
                        print(
                            f"{lang} STRESS {label:18s} {sname:20s} {dname:28s} "
                            f"chars {chars:6.1%} words {words:6.1%}",
                            flush=True,
                        )
    if not args.skip_stress:
        files = {lbl: font_file(f, st) for f, st, lbl in FONTS}
        # how much tilt can a paragraph take? A narrow block of larger text, as in a photo
        if files.get("Noto Sans"):
            for lang, text in TEXTS.items():
                if args.text and lang != args.text:
                    continue
                clean = render(text, files["Noto Sans"], 24, (0, 0, 0), (255, 255, 255), width=700)
                for deg in (0, 0.5, 1, 2, 3, 5, 8):
                    read = read_image(_rotate(clean, deg) if deg else clean, "tur+eng")
                    chars, words = score(text, read)
                    runs.append(
                        {
                            "kind": "rotation",
                            "text": lang,
                            "font": "Noto Sans",
                            "scheme": "black on white",
                            "degrees": deg,
                            "size": 24,
                            "langs": "tur+eng",
                            "chars": round(chars, 4),
                            "words": round(words, 4),
                        }
                    )
                    print(
                        f"{lang} ROTATION {deg:>3} degrees 24px, 700 px wide  "
                        f"chars {chars:6.1%} words {words:6.1%}",
                        flush=True,
                    )
        # the two sample photos of a printed notice
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import sample_photos

        with tempfile.TemporaryDirectory() as d:
            for lang, spec in sample_photos.SPECS.items():
                if args.text and lang != args.text:
                    continue
                path = Path(d) / spec["file"]
                sample_photos.make_photo(spec, path)
                read = read_image(Image.open(path).convert("RGB"), "tur+eng")
                chars, words = score(sample_photos.truth(spec), read)
                runs.append(
                    {
                        "kind": "photo",
                        "text": lang,
                        "photo": spec["file"],
                        "langs": "tur+eng",
                        "chars": round(chars, 4),
                        "words": round(words, 4),
                    }
                )
                print(
                    f"{lang} PHOTO {spec['file']:14s} chars {chars:6.1%} words {words:6.1%}",
                    flush=True,
                )
    (out / "results.json").write_text(
        json.dumps({"missing_fonts": missing, "runs": runs}, indent=1)
    )
    print(f"{len(runs)} runs written to {out / 'results.json'}")


if __name__ == "__main__":
    main()
