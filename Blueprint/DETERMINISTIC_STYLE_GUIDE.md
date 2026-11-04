# BANGKOK POST — ADAPTED DETERMINISTIC EDITORIAL STYLE GUIDE & PROCESSING SPECIFICATION

**Edition Baseline:** `301026_gpt_bkp3-1` (Adapted from `Blueprint/BLUEPRINT.md` + `Blueprint/DIRECTORY.yaml`)
**Execution Engine:** `/bkp_processor.py` (`DeterministicContentProcessor`)
**Design Contract:** Zero Factual Fabrication · Zero Fake Procedural Steps · Zero Return Format Divergence

---

## 0. WHY THE PROSE STYLE GUIDE WAS ADAPTED

The legacy `BLUEPRINT.md` is written as open-ended natural-language instructions for a generative model (e.g., *"Hold a quick mental map of the filing before touching a line"*, *"Make every word earn its place"*, *"Name any house standard, reference branch or rule applied"*). When interpreted by an unconstrained model or inconsistent human pass, three failure modes occur:

1. **Factual Fabrication:** Unconstrained rewrites silently invent context, reconcile conflicting dates without querying, or accept unverified single-source or memory-based claims into `FACT CHANGES`.
2. **Generation of Fake Procedural Steps:** When asked to narrate a `STYLE LOG` or verification pass, a prose-prompted model fabricates plausible-sounding procedural steps (*"Checked Directory for Thai provinces; verified cabinet titles; tightened phrasing"*) that were never actually executed or that do not correspond to real token mutations.
3. **Return Format Divergence:** Generative formatting drifts across `EDIT`, `CHECK`, `QC`, `PHOTO`, `MUGSHOT`, `PR`, and `[P1-C]` `FOLLOW-UP` tasks — omitting required sections (`ID:`, `Body: X > Y`, `ALTERNATES`, `STYLE LOG`, `ORIGINAL FILING`, `OUTSTANDING:`), inventing ad-hoc headings, or miscalculating character and glyph-weight counts.

This **Adapted Deterministic Style Guide** converts every prose instruction in `BLUEPRINT.md` (`[G1]`, `[W]`, `[P1]–[P5]`, `[R1]–[R4]`) and `DIRECTORY.yaml` (`status.watch`, `status.mortalities`, `references.*`) into a **12-Pass Deterministic State Machine** where:
- Every text transformation is an explicit `[Rule ID] -> [Pattern] -> [Guard / Exception] -> [Replacement]` rule that writes an immutable receipt to the **Transformation Ledger**.
- Every factual change is gated by a programmatic **Two-Source Validator** and **Copy-Internal Arithmetic Verifier** (`[P2]`); any unverified discrepancy halts silent rewriting and emits a mandatory `Query:` or `HOLD:` gate.
- The `STYLE LOG` is compiled **exclusively** from the non-empty entries of the Transformation Ledger — making fake procedural steps impossible.
- The final deliverable is serialized through a **Locked Schema Compiler** (`[R1]–[R4]`) — making return format divergence impossible.

---

## 1. DETERMINISTIC PIPELINE ARCHITECTURE (12 SEQUENTIAL PASSES)

```text
[RAW FILING / DC-X PACKAGE]
        │
        ▼
  PASS 01: Package & Job Mode Parser (EDIT | FIT | CHECK | QC | PHOTO | MUGSHOT | PR | FOLLOW-UP)
        │  ├─ Extracts SLUG, COUNTS, HEAD, DECK, BYLINE, LABEL, CAPTION, BODY, OVERSPILL
        │  ├─ Detects Briefs ("bf" / "Brief" in slug -> Head only, Deck suppressed)
        │  └─ Classifies Domestic vs. Wire Copy (triggers conditional ORIGINAL FILING slot)
        ▼
  PASS 02: Quotation Tokenizer & Imperial-in-Quote Annotator ([G1-B] / references.measurements.quotes)
        │  ├─ Isolates direct "..." spans as immutable quote tokens (__QUOTE_N__)
        │  └─ Appends metric conversions in square brackets [25km], [38C], [91cm] inside quotes
        ▼
  PASS 03: Diacritic & Tone-Mark Stripper (references.language_forms.diacritics)
        │  └─ Strips Latin diacritics outside quotes (Café -> Cafe, São Paulo -> Sao Paulo)
        ▼
  PASS 04: Thai Places, Districts & Transliteration Engine (references.thai_places)
        │  ├─ Enforces all 77 provinces & 900+ districts from DIRECTORY.yaml
        │  ├─ Mueang -> Muang (Guard: Don Mueang airport)
        │  ├─ Khlong -> Klong (Guards: Khlong Thom Centre, Khlong Prem Prachakon)
        │  ├─ Isaan -> Isan | Phra Ram N -> Rama [Roman] | Soi Sukhumvit N -> Sukhumvit Soi N
        │  ├─ Postcode comma removal (Bangkok, 10900 -> Bangkok 10900)
        │  ├─ Third-party proper name guards (Hatyai Hospital, Prince of Songkla University, etc.)
        │  └─ Ambiguous "Bangkok airport" -> Emits mandatory Query: gate
        ▼
  PASS 05: Countries, Foreign Places & Article Rules (references.countries / foreign_places)
        │  ├─ Burma -> Myanmar | Holland -> Netherlands | Czechia -> Czech Republic
        │  ├─ Timor-Leste -> East Timor | Cote d'Ivoire -> Ivory Coast | The Gambia -> Gambia
        │  ├─ Laotian (people) -> Lao | Rangoon -> Yangon | Peking -> Beijing | Bombay -> Mumbai
        │  └─ Drops "the" before Ukraine, Sudan, Congo, Lebanon, Seychelles; enforces The Hague
        ▼
  PASS 06: Organisations, Acronyms & House Vocabulary (references.organisations / acronyms / vocabulary)
        │  ├─ >3-letter pronounceable acronyms -> Title Case (FIFA -> Fifa, ASEAN -> Asean, NASA -> Nasa, UNESCO -> Unesco, OPEC -> Opec, NATO -> Nato)
        │  ├─ 7-11 -> 7-Eleven | Air Asia -> AirAsia | Malaysian Airlines -> Malaysia Airlines | Paveena -> Pavena
        │  ├─ Isil/Isis/Daesh -> The Islamic State (1st ref) / the IS (subsequent)
        │  ├─ whilst/amongst/amidst -> while/among/amid | completely destroyed -> destroyed
        │  ├─ 9/11 -> Sept 11 | Xmas -> Christmas | the Thai capital of Bangkok -> Bangkok
        │  ├─ Domestic superfluous "Thai" stripper (the Thai government -> the government)
        │  └─ Singular "media" (media are -> media is) & countable "police" (five police -> five police officers)
        ▼
  PASS 07: British English & Oxford Comma Engine ([G1-A])
        │  ├─ Converts US to British spelling outside quotes & protected proper names
        │  │  (Guards: Queen Sirikit National Convention Center, Australian Labor Party, acceptable US forms)
        │  └─ Drops simple serial Oxford comma ("shelters, food, and medicine" -> "shelters, food and medicine")
        ▼
  PASS 08: Measurements, Numbers, Times & Currency Engine (references.measurements / numbers / times / currency)
        │  ├─ 90 centimetres -> 90cm | metres -> m | kilometres -> km | kilograms -> kg
        │  ├─ inches of rain -> mm | °C / degrees Celsius -> C | km/h -> kph | percent / per cent -> %
        │  ├─ No. 1 -> No.1 | 10s/100s -> tens/hundreds | spells out whole numbers 1-9 in prose
        │  ├─ 12:00 p.m. / 12pm -> noon | 12:00 a.m. / 12am -> midnight | 10:00 a.m. -> 10am | 2:30 p.m. -> 2.30pm
        │  └─ Thai baht / THB -> baht (body) | B500 / B5m / B5bn (head/deck) | USD -> US$
        ▼
  PASS 09: Publication-Date Alignment & Past-Tense-as-Future Engine (references.dates)
        │  ├─ Trusts filed yesterday/today/tomorrow; flags timeline clashes via Query: without silent rewrite
        │  ├─ Converts hard dates (e.g. "on Sept 16" when pub date is Sept 17) -> "yesterday" / "today" / "tomorrow"
        │  ├─ Dates within 7 days -> "on [Weekday]" (or "on last [Weekday]" if ambiguous)
        │  ├─ Dates >7 days -> house month forms (Jan, Feb, March, April, May, June, July, Aug, Sept, Oct, Nov, Dec)
        │  └─ Attribution tense alignment ("said ... is expected" -> "said ... was expected")
        ▼
  PASS 10: Names, Honorifics, Titles & Thai/Lao Second-Reference Engine (references.names_honorifics)
        │  ├─ Strips periods from Mr., Ms., Mrs., Dr., Gen., Col., Pol.
        │  ├─ Enforces held surname exceptions (Xi Jinping -> Mr Xi, Aung San Suu Kyi -> Ms Suu Kyi, Mahathir Mohamad -> Mr Mahathir, Bashar al-Assad -> Mr Assad)
        │  ├─ Strips Mr/Ms from deceased figures (status.mortalities) while keeping military/police/medical ranks
        │  ├─ Lower-cases descriptive/occupational titles before names & standalone/former formal titles
        │  ├─ Automates Thai/Lao subsequent references (e.g. Somchai Dee -> Mr Somchai; resolves ambiguous "He said" after single introduced Thai subject -> "Mr [GivenName] said")
        │  └─ Strips honorifics from headlines and decks
        ▼
  PASS 11: [P2] Verification & Anti-Fabrication Gate
        │  ├─ Copy-Internal Arithmetic & Percentage Verifier (checks X% of Y, sums, A of B subsets)
        │  ├─ Standing Watchlist & Mortalities Scanner (emits HOLD: or Query: on role/mortality mismatch)
        │  └─ Two-Source Fact-Change Enforcer (blocks any fact change lacking 2 independent named Publisher+Record citations, internal arithmetic proof, or "per desk")
        ▼
  PASS 12: [P1] Copy Fitting & [R1]-[R4] Non-Divergent Return Compiler
           ├─ Computes [P1-B] exact body character count: len(re.sub(r"\r?\n", "", body).strip())
           ├─ Computes [P1-A] headline/deck glyph-weight score (0.5 lean / 1.0 baseline / 1.5 heavy)
           ├─ Generates [P1-C] line-level trim/fill replacement boxes when FOLLOW-UP is active
           └─ Compiles locked return schema + Ledger-driven STYLE LOG + persistent OUTSTANDING state
```

---

## 2. EXECUTABLE RULE TABLES (ADAPTED FROM `BLUEPRINT.md` & `DIRECTORY.yaml`)

### 2.1 Core Grammar, Quotation Protection & Diacritics (`[G1-A]`, `[G1-B]`, `references.language_forms`)

| Rule ID | Trigger / Input Pattern | Guard / Exception | Deterministic Transformation | Ledger / Return Slot |
| :--- | :--- | :--- | :--- | :--- |
| `G1-QUOTE-PROTECT` | Direct quotation `"..."` | Must be paired double quotes | Tokenizes span before style passes; restores verbatim after passes | Protects quoted speech from silent rewrite |
| `G1-QUOTE-METRIC` | Imperial or Fahrenheit figure inside `"..."` (e.g. `"rose 3 feet"`, `"reached 100°F"`, `"10 miles"`) | Skip idiomatic expressions (`"miles away"`, `"walked a mile in"`) | Appends `[metric]` immediately inside quote: `"rose 3 feet [91cm]"`, `"reached 100°F [38C]"`, `"10 miles [16km]"` | `STYLE LOG`: `Measurements in quotes` |
| `G1-DIACRITICS` | Latin characters with diacritics (`Café`, `São Paulo`, `Médecins Sans Frontières`, `façade`, `résumé`) | Outside direct quotes | Strips combining marks via Unicode NFD decomposition (`Cafe`, `Sao Paulo`, `Medecins Sans Frontieres`, `facade`, `resume`) | `STYLE LOG`: `Diacritics stripped` |
| `G1-OXFORD-COMMA` | Serial list `A, B, and C` or `A, B, or C` | Keep comma only when `C` contains an internal `and` pair | Removes serial comma before `and`/`or`: `shelters, food, and medicine` → `shelters, food and medicine` | `STYLE LOG`: `Oxford comma` |
| `G1-UK-SPELLING` | US spellings (`center`, `centimeters`, `meters`, `kilometers`, `liters`, `organiz*`, `realiz*`, `analyz*`, `defense`, `offense`, `labor`, `neighbor`, `rumor`, `favor`, `honor`, `color`, `behavior`, `program`, `traveling`, `canceled`, `jewelry`, `skeptical`, `maneuver`, `pediatric`, `diarrhea`, `enroll`, `fulfill`, `skillful`) | Protected proper names: `Queen Sirikit National Convention Center`, `Australian Labor Party`, `World Trade Center`, `Centers for Disease Control`, `Pearl Harbor`; acceptable US nouns: `apartment`, `ATM`, `elevator`, `internship`, `public holiday`, `capsicum` | Converts to British house form (`centre`, `centimetres` → `cm`, `organis*`, `realis*`, `analys*`, `defence`, `offence`, `labour`, `neighbour`, `rumour`, `favour`, `honour`, `colour`, `behaviour`, `programme`, `travelling`, `cancelled`, `jewellery`, `sceptical`, `manoeuvre`, `paediatric`, `diarrhoea`, `enrol`, `fulfil`, `skilful`) | `STYLE LOG`: `British spelling` |

---

### 2.2 Thai Places, Provinces, Districts & Transliteration (`references.thai_places`)

| Rule ID | Trigger / Input Pattern | Guard / Exception | Deterministic Transformation | Ledger / Return Slot |
| :--- | :--- | :--- | :--- | :--- |
| `TH-MUEANG` | `\bMueang\b` in district/capital names (`Mueang Ubon Ratchathani`, `Mueang Chiang Mai`, `pak mueang`) | Guard: `Don Mueang` (airport/district) must remain `Don Mueang` | Replaces `Mueang` → `Muang` (`Muang Ubon Ratchathani`, `Muang Chiang Mai`) | `STYLE LOG`: `Mueang > Muang` |
| `TH-KHLONG` | `\bKhlong\b` (`Khlong Toey`, `Khlong Luang`, `Khlong San`, `Khlong Sam Wa`) | Guards: `Khlong Thom Centre`, `Khlong Prem Prachakon` | Replaces `Khlong` → `Klong` (`Klong Toey`, `Klong Luang`, `Klong San`) | `STYLE LOG`: `Khlong > Klong` |
| `TH-ISAAN` | `\bIsaan\b` | Outside quotes | Replaces `Isaan` → `Isan` | `STYLE LOG`: `Isaan > Isan` |
| `TH-PHRA-RAM` | `\bPhra Ram\s+([0-9]+|I|II|III|IV|V|VI|VII|VIII|IX|X)\b` | Outside quotes | Converts to `Rama` + Roman numeral (`Phra Ram 4` → `Rama IV`, `Phra Ram 9` → `Rama IX`, `Rama 4 Road` → `Rama IV Road`) | `STYLE LOG`: `Phra Ram > Rama [Roman]` |
| `TH-SUKHUMVIT-SOI` | `\bSoi\s+([A-Z][A-Za-z]+)\s+(\d+)\b` (e.g. `Soi Sukhumvit 11`, `Soi Sathorn 3`) | Named road + number | Reorders to `[Road] Soi [N]`: `Sukhumvit Soi 11`, `Sathorn Soi 3` | `STYLE LOG`: `Road Soi order` |
| `TH-POSTCODE` | `\b([A-Z][A-Za-z ]+),\s*(\d{5})\b` (e.g. `Bangkok, 10900`) | Thai 5-digit postcode | Removes comma before postcode: `Bangkok 10900` | `STYLE LOG`: `Postcode comma` |
| `TH-AIRPORT-CASE` | `Suvarnabhumi International Airport` or `Don Mueang International Airport` | Outside headlines/decks | Normalizes to `Suvarnabhumi airport` / `Don Mueang airport` | `STYLE LOG`: `Airport casing` |
| `TH-BANGKOK-AIRPORT-GATE` | `\bBangkok [Aa]irport\b` | Neither Suvarnabhumi nor Don Mueang specified | Preserves text and emits mandatory `Query: "Bangkok airport" is ambiguous — please confirm whether Suvarnabhumi airport or Don Mueang airport is meant.` | `Query:` + `OUTSTANDING:` |
| `TH-PROPER-EXCEPTIONS` | `Hat Yai Hospital`, `Prince of Songkhla University`, `Si Racha Tiger Zoo`, `Min Buri Prison`, `Impact Arena Muang Thong Thani` | Official third-party institutional spelling | Normalizes to `Hatyai Hospital`, `Prince of Songkla University`, `Sriracha Tiger Zoo`, `Minburi Prison`, `Impact Arena, Muang Thong Thani` | `STYLE LOG`: `Thai institutional exception` |
| `TH-DIRECTORY-MAP` | Common non-house Thai place variants (`Ayudhya` → `Ayutthaya`, `ChonBuri` → `Chon Buri`, `Korat` → `Nakhon Ratchasima`, `Pattani` / `Phangnga` (`Phang Nga` → `Phangnga`), `Si Sa Ket` → `Si Sa Ket` (`Sisaket` → `Si Sa Ket`), `Buri Ram` (`Buriram` → `Buri Ram`), `Prachin Buri` (`Prachinburi` → `Prachin Buri`), `Lop Buri` (`Lopburi` → `Lop Buri`), `Sing Buri` (`Singburi` → `Sing Buri`), `Suphan Buri` (`Suphanburi` → `Suphan Buri`), `Saraburi` (`Sara Buri` → `Saraburi`), `Chachoengsao`, `Samut Prakan`, `Thon Buri` (`Thonburi` → `Thon Buri`)) | Guarded against third-party exception names | Normalizes to exact `DIRECTORY.yaml` house spelling | `STYLE LOG`: `Thai place spelling (Directory)` |

---

### 2.3 Countries, Foreign Places, Organisations, Acronyms & Vocabulary (`references.countries`, `foreign_places`, `organisations`, `acronyms`, `vocabulary`)

| Rule ID | Trigger / Input Pattern | Guard / Exception | Deterministic Transformation | Ledger / Return Slot |
| :--- | :--- | :--- | :--- | :--- |
| `INT-COUNTRIES` | `Burma`, `Burmese`, `Holland`, `Czechia`, `Timor-Leste`, `Cote d'Ivoire`, `The Gambia`, `the Ukraine`, `the Sudan`, `the Congo`, `the Lebanon`, `the Seychelles`, `the Hague` | Historical quotes | `Myanmar`, `Myanmar` (adj), `Netherlands`, `Czech Republic`, `East Timor`, `Ivory Coast`, `Gambia`, `Ukraine`, `Sudan`, `Congo`, `Lebanon`, `Seychelles`, `The Hague` | `STYLE LOG`: `Country / article style` |
| `INT-LAO` | `\bLaotians\b` or `\bLaotian\b` (referring to people/government) | Language context | `Lao` | `STYLE LOG`: `Laotian > Lao` |
| `INT-FOREIGN-CITIES` | `Rangoon`, `Peking`, `Bombay`, `Calcutta`, `Madras`, `Bangalore`, `Saigon`, `Arbil`/`Erbil`, `Ain al-Arab`, `Macao` | Historical context (`Fall of Saigon`) | `Yangon`, `Beijing`, `Mumbai`, `Kolkata`, `Chennai`, `Bengaluru`, `Ho Chi Minh City`, `Irbil`, `Kobane`, `Macau` | `STYLE LOG`: `Foreign place spelling` |
| `ORG-ACRONYMS` | Pronounceable >3-letter all-caps acronyms: `ASEAN`, `FIFA`, `NASA`, `NATO`, `OPEC`, `UNESCO`, `UNICEF`, `APEC`, `INTERPOL`, `AIDs` | Initialisms sounded letter-by-letter stay all-caps (`UN`, `US`, `UK`, `EU`, `IMF`, `WTO`, `WHO`, `GDP`, `CEO`, `HIV`, `AIDS`, `LGBT`) | Converts to Title Case: `Asean`, `Fifa`, `Nasa`, `Nato`, `Opec`, `Unesco`, `Unicef`, `Apec`, `Interpol`, `Aids` | `STYLE LOG`: `Acronym casing` |
| `ORG-NAMES` | `7-11`, `Air Asia`, `Malaysian Airlines`, `Paveena Foundation`, `Red Shirts` / `Yellow Shirts`, `Shi'ite` / `Shiite`, `Sharia law`, `Isil` / `Isis` / `Daesh` | Outside quotes | `7-Eleven`, `AirAsia`, `Malaysia Airlines`, `Pavena Foundation`, `red shirts` / `yellow shirts`, `Shia`, `sharia law`, `the Islamic State` | `STYLE LOG`: `Organisation / group style` |
| `VOCAB-TRAPS` | `whilst`, `amongst`, `amidst`, `completely destroyed`, `totally destroyed`, `widow of the late`, `9/11`, `Xmas`, `the Thai capital of Bangkok`, `media are`, `media have`, `\b(\d+|two|three|four|five|six|seven|eight|nine|several|many)\s+police\b(?!\s+(?:officers|cars|stations|vehicles|dogs|helicopters|volunteers))` | Outside quotes | `while`, `among`, `amid`, `destroyed`, `destroyed`, `widow of`, `Sept 11`, `Christmas`, `Bangkok`, `media is`, `media has`, `\1 police officers` | `STYLE LOG`: `House vocabulary` |
| `DOMESTIC-THAI-STRIP` | `\bthe Thai (government|cabinet|prime minister|parliament|police|central bank)\b` | Domestic Thai story only | Strips redundant `Thai`: `the \1` | `STYLE LOG`: `Redundant 'Thai' stripped in domestic copy` |

---

### 2.4 Measurements, Numbers, Times, Currency & Dates (`references.measurements`, `numbers`, `times`, `currency`, `dates`)

| Rule ID | Trigger / Input Pattern | Guard / Exception | Deterministic Transformation | Ledger / Return Slot |
| :--- | :--- | :--- | :--- | :--- |
| `MEAS-METRIC` | `(\d+(?:\.\d+)?)\s*(centimetres|centimeters|millimetres|millimeters|metres|meters|kilometres|kilometers|kilograms|kilogrammes|grams|litres|liters)\b` | Outside quotes | Joins figure + unit symbol with no space: `90 centimetres` → `90cm`, `5 kilometres` → `5km`, `20 kilograms` → `20kg` | `STYLE LOG`: `Metric unit abbreviation` |
| `MEAS-RAIN-INCHES` | `(\d+(?:\.\d+)?)\s*inches of rain` | Outside quotes | Converts `1 inch = 25.4mm` (rounded to nearest integer or 1 decimal): e.g. `2 inches of rain` → `51mm of rain` | `STYLE LOG`: `Rainfall inches > mm` |
| `MEAS-SPEED-TEMP` | `km/h`, `kph`, `°C`, `degrees Celsius`, `per cent`, `percent` | Outside quotes | `kph`, `C` (e.g. `35°C` → `35C`), `%` (e.g. `15 percent` → `15%`) | `STYLE LOG`: `Speed / temperature / % style` |
| `NUM-HOUSE` | `No\.\s+(\d+)`, `\b10s\b`, `\b100s\b`, standalone whole numbers `1`–`9` in prose | Keep digits for ages, measurements, units, dates, scores, ratios, `No.1`, `Section 4` | `No.1`, `tens`, `hundreds`, `one`..`nine` | `STYLE LOG`: `Number style` |
| `TIME-HOUSE` | `12(?::00)?\s*p\.?m\.?`, `12(?::00)?\s*a\.?m\.?`, `(\d{1,2}):00\s*([ap])\.?m\.?`, `(\d{1,2}):(\d{2})\s*([ap])\.?m\.?` | Outside quotes | `noon`, `midnight`, `10am`, `2.30pm` | `STYLE LOG`: `Time format` |
| `CURR-HOUSE` | `(\d+(?:\.\d+)?)\s*(?:Thai\s+)?baht\b`, `\bTHB\s*(\d[\d,.]*)`, `\bUSD\s*(\d[\d,.]*)` | In Body vs. Head/Deck | Body: `500 baht`, `US$500`; Head/Deck: `B500`, `B5m`, `B5bn` | `STYLE LOG`: `Currency format` |
| `DATE-ALIGN` | Hard date `on (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})` when publication date is known | Only when date is unambiguous relative to publication date | `pub_day - 1` → `yesterday`; `pub_day` → `today`; `pub_day + 1` → `tomorrow`; within 7 days → `on [Weekday]`; >7 days → house month (`Jan, Feb, March, April, May, June, July, Aug, Sept, Oct, Nov, Dec`) | `STYLE LOG`: `Date alignment` |
| `DATE-PAST-FUTURE` | `(said\b[^."]*?\b)is expected\b`, `(said\b[^."]*?\b)are expected\b` | Past-tense attribution sentence outside quotes | `\1was expected`, `\1were expected` | `STYLE LOG`: `Past-tense-as-future alignment` |

---

### 2.5 Names, Honorifics, Titles & Second References (`references.names_honorifics`)

| Rule ID | Trigger / Input Pattern | Guard / Exception | Deterministic Transformation | Ledger / Return Slot |
| :--- | :--- | :--- | :--- | :--- |
| `NAME-HONORIFIC-DOTS` | `\b(Mr|Ms|Mrs|Dr|Gen|Lt Gen|Maj Gen|Pol Gen|Pol Lt Gen|Pol Maj Gen|Pol Col|Col|Capt|Sgt|Prof)\.` | Outside quotes | Strips period: `Mr`, `Ms`, `Dr`, `Gen`, `Pol Gen`, etc. | `STYLE LOG`: `Honorific punctuation` |
| `NAME-HELD-EXCEPTIONS` | Subsequent reference to `Xi Jinping`, `Li Qiang`, `Wang Yi`, `Kim Jong Un`, `Lee Hsien Loong`, `Aung San Suu Kyi`, `Mahathir Mohamad`, `Anwar Ibrahim`, `Bashar al-Assad`, `Osama bin Laden` | After 1st full-name mention | Enforces `DIRECTORY.yaml` held form: `Mr Xi`, `Mr Li`, `Mr Wang`, `Mr Kim`, `Mr Lee`, `Ms Suu Kyi`, `Mr Mahathir`, `Mr Anwar`, `Mr Assad`, `bin Laden` | `STYLE LOG`: `Held second-reference exception` |
| `NAME-MORTALITY-STRIP` | `Mr` or `Ms` before a deceased person in `status.mortalities` (`Shinzo Abe`, `Queen Elizabeth II`, `Chavarat Charnvirakul`, `Kofi Annan`, `Lee Kuan Yew`, `Banharn Silpa-archa`, `Prem Tinsulanonda`, `Chatichai Choonhavan`) | Military/police/medical/royal titles (`Gen Prem`) are retained | Strips `Mr`/`Ms` on all references to deceased individuals | `STYLE LOG`: `Deceased honorific stripped` |
| `NAME-THAI-SECOND-REF` | First reference introduces `<FirstName> <LastName>, the <role>,` or `<Role> <FirstName> <LastName>`; subsequent sentence in same/next paragraph begins `He said` / `She said` or repeats `<LastName>` / `<FirstName> <LastName>` | Single unambiguous introduced Thai/Lao subject in scope | Converts subsequent reference to `Mr <FirstName>` / `Ms <FirstName>` (e.g., `Somchai Dee, the district chief... He said` → `Mr Somchai said`; `Mr Dee` → `Mr Somchai`) | `STYLE LOG`: `Thai second reference` |
| `NAME-TITLE-CASE` | Capitalized occupational/descriptive title before a name (`Deputy Spokesperson`, `Company President`, `Human Rights Lawyer`, `Head Coach`) or standalone/former title (`the Prime Minister said`, `Former Prime Minister`) | Formal political/official title directly before name (`Prime Minister Paetongtarn Shinawatra`) stays capped | Lower-cases occupational/descriptive/standalone/former title (`deputy spokesperson`, `company president`, `the prime minister said`, `former prime minister`) | `STYLE LOG`: `Title casing` |
| `HEAD-HONORIFIC-STRIP` | `Mr `, `Ms `, `Mrs ` in `HEAD` or `DECK` | Headlines & decks omit civil honorifics | Strips `Mr`/`Ms`/`Mrs` from headline and deck | `STYLE LOG`: `Headline honorific stripped` |

---

## 3. `[P2]` VERIFICATION & ANTI-FABRICATION GATE SPECIFICATION

To guarantee **zero factual fabrication**, the platform enforces three hard programmatic gates in `bkp_processor.py`:

### 3.1 Copy-Internal Arithmetic & Subset Verifier (`[P2-ARITH]`)
- Scans copy for percentage statements (`X% of N is M`), component sums (`A men and B women, totaling C`), and subset claims (`A sites from a network of B` where `A > B`).
- If an internal arithmetic contradiction is detected (e.g., `50% of 800 residents — or 450 people`, or `120 outlets from a network of 85`), the processor raises a deterministic `HOLD:` / `Query:` banner and records the exact mathematical discrepancy.

### 3.2 Standing Watchlist & Mortalities Gate (`[P2-WATCH]`)
- Checks every filing against `DIRECTORY.yaml` `status.watch` and `status.mortalities`:
  - **Nikorn Chamnong** (`status.watch.nikorn_chamnong`): Flags if described as a current MP without verifying party-list status.
  - **Stithorn Thananithichot** (`status.watch.stithorn_thananithichot`): Flags if described with stale King Prajadhipok's Institute director role without checking current title.
  - **Korn Chatikavanij** (`status.watch.korn_chatikavanij`): Flags if linked to a stale political party without verification.
  - **Chaichanok Chidchob** (`status.watch.chaichanok_chidchob`): Flags if cabinet/party title is unverified.
  - **Chadchart Sittipunt** (`status.watch.chadchart_sittipunt`): Enforces spelling `Chadchart Sittipunt` (corrects `Chatchart`) and verifies Bangkok governor role.
  - **Donald Trump / JD Vance**: Enforces current US president / vice-president roles (`47th US president`, `US vice-president`).

### 3.3 Programmatic Two-Source Validator (`[P2-TWOSOURCE]`)
- A sub-editor or automated pass **cannot** inject a material fact change into the `FACT CHANGES` block unless the change record supplies:
  1. `source_1_publisher` and `source_1_record` (non-empty named publisher + specific record/report), **AND**
  2. `source_2_publisher` and `source_2_record` (independent second publisher + specific record/report), **OR**
  3. `authority_mode` in `{"copy_internal_arithmetic", "per_desk"}`.
- **Hard-Blocked Sources:** Any source matching a raw URL (`http://`, `https://`, `www.`), `"the filing"`, `"Bangkok Post"`, `"search summary"`, `"AI summary"`, `"Directory"`, or `"memory"` is automatically **REJECTED** by the validator. When rejected, the filed wording is preserved in the copy and the item is routed to `Query:` and `OUTSTANDING:`.

---

## 4. `[P1]` DETERMINISTIC COPY-FITTING & GLYPH-WEIGHT SPECIFICATION

### 4.1 `[P1-A]` Headline & Deck Glyph-Weight Formula
Every character in `HEAD` and `DECK` is scored deterministically:
- **Weight `0.5` (Lean):** `' '`, `,`, `.`, `;`, `:`, `'`, `"`, `!`, `|`, `-`, `(`, `)`, `[`, `]`, `/`, `1`, `f`, `i`, `j`, `l`, `r`, `t`, `I`, `J`
- **Weight `1.5` (Heavy):** `m`, `w`, `M`, `W`, `@`, `%`, `&`, `—`, `–`
- **Weight `1.0` (Baseline):** All other characters (`a-z`, `A-Z`, `0, 2-9`, `$`, etc.)

### 4.2 `[P1-B]` Exact Body Character Count Formula
```python
body_count = len(re.sub(r"\r?\n", "", body).strip())
```
- Reported in every `EDIT` / `FIT` return as `Body: [input_count] > [output_count]` (or `Body: [input_count] > [output_count] (target [max_budget])`).

### 4.3 `[P1-C]` Line-Level `FOLLOW-UP` Fitting
- Triggered when a sub-editor specifies a line-trim or line-fill instruction (e.g., `trim 1 line in par 2` or `fill last line by +12 chars`).
- Emits **only** replacement fenced boxes (`#### Par N` / `#### Head` / `#### Deck`) without re-running the full `JOB REPORT`.

---

## 5. `[R1]–[R4]` LOCKED NON-DIVERGENT RETURN SCHEMAS

Every job mode compiles through a locked schema function in `/bkp_processor.py`:

1. **`EDIT` / `FIT` Schema (`[R2]`, `[R4]`):**
   - `JOB REPORT`
   - `ID: [slug] — [one-line job summary]`
   - `EDIT`
   - Optional `HOLD:` / `Query:` lines (immediately above the copy box)
   - Single fenced code block containing `###head` (if placed/supplied), `###deck` (omitted for Briefs), `###byline` (`Post Reporters` when placed domestic) or `###label` (when unplaced), and edited body paragraphs
   - `Body: [in] > [out]` (immediately below the copy box)
   - `ALTERNATES` (`Head:` and `Deck:` alternate options with `[chars / weight]` when placed or head/deck supplied)
   - `FACT CHANGES` (included **only** when a change passes the Two-Source / Arithmetic / Per-Desk validator)
   - `STYLE LOG` (compiled **strictly** from the non-empty Transformation Ledger — never fabricated)
   - `ORIGINAL FILING` (included **only** for domestic stories; omitted for international wire copy)
   - `OUTSTANDING: [none or numbered open items]`

2. **`CHECK` / `QC` Schema (`modules/check.md`):**
   - `JOB REPORT` → `ID:` → `CHECK` or `QC` → `FINDINGS` (ranked `Critical` → `Major` → `House`) → `VERIFIED` → `QUERIES` → `OUTSTANDING:`.

3. **`PHOTO` / `MUGSHOT` Schema (`modules/photo.md`):**
   - `JOB REPORT` → `ID:` → `PHOTO` → fenced caption block (`[Name]` or `[Present-tense action sentence]. [Context sentence]. ([Credit])`) → `ALTERNATES` → `NOTES` → `OUTSTANDING:`.

4. **`PR` Schema (`modules/pr.md`):**
   - `JOB REPORT` → `ID:` → `PR` → optional `HOLD:`/`Query:` → fenced copy box → `Body: [in] > [out]` → `ALTERNATES` → `FACT CHANGES` (if any) → `STYLE LOG` (`Light PR pass; house style and factual gates applied.`) → `OUTSTANDING:`.
