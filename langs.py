#!/usr/bin/env python3
"""scribe language packs: what is installed, and how to get more on this OS.

usage:
  langs.py info              PM<TAB>name, DIR<TAB>path, then L<TAB>code<TAB>system|user per installed language
  langs.py install <code>    install a language, printing MSG<TAB>text / PCT<TAB>n lines, exit 0 on success

A pack is installed with the distro's package manager (asking for a password through
pkexec) when the distro is known. If that is not possible, or fails, the tessdata_fast
file is downloaded into ~/.local/share/scribe/tessdata instead, which needs no root.
"""
import os
import shutil
import subprocess
import sys
import urllib.request

USER_DIR = os.path.expanduser("~/.local/share/scribe/tessdata")
FAST_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{}.traineddata"

# distro family -> (package manager, install argv template, package name template)
FAMILIES = {
    "arch": ("pacman", ["pacman", "-S", "--needed", "--noconfirm"], "tesseract-data-{code}"),
    "debian": ("apt", ["apt-get", "install", "-y"], "tesseract-ocr-{dash}"),
    "fedora": ("dnf", ["dnf", "install", "-y"], "tesseract-langpack-{code}"),
    "alpine": ("apk", ["apk", "add"], "tesseract-ocr-data-{code}"),
}
LIKE = {
    "arch": "arch", "cachyos": "arch", "manjaro": "arch", "endeavouros": "arch", "artix": "arch",
    "debian": "debian", "ubuntu": "debian", "linuxmint": "debian", "pop": "debian", "kali": "debian",
    "fedora": "fedora", "rhel": "fedora", "centos": "fedora", "nobara": "fedora",
    "alpine": "alpine",
}


def os_release():
    info = {}
    try:
        for line in open("/etc/os-release"):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                info[k] = v.strip('"')
    except OSError:
        pass
    return info


def family():
    info = os_release()
    for token in [info.get("ID", "")] + info.get("ID_LIKE", "").split():
        if token in LIKE:
            return LIKE[token]
    return None


def system_dir():
    out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True)
    first = (out.stdout or out.stderr).split("\n")[0]
    if '"' in first:
        return first.split('"')[1].rstrip("/")
    return "/usr/share/tessdata"


def installed():
    found = {}
    for source, d in (("system", system_dir()), ("user", USER_DIR)):
        try:
            for f in os.listdir(d):
                if f.endswith(".traineddata") and f != "osd.traineddata":
                    found[f[: -len(".traineddata")]] = source if f[:-12] not in found else found[f[:-12]]
        except OSError:
            pass
    return found


def info():
    fam = family()
    name = os_release().get("PRETTY_NAME", "")
    print(f"PM\t{FAMILIES[fam][0] if fam else 'indirme'}\t{name}")
    print(f"DIR\t{USER_DIR}")
    for code, source in sorted(installed().items()):
        print(f"L\t{code}\t{source}")


def say(text):
    print(f"MSG\t{text}", flush=True)


def download(code):
    os.makedirs(USER_DIR, exist_ok=True)
    dest = os.path.join(USER_DIR, f"{code}.traineddata")
    say(f"{code} indiriliyor (tessdata_fast)")
    try:
        with urllib.request.urlopen(FAST_URL.format(code), timeout=30) as r:
            total = int(r.headers.get("Content-Length") or 0)
            done, last = 0, -1
            with open(dest + ".part", "wb") as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done * 100 // total
                        if pct != last:
                            last = pct
                            print(f"PCT\t{pct}", flush=True)
        os.replace(dest + ".part", dest)
    except Exception as e:  # network, 404, disk
        try:
            os.remove(dest + ".part")
        except OSError:
            pass
        say(f"İndirme başarısız: {e}")
        return False
    say(f"{code} kuruldu")
    return True


def via_package_manager(code):
    fam = family()
    if not fam:
        return False
    pm, argv, pkg = FAMILIES[fam]
    if not shutil.which("pkexec") or not shutil.which(argv[0]):
        return False
    package = pkg.format(code=code, dash=code.replace("_", "-"))
    say(f"{pm} ile {package} kuruluyor, parola istenebilir")
    r = subprocess.run(["pkexec"] + argv + [package], capture_output=True, text=True)
    if r.returncode == 0 and code in installed():
        say(f"{code} kuruldu")
        return True
    say("Paket yöneticisi ile kurulamadı, doğrudan indiriliyor")
    return False


def install(code):
    if not code.replace("_", "").isalnum():
        say("Geçersiz dil kodu")
        return 1
    if code in installed():
        say(f"{code} zaten kurulu")
        return 0
    if via_package_manager(code) or download(code):
        return 0
    return 1


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "info":
        info()
    elif len(sys.argv) >= 3 and sys.argv[1] == "install":
        sys.exit(install(sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(64)
