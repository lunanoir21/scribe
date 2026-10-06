#!/usr/bin/env python3
"""scribe OCR: crop, clean up and read a screen region with tesseract, fast.

usage: ocr.py <png> <x> <y> <w> <h> <scale> <langs>

The crop is cut into horizontal strips at blank pixel rows and the strips are read by
separate tesseract processes at the same time (tesseract itself is single threaded
here, so this is where the speed comes from).

stdout: one `W<TAB>par<TAB>line<TAB>x<TAB>y<TAB>w<TAB>h<TAB>word` per word (logical px,
relative to the crop), then `CONF<TAB><0-100>`. `ERR<TAB>nolang` + exit 2 if no
requested language pack is installed.
"""
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import langs as langpacks   # noqa: E402  (installed languages, system + user dir)

MIN_WORD_CONF = 40
UPSCALE_BELOW = 150_000     # px area: small selections are read at 2x
RETRY_BELOW_CONF = 60
RETRY_MAX_AREA = 1_500_000
MIN_STRIP = 70              # px, never cut thinner than this
MAX_STRIPS = 12


def tessdata_args(langs, tmp):
    """Extra tesseract args. Packs in the user dir (fast models) win over system ones; when any
    comes from there, tesseract gets a small tessdata dir of symlinks to the chosen files."""
    sysdir = langpacks.system_dir()
    chosen, from_user = {}, False
    for code in langs.split("+"):
        user_file = os.path.join(langpacks.USER_DIR, f"{code}.traineddata")
        sys_file = os.path.join(sysdir, f"{code}.traineddata")
        if os.path.exists(user_file):
            chosen[code], from_user = user_file, True
        else:
            chosen[code] = sys_file
    if not from_user:
        return []
    d = os.path.join(tmp, "tessdata")
    os.makedirs(d, exist_ok=True)
    for code, path in chosen.items():
        os.symlink(path, os.path.join(d, f"{code}.traineddata"))
    for extra in ("configs", "tessconfigs"):          # `tsv` output is a config file
        if os.path.exists(os.path.join(sysdir, extra)):
            os.symlink(os.path.join(sysdir, extra), os.path.join(d, extra))
    return ["--tessdata-dir", d]


def split_rows(gray, n):
    """Row indices where to cut `gray` into n strips, preferring blank rows."""
    h = gray.shape[0]
    if n <= 1:
        return [0, h]
    ptp = gray.max(axis=1).astype(int) - gray.min(axis=1).astype(int)
    blank = ptp < 28
    cuts = [0]
    span = h / n
    for k in range(1, n):
        target = int(span * k)
        lo = max(cuts[-1] + MIN_STRIP, target - int(span * 0.4))
        hi = min(h - MIN_STRIP, target + int(span * 0.4))
        if lo >= hi:
            continue
        window = np.arange(lo, hi)
        good = window[blank[lo:hi]]
        if good.size:
            cut = int(good[np.argmin(np.abs(good - target))])
        else:
            cut = int(window[np.argmin(ptp[lo:hi])])
        cuts.append(cut)
    cuts.append(h)
    return cuts


def read_strip(job):
    idx, img, y_off, up, scale, langs, tmp, extra = job
    path = os.path.join(tmp, f"s{idx}.png")
    img.save(path)
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    out = subprocess.run(
        ["tesseract", path, "stdout", "-l", langs, "--oem", "1", "--psm", "6",
         "-c", "tessedit_do_invert=0", "tsv"] + extra,
        capture_output=True, text=True, env=env).stdout
    f = scale * up
    words, confs = [], []
    for row in out.split("\n")[1:]:
        c = row.split("\t")
        if len(c) < 12 or c[0] != "5":
            continue
        text = c[11].strip()
        try:
            conf = float(c[10])
        except ValueError:
            continue
        if not text or conf < MIN_WORD_CONF:
            continue
        confs.append(conf)
        words.append((f"{idx}-{c[2]}-{c[3]}", f"{idx}-{c[2]}-{c[3]}-{c[4]}",
                      int(c[6]) / f, (int(c[7]) + y_off) / f, int(c[8]) / f, int(c[9]) / f, text))
    return words, confs


def run(gray, up, scale, langs, workers, tmp, extra):
    h = gray.shape[0]
    area = gray.shape[0] * gray.shape[1]
    n = 1 if area < UPSCALE_BELOW else max(1, min(workers, MAX_STRIPS, h // MIN_STRIP))
    cuts = split_rows(gray, n)
    img = Image.fromarray(gray)
    if up != 1:
        img = img.resize((img.width * up, img.height * up), Image.LANCZOS)
    jobs = []
    for i in range(len(cuts) - 1):
        y0, y1 = cuts[i] * up, cuts[i + 1] * up
        jobs.append((i, img.crop((0, y0, img.width, y1)), y0, up, scale, langs, tmp, extra))
    words, confs = [], []
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        for w, c in ex.map(read_strip, jobs):
            words += w
            confs += c
    return words, (sum(confs) / len(confs) if confs else 0)


def main():
    png, x, y, w, h, scale, want = sys.argv[1:8]
    x, y, w, h, scale = float(x), float(y), float(w), float(h), float(scale)

    have = set(langpacks.installed())
    langs = "+".join(l for l in want.split("+") if l in have)
    if not langs:
        print("ERR\tnolang")
        sys.exit(2)

    px, py, pw, ph = int(x * scale), int(y * scale), int(w * scale), int(h * scale)
    img = Image.open(png).convert("L").crop((px, py, px + pw, py + ph))
    if np.asarray(img).mean() < 128:          # light text on dark: flip it
        img = ImageOps.invert(img)
    gray = np.asarray(ImageOps.autocontrast(img))
    area = pw * ph
    workers = min(os.cpu_count() or 4, MAX_STRIPS)

    with tempfile.TemporaryDirectory(prefix="scribe-") as tmp:
        extra = tessdata_args(langs, tmp)
        up = 2 if area < UPSCALE_BELOW else 1
        words, conf = run(gray, up, scale, langs, workers, tmp, extra)
        if up == 1 and conf < RETRY_BELOW_CONF and area < RETRY_MAX_AREA:
            words2, conf2 = run(gray, 2, scale, langs, workers, tmp, extra)
            if conf2 > conf:
                words, conf = words2, conf2

    for par, line, wx, wy, ww, wh, text in words:
        print(f"W\t{par}\t{line}\t{wx:.1f}\t{wy:.1f}\t{ww:.1f}\t{wh:.1f}\t{text}")
    print(f"CONF\t{int(conf)}")


if __name__ == "__main__":
    main()
