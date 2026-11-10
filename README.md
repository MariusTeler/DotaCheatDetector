# DotaCheatDetector

Analizează replay-uri Dota 2 (`.dem`) **după meci** și calculează pentru fiecare jucător un
**scor de suspiciune 0–100**, cu momentele exacte (MM:SS) care l-au generat, ca să le poți
verifica tu în replay.

> ⚠️ **Rezultatul NU este o dovadă și NU este un verdict „cheater / curat”.** Este un indicator
> statistic, calculat din euristici. Un scor mare înseamnă „merită să te uiți la aceste momente”,
> nimic mai mult. Un scor mic nu garantează că jucătorul e curat.

## Siguranță (VAC)

Programul lucrează **exclusiv pe fișiere de replay**:

* nu citește memoria procesului Dota 2, nu injectează nimic, nu se conectează la client;
* poate rula cu Dota închis. Singurele lucruri pe care le face sunt să citească fișiere `.dem`
  (inclusiv din folderul `...\steamapps\common\dota 2 beta\game\dota\replays`) și să descarce
  replay-uri prin OpenDota sau de pe serverele de replay Valve.

## Instalare pe Windows 11

### Varianta 1: executabil (recomandat)

1. Descarcă **[dotacheat-windows.zip](https://github.com/MariusTeler/DotaCheatDetector/releases/latest/download/dotacheat-windows.zip)**
   (pagina [Releases](https://github.com/MariusTeler/DotaCheatDetector/releases)). Zip-ul e
   construit și publicat automat de GitHub Actions la fiecare actualizare a codului. Sau
   construiește-l singur cu varianta 3.
2. Dezarhivează-l oriunde, de exemplu `C:\Tools\dotacheat\`.
3. Dublu-click pe `dotacheat.exe`. Se deschide în browser interfața locală
   (`http://127.0.0.1:8765`), unde lipești Match ID-ul.

### Varianta 2: din sursă, cu `run.bat`

1. Instalează [Python 3.11+](https://www.python.org/downloads/windows/) și bifează **Add python.exe to PATH**.
2. Descarcă repository-ul (Code → Download ZIP) și dezarhivează-l.
3. Dublu-click pe `run.bat`. La prima rulare își creează singur mediul `.venv` și instalează
   dependențele (~1 minut).

### Varianta 3: construiește tu executabilul

```bat
packaging\build_exe.bat
```

Rezultatul este `dist\dotacheat\dotacheat.exe`, ca un folder întreg pe care îl poți copia oriunde.

## Utilizare

### Interfață

```bat
dotacheat.exe            (sau: run.bat)
```

Lipești Match ID-ul și apeși **Analizează**, sau alegi un replay din folderul clientului. Durează
în jur de un minut pe meci (parsarea). La final apare un link către raport.

### Analiză automată după descărcarea din client

Descarci replay-ul din clientul Dota 2 (**Watch → Replays → Download**), iar analiza pornește
singură, fără Match ID. Ai două variante:

* **Interfața** (`dotacheat.exe`) urmărește automat folderul de replay-uri cât timp e deschisă.
  Fiecare replay nou apare în secțiunea „Analiză automată”, cu link spre raport.
* **`urmareste-replayuri.bat`**, din folderul aplicației, sau `dotacheat.exe watch`. Afișează
  sumarul în consolă și deschide raportul în browser pentru fiecare replay nou.

Programul doar verifică periodic folderul, la fiecare 3 s, și așteaptă ca fișierul să nu mai
crească ~6 s, adică să se termine descărcarea. Nu comunică în niciun fel cu clientul. Replay-urile
existente deja în folder sunt ignorate; pentru ele folosește `dotacheat.exe watch --existing`.
Pentru alt folder: `dotacheat.exe watch --folder "D:\replays"`.

### Linie de comandă

```bat
dotacheat.exe analyze --match 8552595443
dotacheat.exe analyze --file "C:\...\dota 2 beta\game\dota\replays\8552595443.dem"
dotacheat.exe analyze --match 8552595443 --config praguri.toml --open
dotacheat.exe folders          :: arată folderele de replay-uri găsite
dotacheat.exe watch            :: analizează automat fiecare replay nou descărcat
```

(Din sursă: `run.bat analyze --match ...` sau `python -m dotacheat analyze ...`.)

**De unde vine replay-ul pentru `--match`:**

1. din cache-ul local;
2. din folderul de replay-uri al clientului, dacă l-ai descărcat din joc. Folderul e găsit
   automat prin Steam / `libraryfolders.vdf`;
3. prin OpenDota: `replay_url`, adică cluster + `replay_salt`. Dacă OpenDota nu are încă
   salt-ul, programul trimite o cerere de parsare și așteaptă până la 5 minute.

Valve păstrează replay-urile pe servere aproximativ 2–3 săptămâni. Pentru meciuri mai vechi
trebuie să ai fișierul local. Arhivele `.dem.bz2` pot conține bzip2 sau Zstandard (formatul
actual); programul le recunoaște pe amândouă.

### Ce primești

| Fișier | Conținut |
|---|---|
| `match_<id>.html` | tabelul cu cei 10 jucători (erou, scor, motive principale) și, pentru fiecare jucător și fiecare euristică, lista momentelor suspecte (MM:SS + explicație), plus histograma timpilor de reacție |
| `match_<id>.json` | toate datele brute ale detecțiilor, metricile și configurația folosită |
| consolă | sumar scurt |

Rapoartele și cache-ul se salvează în `%LOCALAPPDATA%\DotaCheatDetector\`. Locul se poate schimba
cu `--out` / `--cache` sau cu variabila de mediu `DOTACHEAT_HOME`.

**Cum verifici un moment:** în clientul Dota 2 → Watch → Replays, deschizi meciul și derulezi la
ora din raport. Ora este ceasul din joc, deja corectat pentru pauze. Treci pe perspectiva
jucătorului respectiv.

## Euristici

Fiecare euristică e un modul separat în `dotacheat/heuristics/`. Toate pragurile sunt în
[`dotacheat/default_config.toml`](dotacheat/default_config.toml). Le poți suprascrie cu un
fișier propriu pasat prin `--config`, în care pui doar cheile pe care vrei să le schimbi.

| # | Euristică | Ce detectează | De ce e suspect |
|---|---|---|---|
| a1 | `fog_orders` (maphack) | ordine de atac / cast / urmărire pe un erou inamic care **nu era vizibil echipei** jucătorului în acel tick, mai mult decât poate explica latența (`0,5 s + ping` + încă `1 s`) | nu poți da click pe o unitate pe care echipa ta nu o vede; în meciurile curate de calibrare, aproape toate ordinele pe ținte ascunse au venit la ≤0,27 s după dispariția țintei (latență); a existat un singur caz izolat, sub pragul minim de 2 incidente |
| a2 | `fog_reactions` | retragere / întoarcere exact când un erou inamic **invizibil** vine spre jucător, comparat cu un control: inamic invizibil la fel de aproape, dar care nu vine spre el | reacții repetate la informație pe care nu o ai. Testul folosește o distribuție binomială, p ≤ 0,002 |
| b | `reaction_time` | timpul dintre o amenințare vizibilă (Hook, Arrow, Hex, Duel, Blink, inamic ieșit din ceață…) și răspunsul defensiv (Blink, BKB, Manta, Eul, Force, TP, Shadow Dance…), minus ping-ul | reacție umană tipică 200–300 ms; se evaluează **distribuția pe meci**, iar rata de reacții „rapide” se compară cu cea din întâmplare |
| c | `scripts` | aceeași secvență de abilități/iteme repetată de ≥3 ori cu intervale identice la nivel de tick (deviație standard ≤ 0,5 tick-uri), plus ≥3 abilități diferite în același tick | un om variază cu câteva tick-uri (33 ms) de la o execuție la alta |
| d1 | `lasthits` | variația relativă (CV) a timpului dintre ultimul ordin de atac și moartea creep-ului, pe ≥25 de last hit-uri | scripturile de last hit dau timing aproape constant. Jucătorii pro calibrați au CV ≥ 0,26 |
| d2 | `dodges` | eschivări laterale rapide ale skillshot-urilor (Hook, Arrow, Powershot…) care ratează, comparate cu rata din întâmplare | auto-dodge |
| e | `cursor` | ordine pe eroi inamici aflați departe (≥1800 unități) de punctul de sub cursor, cu camera nemișcată | ordinul nu a venit dintr-un click pe acea unitate (script) sau ținta nu era pe ecran |

### Detalii care evită fals-pozitivele

* **Vizibilitatea** vine din bitset-urile autoritative per echipă din replay
  (`m_bNPCVisibleState` din `CDOTA_DataRadiant/Dire`). Acestea includ deja ward-urile, viziunea
  aliaților și dezvăluirile din abilități. Am verificat bitset-ul cu combat log-ul: 97% din daunele
  pe ținte „ascunse” sunt DoT-uri (Death Rime, Searing Signet, Shrapnel…), care lovesc legitim
  în ceață.
* **Timp de reacție:**
  * contează doar comenzile care **chiar au reușit** (confirmate în combat log); apăsările
    repetate pe cooldown sau în timpul unui stun sunt ignorate;
  * un răspuns sosit în același tick cu amenințarea sau mai devreme de un ping dus-întors **nu e
    o reacție** (acțiune simultană sau chiar propriul Blink care dezvăluie inamicul);
  * „din întâmplare” se măsoară pentru fiecare cast în parte: același cast mutat cu ±0,5–3 s, cât
    de des ar părea rapid? În lupte amenințările sunt dese, deci șansa e mare. Contează doar
    excesul față de ea, testat cu distribuția Poisson (p ≤ 0,002);
  * interpolarea clientului nu se scade, deci timpii sunt supraestimați, în favoarea jucătorului.
* **Combo-uri:** ordinele „ținute” de motor până se termină cast point-ul anterior, de exemplu
  Wall of Replica apăsat în timpul Vacuum, au timing-ul jocului, nu al jucătorului, și sunt
  excluse. Sunt ignorate și sub-abilitățile declanșate împreună de joc: orbii lui Invoker,
  cântecele lui Largo, crafting-ul de iteme neutre etc.
* **Cursor:** replay-ul conține cursorul în coordonate de ecran (`m_iCursor`, ~512×384), nu poziția
  camerei. Maparea ecran→lume se calibrează pe fiecare jucător din perechi de click-uri apropiate.
  Eroarea mediană e ~20 de unități. Un ordin se evaluează doar când click-urile dinainte și de
  după arată aceeași cameră, iar zonele de minimap/HUD sunt excluse.

## Scorul 0–100

Fiecare euristică dă un sub-scor `s ∈ [0,1]` per jucător, **deja normalizat** la frecvența
evenimentelor: rate pe oră sau proporții din oportunități. Un meci de 70 de minute nu e
automat mai suspect. Combinarea e un „noisy-OR” ponderat:

```
scor = 100 · (1 − Π (1 − w_h · s_h))
```

Ponderile implicite (`[scoring.weights]`) sunt: maphack 0,85 · timp de reacție 0,60 · scripturi
0,60 · cursor 0,50 · reacții din ceață 0,45 · eschivări 0,40 · last hit 0,25.

Un singur semnal foarte puternic poate urca scorul singur, iar semnalele slabe se adună fără să
treacă de 100. Raportul arată câte puncte a adus fiecare euristică.

| Scor | Etichetă |
|---|---|
| 0–9 | nimic notabil |
| 10–29 | suspiciune scăzută |
| 30–59 | suspiciune moderată |
| ≥ 60 | suspiciune ridicată |

## Calibrare (noiembrie 2026)

Testat pe 14 replay-uri reale, 13 dintre ele de pe patch-ul curent:

* 10 meciuri profesioniste: DreamLeague Div. 2, 1win Essence;
* 3 pub-uri;
* 1 meci din 2025.

| | Rezultat |
|---|---|
| 140 de jucători din meciuri presupuse curate | mediana 0, p99 0, maxim **3,1** (Enigma, CV last hit 0,26). Niciun jucător ≥ 10. |
| Cheat **simulat** (`tools/simulate_cheater.py`) injectat într-un pub real | maphack singur **85**, reacții de 60 ms singure **53**, combo script singur **39**, toate trei **95**. Ceilalți 9 jucători: 0. |

Limitele calibrării:

* **Pragurile au fost reglate pe aceleași meciuri** pe care le-am testat. Pentru o estimare
  cinstită a fals-pozitivelor trebuie rulat pe meciuri noi:
  ```bat
  python tools\calibrate.py <folder-cu-dem>
  ```
* Nu am avut replay-uri cu cheateri confirmați (conturi banate ulterior). Simularea arată că
  euristicile reacționează la tiparele pe care le caută, nu că un cheat real produce exact aceste
  tipare. Cheat-urile „umanizate” (întârzieri aleatorii, maphack folosit doar pentru decizii fără
  click-uri pe ținte invizibile) pot trece nedetectate.

## Limitări

* **Nu este o dovadă.** Euristicile pot greși în ambele sensuri.
* **Informație legitimă din afara vizibilității:** sunete ale abilităților în ceață, ping-uri și
  voice de la coechipieri, experiența (inamicul „trebuie” să fie acolo), TP-uri vizibile pe
  minimap, Smoke anunțat etc. De aceea a2 cere un tipar repetat și semnificativ statistic.
* **Replay-uri vechi:** unele nu au datele de vizibilitate per echipă (de exemplu un replay din
  2023 testat; cel din 2025 le avea), deci
  euristicile de ceață și reacție sunt dezactivate și raportul spune asta. Replay-urile Source 1
  (pre-2015) nu sunt suportate.
* **Patch-uri noi:** formatul replay-urilor se schimbă. Parserul (gem-dota) e fixat la o versiune
  testată și se poate actualiza în `pyproject.toml`.
* **Timpii sunt la rezoluția serverului** (30 tick/s = 33 ms), iar ping-ul este cel raportat de
  client în fiecare ordin.
* Listele de abilități (amenințări, răspunsuri defensive, skillshot-uri) sunt în
  `dotacheat/gamedata.py`. Sunt incomplete și ușor de extins.
* Euristica de cursor nu poate fi evaluată pentru jucătorii care mișcă des camera sau folosesc
  mult minimap-ul. În acest caz apare ca „nu a putut fi calibrat”.

## Dezvoltare

```bash
pip install -e .[dev]
pytest                                   # teste unitare pe date sintetice (toate euristicile)
python tools/calibrate.py <folder>       # distribuția scorurilor pe un set de replay-uri
python tools/simulate_cheater.py x.dem --pid 3 --kinds maphack,reaction,script
```

Structură:

```
dotacheat/
  cli.py            analyze --match / --file, watch, gui, folders
  watch.py          urmărirea folderului de replay-uri (analiză automată)
  fetch.py          folder local Steam, OpenDota, download, bz2/zstd
  extract.py        o singură parsare (gem-dota + hook pe unit orders) → MatchData, cache .mdata.gz
  model.py          MatchData, ordine, vizibilitate, poziții, ceas cu pauze
  heuristics/       câte un modul per euristică + base.py + registry.py
  scoring.py        noisy-OR ponderat
  report/           HTML, JSON, consolă
  web.py            interfața locală (stdlib, doar 127.0.0.1)
  default_config.toml
spike/              spike-ul inițial de evaluare a parserului (SPIKE.md)
tools/              calibrare, simulare
packaging/          PyInstaller (.spec, build_exe.bat)
tests/
```

Parser: [gem-dota](https://pypi.org/project/gem-dota/) (Python). Datele de meci vin din
[OpenDota API](https://docs.opendota.com/).
