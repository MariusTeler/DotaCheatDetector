# Spike de parsare — rezultate

Parser testat: **gem-dota 0.14.0** (Python, publicat 2026-10-26).
Replay-uri reale folosite (din bucket-ul public de test al lui manta, singura sursă
accesibilă din mediul de dezvoltare — OpenDota și CDN-ul Valve sunt blocate aici):

| Match | Data aprox. | Durată | Timp parsare (gem.parse complet) |
|---|---|---|---|
| 8552595443 | 2025 (build recent) | ~39 min | 70 s |
| 7116386145 | 2023 (build vechi) | ~37 min | 56 s |

## Ce merge

| Cerință | Status | Detalii |
|---|---|---|
| Ordine jucători (unit orders) | ✅ | `DOTA_UM_SpectatorPlayerUnitOrders`: 81k ordine/meci, cu tick, tip, țintă (entity index), poziție, ability, queue, **ping și last_order_latency** per ordin. Necesită un hook mic peste `ReplayParser._dispatch_inner` (gem nu le expune public). |
| Mapare ordin → jucător | ✅ | `entindex` = player controller; maparea la erou se face prin `units`. |
| Poziții | ✅ | Per tick (doar la schimbare), din `CBodyComponent.m_cell*/m_vec*`; ~15–23k eșantioane/erou. |
| Cast-uri abilități / iteme | ✅ | Din combat log (ABILITY / ITEM) și din ordine (`ability_id` = entity index al abilității/itemului, rezolvabil prin entități). |
| Vizibilitate per echipă (fog) | ✅ pe replay recent / ❌ pe 2023 | `m_bNPCVisibleState` din `CDOTA_DataRadiant/Dire`. Pe replay-ul din 2023 toate stările sunt `UNKNOWN`. |
| Combat log | ✅ | DAMAGE, MODIFIER_ADD/REMOVE, DEATH, ABILITY, ITEM, PURCHASE etc., cu flag-uri `visible_radiant/dire`. |
| Cursor jucător | ⚠️ parțial | `CDOTAPlayerController.m_iCursor` se schimbă de ~20–27k ori/meci → poziția cursorului e în replay; unitatea/coordonatele trebuie calibrate. Poziția camerei NU am găsit-o (doar zoom). |

## Validarea vizibilității (8552595443)

* 4124 ordine pe eroi inamici vizibili, **41 pe eroi ascunși** (0,5–17 s de la ultima vizibilitate) într-un meci presupus normal → euristica (a) are nevoie de toleranță la latență și de filtre (vezi mai jos).
* Cross-check cu combat log: 673 evenimente de damage pe ținte „ascunse”; 97% sunt DoT-uri legitime (Death Rime, Searing Signet, Shrapnel, Battle Hunger), doar 10 sunt atacuri (proiectile deja în zbor). Bitset-ul e deci coerent.

Clarity (Java) și manta (Go) nu au fost necesare: gem acoperă tot ce trebuie și e cel mai ușor de livrat pe Windows (pip/PyInstaller).
