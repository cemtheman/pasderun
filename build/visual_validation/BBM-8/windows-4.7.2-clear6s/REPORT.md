# BBM-8 â€” scoped engineering PASS

Windows Godot **4.7.2 / Compatibility / Intel UHD Graphics** Ã¼zerinde gerÃ§ek gameplay lifecycle doÄŸrulandÄ±. Ã–nceki4.6.1 diagnostic renderer blocker kapatÄ±ldÄ±;360karelik eski teÅŸhis tekrarlanmadÄ±.

Mevcut tek motion controller Ã¼zerinden **entry2.4s â†’ accepted clear6s6s â†’ exit2.4s â†’ native dÃ¶nÃ¼ÅŸ â†’ gameplay/mÃ¼zik recovery** tamamlandÄ±. Entegrasyon opt-in, varsayÄ±lan kapalÄ±.

- 26/26 focused runtime testi PASS: duplicate, pause, cancel, reset, queued start, gerÃ§ek grounding loss ve native recovery dahil.
- 730gerÃ§ek runtime gÃ¶zlemi;647geometri Ã¶rneÄŸinde mevcut sÄ±nÄ±rlar iÃ§inde sÄ±fÄ±r hata.
- Gameplay/front/side/Ã¼Ã§ Ã§eyrek:488PNG tam decode/hash doÄŸrulamasÄ±;28panelin tÃ¼m temporal incelemesi ve bÃ¼yÃ¼k keyframe incelemesi PASS.
- Feature kapalÄ± canonical regresyon karÅŸÄ±laÅŸtÄ±rmasÄ±:120karede body/bone farkÄ±0, state/audio aynÄ±.

| Ã–lÃ§Ã¼m | En kÃ¶tÃ¼ | Mevcut sÄ±nÄ±r |
|---|---:|---:|
| Contact |0.002872|0.011715|
| Planted drift |0.003552|0.009762|
| Support margin |0.001243|>0|
| Knee/toe tracking |4.721Â°|6Â°|
| Trunk |8.889Â°|10Â°|
| Reconstruction |7.451e-6|1e-5|
| Root phase boundary |6.426e-5|1e-4|

BaÅŸarÄ±sÄ±z ara denemeler ayrÄ± klasÃ¶rlerde saklandÄ±; yalnÄ±z bu release klasÃ¶rÃ¼ PASS olarak seÃ§ildi. GÃ¶rsel deÄŸerlendirme ayrÄ±ntÄ±sÄ± review.md, Ã¶lÃ§Ã¼mler geometry_audit.json, kontrol sonuÃ§larÄ± focused_tests/runtime.json, kaynak/asset/executable hash baÄŸlarÄ± verification.json, tÃ¼m capture hashâ€™leri capture_manifest.json iÃ§indedir. lifecycle_front.gif gerÃ§ek PNG dizisinin10fps Ã¶nizlemesidir.

Canonical baÅŸlangÄ±Ã§: ee6da0dd58c026fdc0b2d5433192e36e2f4c0704. Yerel izole branch: work/bbm8-clear6s-windows-20261008. Worktree: C:\Users\chodo\Documents\Codex\2026-10-08\godot-ger-ek-renderer-do-ruland\work\bbm8. Ã–zgÃ¼n pas-de-run checkout branch/HEAD ve dÃ¶rt untracked kÃ¶kÃ¼ korundu. BBM-0â€“7, GLB, mevcut gate tanÄ±mlarÄ± ve accepted evidence deÄŸiÅŸmedi. Main merge/push/deploy yapÄ±lmadÄ±.

PASS kapsamÄ± bu READY-window entegrasyonu ve Ã¶lÃ§Ã¼len regresyondur.120kare karÅŸÄ±laÅŸtÄ±rmasÄ± tÃ¼m140s kurs sertifikasÄ± deÄŸildir; fixed-fps deterministik capture gerÃ§ek zamanlÄ± performans Ã¶lÃ§Ã¼mÃ¼ deÄŸildir. Ä°nsan sanatsal/Ã¶ÄŸretmen kabulÃ¼ yapÄ±lmadÄ±.

## Yeniden Ã¼retme

Godot console executable ile izole worktreeâ€™de: `--path <worktree> --rendering-method gl_compatibility --fixed-fps 60 --script res://tools/godot/bbm8_integration_harness.gd -- --mode=capture --output=<yeni-klasÃ¶r>`. Focused test iÃ§in `--mode=tests`. User-log/cache iÃ§in APPDATA yazÄ±labilir scratch klasÃ¶rÃ¼ne yÃ¶nlendirildi. Blender5.2 background geometry_audit yalnÄ±z gerÃ§ek gÃ¶zlemleri source skinâ€™e replay ederek Ã¶lÃ§er; Blender render Ã¼retmez.
