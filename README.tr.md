# scribe

Ekranındaki yazıyı Google Lens gibi seç ve kopyala. Hyprland için bir Quickshell modülü.

[Web sitesi](https://lunanoir21.github.io/scribe/) · [English](README.md) · [Değişiklik günlüğü](CHANGELOG.md)

Bir tuşa bas, yazının üstüne bir kutu çiz (video, resim, PDF, terminal, kopyalanamayan bir uygulama) ve scribe okusun. Yazı ekranda olduğu yerde kalır. Üstünden sürükleyerek seç, seçimin üstünde çıkan küçük çubuktan **Kopyala**'ya bas.

## Özellikler

- **Lens tarzı seçim.** Orijinal yazıya dokunulmaz. Kelimelerin üstünden sürüklemek, gerçek metin seçer gibi satır satır yarı saydam bir vurgu çizer.
- **Hızlı.** Seçim boş satırlardan şeritlere kesilir ve şeritler paralel Tesseract süreçleriyle okunur. 1000×600'lük bir alan yaklaşık 0,6 sn, tam 1080p ekran yaklaşık 1 sn sürer.
- **Tek pencere.** Alan seçimi, tarama animasyonu ve sonuç tek bir layer-shell penceresinde, adımlar arasında hiçbir şey yeniden yaratılmaz.
- **Ayarlardan dil paketi.** Taramadan sonra sağ alttaki dişli ayarları açar. Eksik diller dağıtımının paket yöneticisiyle (pacman, apt, dnf, apk) kurulur, olmazsa doğrudan ev klasörüne indirilir.
- **Klavye ve fare.** `Ctrl+A` hepsini seçer, `Ctrl+C` ya da `Enter` kopyalar, `Esc` kapatır.
- **Sakin arayüz.** Monokrom, JetBrains Mono, Hyprland'ın kendi animasyon eğrisi. Vurgu rengi ayarlanabilir.

## Gereksinimler

- Hyprland ve [Quickshell](https://quickshell.org)
- `grim`, `wl-clipboard`
- En az bir dil paketiyle `tesseract`
- `numpy` ve `pillow` ile Python 3
- `pkexec` (polkit) isteğe bağlı, yalnızca dil paketlerini paket yöneticisiyle kurmak için

## Kurulum

```sh
git clone https://github.com/lunanoir21/scribe
cd scribe
./install.sh --patch
```

`--patch` modülü `~/.config/quickshell/vendor/scribe` içine kopyalar, `Shell.qml` dosyana import ve `ScribeHost {}` ekler, `hyprland.conf` sonuna kısayolu yazar. Düzenlenen dosyaların bir kez `<dosya>.scribe.bak` yedeği alınır ve her değişiklik işaret yorumlarının arasındadır. `--patch` olmadan betik yalnızca dosyaları kopyalar ve eklemen gereken satırları yazdırır.

```sh
./install.sh --help
  --dest DIR    scribe/ klasörünün konacağı yer     (varsayılan ~/.config/quickshell/vendor)
  --shell FILE  Quickshell Shell.qml dosyan         (varsayılan <dest>/../Shell.qml)
  --hypr FILE   hyprland.conf dosyan                (varsayılan ~/.config/hypr/hyprland.conf)
  --key KEYS    kısayol tuşları                     (varsayılan "SUPER SHIFT, T")
  --uninstall   modülü ve eklenen satırları kaldır
```

Eklenen kısayol:

```
bind = SUPER SHIFT, T, exec, qs -p /path/to/Shell.qml ipc call scribe start
```

## Kullanım

1. `Super+Shift+T`'ye bas. Ekran donar.
2. Yazının üstüne bir kutu çiz. Süpürme çizgisi okunduğunu gösterir.
3. İstediğin kelimelerin üstünden sürükle. Seçimin üstünde bir çubuk çıkar: **Kopyala** ya da **Tümünü seç**.

| Tuş | İşlem |
|---|---|
| `Ctrl+A` | tüm yazıyı seç |
| `Ctrl+C` / `Enter` | seçimi kopyala |
| `Esc` | kapat (ayar paneli açıksa önce onu kapatır) |
| sağ tık | seçimi temizle |

## Ayarlar

Taramadan sonra sağ alttaki dişli paneli açar:

- **Okuma dilleri.** Okumak istediğin dilleri işaretle. Kurulu olmayan dillerde **İndir** düğmesi çıkar. Panel hangi paket yöneticisini kullanacağını söyler.
- **Davranış.** Kopyalayınca kapat, okuyunca hepsini kopyala, paragraf satırlarını birleştir.
- **Vurgu rengi.**

Her şey modülün yanındaki `settings.json` dosyasında saklanır:

| Anahtar | Varsayılan | Anlamı |
|---|---|---|
| `langs` | `"tur+eng"` | `+` ile birleştirilmiş Tesseract dil kodları |
| `autoCopy` | `false` | okuma bitince tüm yazıyı kopyala |
| `closeAfterCopy` | `true` | kopyalamadan kısa süre sonra kapat |
| `joinLines` | `true` | paragraf satırlarını yeni satır yerine boşlukla birleştir |
| `minConfidence` | `60` | ortalama güven bunun altındaysa sonuç "emin değil" diye işaretlenir |
| `highlight` | `"#8ab4f8"` | seçim rengi |

### Dil paketleri

| Dağıtım ailesi | Kurulum yöntemi |
|---|---|
| Arch, CachyOS, Manjaro, EndeavourOS | `pkexec` ile `pacman -S tesseract-data-<kod>` |
| Debian, Ubuntu, Mint, Pop!_OS | `pkexec` ile `apt-get install tesseract-ocr-<kod>` |
| Fedora, RHEL, Nobara | `pkexec` ile `dnf install tesseract-langpack-<kod>` |
| Alpine | `pkexec` ile `apk add tesseract-ocr-data-<kod>` |
| diğerleri ya da yukarıdaki başarısız olursa | `tesseract-ocr/tessdata_fast` içinden `<kod>.traineddata` dosyasını `~/.local/share/scribe/tessdata` içine indirir |

`~/.local/share/scribe/tessdata` içindeki paketler sistemdekilerden önceliklidir. Aynı mantık komut satırında da var: `python3 langs.py info` ve `python3 langs.py install deu`.

## Nasıl çalışır

```
kısayol ─▶ qs ipc call scribe start
           grim            odaktaki ekranı dondur
           ScribeLens      alan seç (tek tam ekran layer penceresi)
           ocr.py          kırp, koyu temayı ters çevir, boş satırlardan şeritlere kes,
                           şerit başına bir tesseract süreci, kelime kutularını birleştir
           ScribeLens      kelimeleri yerinde çiz, sürükleyerek seç
           wl-copy         kopyala
```

`scribe.sh read` kelime başına bir kayıt (`W par line x y w h text`, mantıksal piksel) ve son satırda `CONF n` yazdırır, yani motor tek başına da kullanılabilir.

## Geliştirici yardımcıları

```sh
qs -p Shell.qml ipc call scribe test 340 120 700 260        # sürüklemeyi atla, bölgeyi oku
qs -p Shell.qml ipc call scribe testsel 340 120 700 260 3 9 # aynısı, 3..9. kelimeler seçili
qs -p Shell.qml ipc call scribe devopen                      # ayar panelini aç
qs -p Shell.qml ipc call scribe cancel                       # her şeyi kapat
```

## Sınırlar

- El yazısı ve çok küçük (yaklaşık 10 px altı) yazılar güvenilir okunmaz.
- Yazı dolu bir 1080p ekranın tamamını okumak hâlâ yaklaşık bir saniye sürer.
- Arayüz metinleri şimdilik Türkçe.

## Lisans

[MIT](LICENSE)
