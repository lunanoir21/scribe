#!/usr/bin/env python3
"""Two made-up photos of a printed notice, one English and one Turkish, with the text they show.

They are the images in the website's screenshots and the "photos" rows of the accuracy results.
All content is invented. Needs Pillow and the Noto Sans and Noto Serif fonts.

    python3 tools/sample_photos.py OUTDIR      writes notice_en.jpg and notice_tr.jpg
"""

import math
import random
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1920, 1080
FONT_DIR = "/usr/share/fonts/noto/"

SPECS = {
    "eng": {
        "file": "notice_en.jpg",
        "title": "NOTICE TO RESIDENTS",
        "body": (
            "The courtyard garden will be closed for planting from Monday to Friday. Please keep "
            "bicycles in the shed and use the side entrance while the work is done. Thank you for "
            "your patience while the new flower beds are prepared."
        ),
        "contact": (
            "Questions? Write to hello@example.org, visit https://example.org/garden or call "
            "+90 532 123 45 67. Donations are welcome: IBAN TR33 0006 1005 1978 6457 8413 26."
        ),
        "seed": 7,
        "rot": -1.6,
        "paper": (244, 239, 226),
        "wood": (74, 56, 42),
        "sans": False,
        "blur": 0.55,
    },
    "tur": {
        "file": "notice_tr.jpg",
        "title": "SAKİNLERE DUYURU",
        "body": (
            "Avlu bahçesi, Pazartesi gününden Cuma gününe kadar ekim çalışması nedeniyle "
            "kapalı olacaktır. Lütfen bisikletlerinizi kulübeye bırakın ve çalışma sürerken "
            "yan girişi kullanın. Yeni çiçek tarhları hazırlanırken gösterdiğiniz sabır için "
            "teşekkür ederiz."
        ),
        "contact": (
            "Sorularınız için hello@example.org adresine yazın, https://example.org/bahce "
            "sayfasını ziyaret edin ya da +90 532 123 45 67 numarasını arayın. Bağışlar için "
            "IBAN TR33 0006 1005 1978 6457 8413 26."
        ),
        "seed": 11,
        "rot": 1.4,
        "paper": (238, 236, 222),
        "wood": (58, 66, 60),
        "sans": True,
        "blur": 0.3,
    },
}


def truth(spec):
    return " ".join([spec["title"], spec["body"], spec["contact"]])


def make_photo(spec, out):
    F = FONT_DIR
    random.seed(spec["seed"])  # noqa: S311  (repeatable picture, not a secret)
    bg = Image.new("RGB", (W, H), spec["wood"])
    px = bg.load()
    for y in range(H):
        for x in range(W):
            g = int(8 * math.sin(x / 9.0 + math.sin(y / 70.0) * 3) + random.randint(-4, 4))  # noqa: S311
            r, gg, b = px[x, y]
            px[x, y] = (max(0, min(255, r + g)), max(0, min(255, gg + g)), max(0, min(255, b + g)))
    bg = bg.filter(ImageFilter.GaussianBlur(1.2))
    pw, ph = 1180, 880
    paper = Image.new("RGB", (pw, ph), spec["paper"])
    d = ImageDraw.Draw(paper)
    ink = (34, 32, 30)
    if spec["sans"]:
        body_font = ImageFont.truetype(F + "NotoSans-Regular.ttf", 34)
        title_font = ImageFont.truetype(F + "NotoSans-Bold.ttf", 46)
    else:
        body_font = ImageFont.truetype(F + "NotoSerif-Regular.ttf", 34)
        title_font = ImageFont.truetype(F + "NotoSerif-Bold.ttf", 46)
    d.text((90, 70), spec["title"], font=title_font, fill=ink)
    d.line((90, 138, pw - 90, 138), fill=(120, 112, 100), width=2)
    y = 176
    for line in textwrap.wrap(spec["body"], width=44):
        d.text((90, y), line, font=body_font, fill=ink)
        y += 52
    y += 40
    for line in textwrap.wrap(spec["contact"], width=44):
        d.text((90, y), line, font=body_font, fill=ink)
        y += 52
    noise = Image.effect_noise((pw, ph), 14).convert("RGB")
    paper = ImageChops.blend(
        paper, ImageChops.multiply(paper, noise.point(lambda v: 200 + v // 5)), 0.35
    )
    rotd = paper.convert("RGBA").rotate(spec["rot"], expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", rotd.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 150), mask=rotd.split()[3])
    sh = sh.filter(ImageFilter.GaussianBlur(16))
    ox, oy = (W - rotd.width) // 2 + 10, (H - rotd.height) // 2 + 6
    bg = bg.convert("RGBA")
    bg.alpha_composite(sh, (ox + 14, oy + 20))
    bg.alpha_composite(rotd, (ox, oy))
    img = bg.convert("RGB")
    dr = ImageDraw.Draw(img)
    cx, cy = ox + pw // 2 - 20, oy + 34
    dr.ellipse((cx - 17, cy - 17, cx + 17, cy + 17), fill=(150, 36, 36))
    dr.ellipse((cx - 9, cy - 11, cx - 1, cy - 3), fill=(220, 120, 110))
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    for i in range(60):
        vd.ellipse(
            (-W * 0.25 + i * 8, -H * 0.25 + i * 5, W * 1.25 - i * 8, H * 1.25 - i * 5),
            fill=int(255 * (i / 60) ** 1.5),
        )
    img = Image.composite(
        img,
        Image.new("RGB", (W, H), (18, 14, 10)),
        vig.filter(ImageFilter.GaussianBlur(40)).point(lambda v: max(110, v)),
    )
    img = ImageEnhance.Contrast(img).enhance(1.04).filter(ImageFilter.GaussianBlur(spec["blur"]))
    grain = Image.effect_noise((W, H), 9).convert("RGB")
    img = ImageChops.add(img, grain.point(lambda v: max(0, v - 128) // 3))
    img.save(out, quality=88)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    for spec in SPECS.values():
        make_photo(spec, out / spec["file"])
        print("wrote", out / spec["file"])


if __name__ == "__main__":
    main()
