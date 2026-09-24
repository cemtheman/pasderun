# Pas de Run — Motion Studio çalışma günlüğü

Bu dosya Motion Studio oturumlarının devam noktasıdır. **Yeni oturumun başında bu dosyayı oku; oturum bitmeden yeni adımları, kanıtları ve tam SHA'ları kronolojik olarak ekle.** Var olan kayıtları sessizce değiştirme. Sonuçları betik yazıldı / yerel test geçti / final Rig üzerinde Blender çalıştı / görüntü incelendi / kabul edildi biçiminde açıkça ayır. Her commit sonrası `git rev-parse HEAD` ve `git status --short --branch` ile doğrula; gerçekte çalışmayan bir komutu PASS sayma.

## Proje ve sınırlar

- Repo: `cemtheman/pasderun`.
- Motion Studio çalışma dalı: `motion-studio-v0-6-accepted-arm-visual-probe`. Bu dosya oluşturulmadan önce dalın doğrulanmış HEAD'i `550a3fb7a7fc8cf11860736b518c66593e5e9620` idi. **Güncel HEAD'i her oturumda yeniden sorgula; bu sayı gelecekte değişecek.**
- Kullanıcının Windows checkout'u: `C:\Users\chodo\Documents\pas-de-run`; Blender: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`.
- Güvenilir üretim tabanı: `main` üzerinde `080d42cb076a0efcc4902bbef7d9e42aae5550e3`; bu deneysel çalışma dalındaki değişiklikleri doğrudan `main` veya üretime aktarma.
- Kaynak model final `Rig` içeren GLB'dir; kanonik bacak anahtarları `left_thigh`, `left_shin`, `left_foot`, `left_toes` ve sağ karşılıklarıdır. Bunların rig bone adları kalibrasyonla çözülür. Scratch ortamında Blender ve yerel kaynak GLB bulunmayabilir; Python testleri gerçek Rig sonucunun yerine geçmez.
- Kılavuz: *Ballet Positions Catalog & Guide.pdf*, SHA-256 `2d6321bf92dd97014fb86555bc30426772e9a34e0527e7bf397339fa3648793d`.
- Kullanıcı kararı: Tüm poz ve geçiş adaylarını hızla üret; bale hocasının değerlendirmesini sonraya bırak. Geometrik hata, henüz yapılmayan değerlendirme veya başarısız çıktı gerçeğini saklama.

## Değişmez çalışma yöntemi

1. `git fetch origin motion-studio-v0-6-accepted-arm-visual-probe`; doğru dalda olduğundan, güncel SHA'dan ve temiz/korunması gereken yerel değişikliklerden emin ol. Kullanıcının yerel commit'lerini veya üretilmiş dosyalarını silme; `reset --hard` ve zorlamalı ref güncellemesi kullanma.
2. Yalnızca ilgili Motion Studio kaynaklarını ve gerçek raporları oku. Önceki test edilmiş pozların kaynaklarını, kabul edilmiş Phase 10 animasyonlarını, `main` veya üretim paketini değiştirme.
3. Her düzeltme için dar kapsamlı Python testi çalıştır; Blender veya Godot testi gerektiğinde Windows çalıştırmasının çıktısını ayrıca iste/incele. `report.json` durumunu, sayısal ihlalleri, görüntüleri ve Blender çıkışını kaydet. Betik hatası varsa önce kodu düzelt, yeniden çalıştırma komutunu ver.
4. Ayrı bir commit oluştur; tam parent ve yeni commit SHA'sını bu günlüğün **Oturum kayıtları** bölümüne ekle. Kullanıcının göreceği komutlarda çalışma dizinini, dal güncellemesini ve gerekli parametreleri eksiksiz yaz.
5. Oturum kapanırken bu dosyayı repo dalında güncelle ve aynı içerikli Library kopyasını da güncelle. İki kopyanın SHA-256 değerlerini karşılaştır. Uyuşmazlık varsa repo kopyasını kaynak kabul edip farkı açıkça belirt. Yeni oturumda repo dosyası geçmişle birlikte okunmalı; Library kopyası yedektir.
6. Son yanıtta tamamlanan işler, doğrulanmış kanıt, açık engeller ve sonraki **tek somut adım** yer alsın. Bir otomasyon veya doğrulama yapılmadıysa yapıldı deme.

## Kaynak ve checkpoint zinciri

| SHA | İçerik | Kanıt / durum |
| --- | --- | --- |
| `080d42cb076a0efcc4902bbef7d9e42aae5550e3` | Motion Studio öncesi güvenilir üretim tabanı (`main`) | Üretime dokunulmuyor. |
| `978df231acd79394556ff21828ff2da405d4674b` | Bra Bas → rehber birinci → ikinci kol yolu geometri ekranı | 49 gerçek Blender örneğinde minimum frontal el aralığı `+0.00230378`; 34–40 arası en büyük normalize ön kol düşüşü `0.01763701`; en büyük playback eklem hatası `0.00000062`. Bu yalnızca kol geometrisi ekranıdır. |
| `dd650e8e539397c711414d8b5cdd10edaa2c3b8e` | Kol katalog kodu | 8 poz, 14 yönlü klip, 56 yönlü çift rotası. |
| `05a1cd9dca63492f785ba8401e7931f2181c7e3e` | Ayak katalog adayı ve Blender betiği | 8 poz, 14 yönlü klip taslağı; yerel testler geçti. Final Rig sonucu o commit'te doğrulanmamıştı. |
| `550a3fb7a7fc8cf11860736b518c66593e5e9620` | Ayak kalibrasyon anahtarı düzeltmesi | `upper_leg/lower_leg` hatalı anahtarları `thigh/shin` yapıldı; 66 yerel Python testi geçti. Düzeltme sonrası Blender çalıştırma raporu henüz görülmedi. |

## 2026-09-24 — Poz katalogları ve gerçek sonuç

1. Kılavuzdaki Bra Bas, birinci, ikinci, beşinci/taç, sağ/sol üçüncü ve sağ/sol dördüncü **kol** biçimleri için sekiz Action; bağlantıların iki yönünde 14 Action üretildi. Aradaki kılavuz yolu yalnızca Bra Bas → birinci → ikinci için daha önce ekranlanmış geometriyi kullanır. Dosyalar: `tools/motion_studio/guide_arm_catalog.py`, `tools/blender/motion_studio/guide_arm_catalog_batch_v0_7.py`.
2. Kullanıcının final Rig üzerinde ürettiği `build/motion_studio/guide_arm_catalog_v0_7/report.json` (Library dosyası: `report(20260924-185506).json`) **`CATALOG_FRONT_HAND_OVERLAP`** durumunda. `fifth_crown` statik frontal el aralığı `−0.04236233`; beş denenen taç genişliği `.12, .15, .18, .22, .26` boyunca hâlâ negatif. `first_to_fifth_crown` en kötü `−0.07300121` (örnek 14); ters yön `−0.07300162` (örnek 12). Rapordaki `front_overlap_names`: `fifth_crown`, `first_to_fifth_crown`, `fifth_crown_to_first`. Diğer kol pozları ve klipleri oluşturulmuş olsa da bu üçü temiz/bitmiş sayılmaz. El görüntüsündeki çakışmayı çözmek için poz hedefi ve geçiş yolunu yeniden ele al; gerçek render ve bütün kareler üzerinden yeniden ölç.
3. Beş ayak pozisyonunun sağ/sol ön varyantlarından oluşan sekiz aday, birinciden diğerlerine çift yönlü 14 hareket olarak kodlandı. Önce gerçek Blender çalışması `KeyError: 'left_upper_leg'` ile durdu; bu `550a3fb...` commit'iyle düzeltildi. **Düzeltme sonrası gerçek Blender raporu ve ayak görselleri elimizde yok.** Ayak basma/kayma, diz çizgisi, beden dengesi ve zeminin altına geçme başarıyla doğrulanmış değildir.
4. Kol ve ayak Action'ları ayrı kataloglarda; gövde, kollar ve ayakların eşzamanlı koreografisi henüz üretilmedi. 25 örnek / 24 fps bir tanılama ızgarasıdır; rehber veya video üzerinden ölçülmüş hareket süresi değildir. Godot için export henüz yok. Bale hocası değerlendirmesi bilerek sonraya bırakıldı.

## Sıradaki somut adımlar

1. Önce ayak betiğini `550a3fb...` veya daha yeni dal SHA'sından final Rig üzerinde çalıştırıp `build/motion_studio/guide_foot_catalog_v0_7/report.json` ve ön/yan görüntüleri incele. Hata varsa raporu ve traceback'i koruyarak düzelt; yalnızca yerel test geçti diye başarı ilan etme.
2. Taç kol pozundaki ölçülen frontal el çakışmasını ve iki geçişteki örnek 12–14 çevresindeki çakışmayı düzelt; bütün 25 kare ve statik taç için yeniden ölçüm yap. Ekteki gerçek kol raporunu başarısız ekran olarak koru.
3. İki katalog geçerliyse aynı Rig'de bütün bedenin uyumlu hareketini ve planlı geçişlerini üret; ayak teması, gövde/saç çarpışması, süre ve Godot içe aktarma ayrı kanıt kapılarıdır. Hoca değerlendirmesi sonradan yapılabilir.

## Windows tekrar çalıştırma

PowerShell'de:

```powershell
cd C:\Users\chodo\Documents\pas-de-run
git fetch origin motion-studio-v0-6-accepted-arm-visual-probe
git switch motion-studio-v0-6-accepted-arm-visual-probe
git merge --ff-only origin/motion-studio-v0-6-accepted-arm-visual-probe
git rev-parse HEAD
git status --short --branch

& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\guide_foot_catalog_batch_v0_7.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --output .\build\motion_studio\guide_foot_catalog_v0_7
```

Kol kataloğu tekrar gerektiğinde önkoşul yerel raporlarıyla birlikte tam komut `tools/motion_studio/README.md` içinde yer alır. Rapor JSON, Blender konsol çıktısı, görseller ve kullanılan tam `git rev-parse HEAD` bir sonraki kayda işlenmelidir.

## Her yeni oturumda eklenecek kayıt şablonu

```markdown
### YYYY-AA-GG — Kısa konu

- Başlangıç: dal, tam SHA, `git status --short --branch`; kullanılan kalibrasyon / kaynak GLB SHA.
- Amaç ve kullanıcının kararı: ...
- Adım 1: değişen dosyalar, gerekçe ve sonuç.
- Adım 2: çalıştırılan test/Blender komutu; gerçek `report.json` durumu ve sayısal bulgular.
- Görsel inceleme: hangi kareler, önden/yandan karar; yapılmadıysa açıkça belirt.
- Commit: parent tam SHA → yeni tam SHA; yayınlanan dal. Günlük commit'i için `git log -1 --format=%H -- MOTION_STUDIO_CHECKPOINT.md`.
- Açık sorunlar ve bir sonraki ilk komut: ...
- Library yedeği: eşit SHA-256 / farklılık nedeni.
```
