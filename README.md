# sortingen (`v1.1.0`)

Terminal üzerinden herhangi bir klasördeki dosyaları uzantılarına (`--doctype`), kategorilerine (`--category`) veya değiştirilme tarihlerine (`--date`) göre alt klasörlere ayıran, Türkçe dizin çözümleme, masaüstü dahil etme (`--include-desktop`) ve geri alma (`--undo`) destekli komut satırı aracı.

> Standart POSIX `sort` komutu (`/usr/bin/sort`) sistemde mevcut olduğundan, çakışma olmaması için komut adı **`sortingen`** olarak yapılandırılmıştır.

---

## Özellikler

- **`--doctype` (Varsayılan):** Klasör içindeki dosyaları uzantılarına göre (`pdf/`, `docx/`, `jpg/`, `zip/`, `tar.gz/`, uzantısızlar için `diger/`) alt klasörlere yerleştirir. Hedef dizinde `Desktop` veya `Masaüstü` klasörü bulunuyorsa `.desktop` kısayollarını oraya atmak yerine `apps/` (veya `desktop_shortcuts/`) klasörüne yönlendirir.
- **`--category` (`-c`) & XDG Dizin Eşleştirme:** Dosyaları ana kategorilere (`Belgeler`, `Resimler`, `Videolar`, `Müzik`, `apps`, `Arşivler`, `Kodlar`) ayırır; hedefte mevcut `Documents`, `Pictures`, `Görseller`, `Videos`, `Music`, `Musics`, `Sesler`, `Apps`, `Uygulamalar`, `Kurulumlar` gibi eşanlamlı XDG/kullanıcı klasörleri varsa yenisini açmadan mevcut klasörü kullanır.
- **`--include-desktop` (`-D`):** Kullanıcının Masaüstü klasöründeki (`~/Desktop` veya `~/Masaüstü`) dosyaları da taramaya dahil eder; sistem ikonlarını (`computer.desktop`, `trash-can.desktop`, `user-home.desktop`, `network.desktop`) masaüstünde korur ve geri kalan dosyaları hedef klasöre taşır (`--undo` ile geri alınabilir).
- **Mevcut Klasörleri Tanıma (Case-Insensitive & Türkçe Normalizasyon):** Hedef dizinde halihazırda `PDF/`, `Pdf/` veya `pdf/` gibi bir klasör varsa yeni klasör açmaz; ilgili dosyaları doğrudan mevcut klasörün içine taşır.
- **Akıllı Türkçe Klasör Çözümleme:** Hangi dizinde olursanız olun `sortingen indirilenler --doctype` yazdığınızda Türkçe karakter dönüşümüyle (`i` ↔ `İ`, `ı` ↔ `I`) `~/İndirilenler` (veya `~/Downloads`) klasörünü otomatik bulur.
- **Sıfır Veri Kaybı (Çakışma Koruması):** Hedef alt klasörde aynı isimli bir dosya varsa üzerine yazmaz; `belge (1).pdf`, `belge (2).pdf` şeklinde numaralandırarak korur.
- **Aktif İndirme Koruması:** İndirmesi devam eden `.crdownload`, `.part`, `.partial`, `.tmp`, `.aria2` uzantılı geçici dosyalara ve gizli dosyalara (`.dosya`) dokunmaz.
- **Tek Komutla Geri Alma (`--undo`):** Yapılan son sıralama işlemini `sortingen <klasör> --undo` ile tamamen geri alır ve yalnızca `sortingen` tarafından yeni oluşturulmuş boş klasörleri temizler.

---

## Kullanım

```bash
# İndirilenler klasörünü dosya tiplerine (pdf, docx, jpg...) göre düzenle
sortingen indirilenler --doctype

# Belirli bir dizini dosya tiplerine göre düzenle
sortingen ~/İndirilenler --doctype
sortingen /path/to/folder --doctype

# Bulunduğun klasörü düzenle
sortingen . --doctype

# Hiçbir dosyayı taşımadan önce ne yapılacağını önizle (Dry-Run)
sortingen indirilenler --doctype --dry-run

# Ana kategorilere göre düzenle (Belgeler, Resimler, Videolar, Müzik, apps, Arşivler...)
sortingen indirilenler --category

# Ana dizini ve Masaüstü'nü birlikte kategorilere göre düzenle (sistem ikonları korunur)
sortingen ~ --category --include-desktop

# Tarihe göre düzenle (YYYY-AA)
sortingen indirilenler --date

# Son yapılan düzenlemeyi geri al
sortingen indirilenler --undo
```

---

## Testler

```bash
python3 tests/test_sortingen.py -v
```
