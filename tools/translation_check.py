#!/usr/bin/env python3
"""Do links, e-mail addresses, phone numbers and IBANs survive translation unchanged?

Translates sentences that contain them with the offline engine (it must be installed) and checks
that every one of them comes back exactly as it went in. This is the only part of translation
that can be checked without reference translations; the quality of the translated words is not
measured here.

    python3 tools/translation_check.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ENTITIES = {
    "url": [
        "https://example.org/garden",
        "https://example.com/docs/layout?id=42",
        "www.example.net/a-b",
        "https://sub.example.org/bahce",
    ],
    "email": ["hello@example.org", "ali.veli+test@example.co.uk", "destek@example.com"],
    "phone": ["+90 532 123 45 67", "0532 123 45 67", "+44 20 7946 0958"],
    "iban": [
        "TR33 0006 1005 1978 6457 8413 26",
        "TR330006100519786457841326",
        "DE89 3704 0044 0532 0130 00",
    ],
}
SENTENCES = {
    "eng": [
        "Write to {x} if you have any questions.",
        "Please open {x} and read the notes first.",
        "The details are at {x}, as agreed on Monday.",
        "Send it to {x} before the end of the week.",
    ],
    "tur": [
        "Sorularınız varsa {x} adresine yazın.",
        "Lütfen önce {x} bağlantısını açın.",
        "Ayrıntılar pazartesi kararlaştırıldığı gibi {x} içinde.",
        "Hafta sonundan önce {x} alanına gönderin.",
    ],
}


def translate(text, src, tgt):
    r = subprocess.run(
        [sys.executable, "-I", str(ROOT / "translate.py"), "translate", "--src", src, "--tgt", tgt],
        input=text,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return json.loads(r.stdout)


def main():
    status = subprocess.run(
        [sys.executable, "-I", str(ROOT / "translate.py"), "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    info = json.loads(status.stdout)
    if not (info.get("runtime") and {"en-tr", "tr-en"} <= set(info.get("pairs", []))):
        print("the offline pack is not installed; install it from the settings panel first")
        return 1
    total = ok = 0
    rows = []
    for lang, (src, tgt) in {"eng": ("en", "tr"), "tur": ("tr", "en")}.items():
        for kind, values in ENTITIES.items():
            n = good = 0
            for value in values:
                for template in SENTENCES[lang]:
                    out = translate(template.format(x=value), src, tgt)
                    n += 1
                    good += bool(out.get("ok")) and value in out["text"]
            rows.append((f"{src}->{tgt}", kind, good, n))
            total += n
            ok += good
    for direction, kind, good, n in rows:
        print(f"{direction}  {kind:6s} {good}/{n}")
    print(f"unchanged: {ok}/{total} ({ok / total:.1%})")
    subprocess.run(
        [sys.executable, "-I", str(ROOT / "translate.py"), "stop"], capture_output=True, check=False
    )
    return 0 if ok == total else 2


if __name__ == "__main__":
    sys.exit(main())
