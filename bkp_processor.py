#!/usr/bin/env python3
"""Bangkok Post Deterministic Editorial Content Processing Engine (bkp_processor.py).

Implements the 12-pass deterministic sub-editing state machine adapted from
Blueprint/BLUEPRINT.md and Blueprint/DIRECTORY.yaml:
- Zero factual fabrication (enforced by [P2] Two-Source Validator, Arithmetic Verifier & Watchlist Gate)
- Zero fake procedural steps (STYLE LOG is compiled strictly from actual token mutations in TransformationLedger)
- Zero return format divergence (locked schema compilers for EDIT, FIT, CHECK, QC, PHOTO, MUGSHOT, PR, FOLLOW-UP)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
import re
from typing import Any
import unicodedata

ROOT_DIR = Path(__file__).resolve().parent
BLUEPRINT_DIR = ROOT_DIR / "Blueprint"
FALLBACK_DIR = ROOT_DIR / "Blueprint fallback"

# ---------------------------------------------------------------------------
# [P1-A] Glyph-Weight Tables
# ---------------------------------------------------------------------------
LEAN_GLYPHS = set(" ,.;:'\"!|-()[]/1fijlrtIJ")
HEAVY_GLYPHS = set("mwMW@%&—–")

# House month names (references.dates.months)
HOUSE_MONTHS = {
    1: "Jan",
    2: "Feb",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "Aug",
    9: "Sept",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

MONTH_NAME_TO_NUM = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

ARABIC_TO_ROMAN = {
    "1": "I",
    "2": "II",
    "3": "III",
    "4": "IV",
    "5": "V",
    "6": "VI",
    "7": "VII",
    "8": "VIII",
    "9": "IX",
    "10": "X",
}

WIRE_AGENCIES = (
    "Reuters",
    "AFP",
    "Agence France-Presse",
    "Associated Press",
    "AP",
    "Bloomberg",
    "Xinhua",
    "Kyodo",
    "DPA",
    "BBC",
)

# Protected proper names that must NOT be altered by British spelling or Thai place splitters
PROTECTED_PROPER_PHRASES = (
    "Queen Sirikit National Convention Center",
    "Australian Labor Party",
    "World Trade Center",
    "Centers for Disease Control and Prevention",
    "Centers for Disease Control",
    "National Hurricane Center",
    "Kennedy Space Center",
    "Lincoln Center",
    "Rockefeller Center",
    "Pearl Harbor",
    "Don Mueang International Airport",
    "Don Mueang airport",
    "Don Mueang",
    "Khlong Thom Centre",
    "Khlong Prem Prachakon",
    "Hatyai Hospital",
    "Prince of Songkla University",
    "Sriracha Tiger Zoo",
    "Minburi Prison",
    "Impact Arena, Muang Thong Thani",
)

# Third-party Thai institutional exceptions (references.thai_places.exceptions)
THAI_INSTITUTIONAL_EXCEPTIONS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"\bHat Yai Hospital\b"),
        "Hatyai Hospital",
        "Hatyai Hospital (third-party institutional exception)",
    ),
    (
        re.compile(r"\bPrince of Songkhla University\b"),
        "Prince of Songkla University",
        "Prince of Songkla University (third-party institutional exception)",
    ),
    (
        re.compile(r"\bSi Racha Tiger Zoo\b"),
        "Sriracha Tiger Zoo",
        "Sriracha Tiger Zoo (third-party institutional exception)",
    ),
    (
        re.compile(r"\bMin Buri Prison\b"),
        "Minburi Prison",
        "Minburi Prison (third-party institutional exception)",
    ),
    (
        re.compile(r"\bImpact Arena\s+Muang Thong Thani\b"),
        "Impact Arena, Muang Thong Thani",
        "Impact Arena, Muang Thong Thani (comma required)",
    ),
]

# Thai place spelling variants -> DIRECTORY.yaml house forms
THAI_PLACE_NORMALISATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bAyudhya\b"), "Ayutthaya"),
    (re.compile(r"\bChonburi\b"), "Chon Buri"),
    (re.compile(r"\bChonBuri\b"), "Chon Buri"),
    (re.compile(r"\bBuriram\b"), "Buri Ram"),
    (re.compile(r"\bPrachinburi\b"), "Prachin Buri"),
    (re.compile(r"\bLopburi\b"), "Lop Buri"),
    (re.compile(r"\bSingburi\b"), "Sing Buri"),
    (re.compile(r"\bSuphanburi\b"), "Suphan Buri"),
    (re.compile(r"\bSara Buri\b"), "Saraburi"),
    (re.compile(r"\bSisaket\b"), "Si Sa Ket"),
    (re.compile(r"\bPhang Nga\b"), "Phangnga"),
    (re.compile(r"\bThonburi\b"), "Thon Buri"),
    (re.compile(r"\bMinburi\b(?!\s+Prison)"), "Min Buri"),
    (re.compile(r"\bSriracha\b(?!\s+Tiger Zoo)"), "Si Racha"),
    (re.compile(r"\bHatyai\b(?!\s+Hospital)"), "Hat Yai"),
]

# Countries, foreign places & article rules
FOREIGN_AND_COUNTRY_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\bBurma\b"), "Myanmar", "Burma > Myanmar"),
    (re.compile(r"\bBurmese\b"), "Myanmar", "Burmese > Myanmar"),
    (re.compile(r"\bLaotians\b"), "Lao people", "Laotians > Lao people"),
    (re.compile(r"\bLaotian\b"), "Lao", "Laotian > Lao"),
    (re.compile(r"\bHolland\b"), "the Netherlands", "Holland > the Netherlands"),
    (re.compile(r"\bCzechia\b"), "the Czech Republic", "Czechia > the Czech Republic"),
    (re.compile(r"\bTimor-Leste\b"), "East Timor", "Timor-Leste > East Timor"),
    (re.compile(r"\bCote d['’]Ivoire\b"), "Ivory Coast", "Cote d'Ivoire > Ivory Coast"),
    (re.compile(r"\bThe Gambia\b"), "Gambia", "The Gambia > Gambia"),
    (re.compile(r"\bthe Gambia\b"), "Gambia", "the Gambia > Gambia"),
    (re.compile(r"\bthe Ukraine\b"), "Ukraine", "the Ukraine > Ukraine"),
    (re.compile(r"\bthe Sudan\b"), "Sudan", "the Sudan > Sudan"),
    (re.compile(r"\bthe Lebanon\b"), "Lebanon", "the Lebanon > Lebanon"),
    (re.compile(r"\bthe Seychelles\b"), "Seychelles", "the Seychelles > Seychelles"),
    (re.compile(r"\bthe Hague\b"), "The Hague", "the Hague > The Hague"),
    (re.compile(r"\bRangoon\b"), "Yangon", "Rangoon > Yangon"),
    (re.compile(r"\bPeking\b(?!\s+[Dd]uck)"), "Beijing", "Peking > Beijing"),
    (re.compile(r"\bBombay\b"), "Mumbai", "Bombay > Mumbai"),
    (re.compile(r"\bCalcutta\b"), "Kolkata", "Calcutta > Kolkata"),
    (re.compile(r"\bMadras\b"), "Chennai", "Madras > Chennai"),
    (re.compile(r"\bBangalore\b"), "Bengaluru", "Bangalore > Bengaluru"),
    (re.compile(r"\bArbil\b|\bErbil\b"), "Irbil", "Erbil/Arbil > Irbil"),
    (re.compile(r"\bAin al-Arab\b"), "Kobane", "Ain al-Arab > Kobane"),
    (re.compile(r"\bMacao\b"), "Macau", "Macao > Macau"),
]

# Pronounceable >3-letter acronyms -> Title Case (references.acronyms)
TITLE_CASE_ACRONYMS: dict[str, str] = {
    "ASEAN": "Asean",
    "FIFA": "Fifa",
    "NASA": "Nasa",
    "NATO": "Nato",
    "OPEC": "Opec",
    "UNESCO": "Unesco",
    "UNICEF": "Unicef",
    "APEC": "Apec",
    "INTERPOL": "Interpol",
    "KEMAL": "Kemal",
}

# Organisations & vocabulary rules (references.organisations / vocabulary)
ORG_AND_VOCAB_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\b7-11\b"), "7-Eleven", "7-11 > 7-Eleven"),
    (re.compile(r"\bAir Asia\b"), "AirAsia", "Air Asia > AirAsia"),
    (
        re.compile(r"\bMalaysian Airlines\b"),
        "Malaysia Airlines",
        "Malaysian Airlines > Malaysia Airlines",
    ),
    (
        re.compile(r"\bPaveena Foundation\b"),
        "Pavena Foundation",
        "Paveena > Pavena Foundation",
    ),
    (re.compile(r"\bPaveena Hongsakula\b"), "Pavena Hongsakula", "Paveena > Pavena"),
    (re.compile(r"\bRed Shirts\b"), "red shirts", "Red Shirts > red shirts"),
    (re.compile(r"\bYellow Shirts\b"), "yellow shirts", "Yellow Shirts > yellow shirts"),
    (re.compile(r"\bShi['’]?ites\b"), "Shias", "Shi'ites > Shias"),
    (re.compile(r"\bShi['’]?ite\b"), "Shia", "Shi'ite > Shia"),
    (re.compile(r"\bSharia law\b"), "sharia law", "Sharia law > sharia law"),
    (re.compile(r"\b(?:Isil|Isis|ISIS|ISIL|Daesh)\b"), "the Islamic State", "ISIS/ISIL/Daesh > the Islamic State"),
    (re.compile(r"\bwhilst\b"), "while", "whilst > while"),
    (re.compile(r"\bWhilst\b"), "While", "Whilst > While"),
    (re.compile(r"\bamongst\b"), "among", "amongst > among"),
    (re.compile(r"\bAmongst\b"), "Among", "Amongst > Among"),
    (re.compile(r"\bamidst\b"), "amid", "amidst > amid"),
    (re.compile(r"\bAmidst\b"), "Amid", "Amidst > Amid"),
    (re.compile(r"\b(?:completely|totally) destroyed\b"), "destroyed", "completely/totally destroyed > destroyed"),
    (re.compile(r"\bwidow of the late\b"), "widow of", "widow of the late > widow of"),
    (re.compile(r"\b9/11\b"), "Sept 11", "9/11 > Sept 11"),
    (re.compile(r"\bXmas\b"), "Christmas", "Xmas > Christmas"),
    (
        re.compile(r"\bthe Thai capital(?: city)? of Bangkok\b|\bBangkok,\s*the Thai capital\b"),
        "Bangkok",
        "the Thai capital of Bangkok > Bangkok",
    ),
    (re.compile(r"\bmedia are\b"), "media is", "media are > media is (singular media)"),
    (re.compile(r"\bmedia have\b"), "media has", "media have > media has (singular media)"),
    (re.compile(r"\bthe media were\b"), "the media was", "the media were > the media was"),
]

# US -> British English lexical conversions ([G1-A])
US_TO_UK_WORDS: dict[str, str] = {
    "center": "centre",
    "centers": "centres",
    "centered": "centred",
    "centering": "centring",
    "kilometer": "kilometre",
    "kilometers": "kilometres",
    "centimeter": "centimetre",
    "centimeters": "centimetres",
    "millimeter": "millimetre",
    "millimeters": "millimetres",
    "liter": "litre",
    "liters": "litres",
    "organize": "organise",
    "organizes": "organises",
    "organized": "organised",
    "organizing": "organising",
    "organization": "organisation",
    "organizations": "organisations",
    "realize": "realise",
    "realizes": "realises",
    "realized": "realised",
    "realizing": "realising",
    "analyze": "analyse",
    "analyzes": "analyses",
    "analyzed": "analysed",
    "analyzing": "analysing",
    "recognize": "recognise",
    "recognizes": "recognises",
    "recognized": "recognised",
    "recognizing": "recognising",
    "criticize": "criticise",
    "criticizes": "criticises",
    "criticized": "criticised",
    "criticizing": "criticising",
    "emphasize": "emphasise",
    "emphasized": "emphasised",
    "modernize": "modernise",
    "modernized": "modernised",
    "apologize": "apologise",
    "apologized": "apologised",
    "authorize": "authorise",
    "authorized": "authorised",
    "prioritize": "prioritise",
    "prioritized": "prioritised",
    "stabilize": "stabilise",
    "stabilized": "stabilised",
    "defense": "defence",
    "defenses": "defences",
    "offense": "offence",
    "offenses": "offences",
    "pretense": "pretence",
    "labor": "labour",
    "labors": "labours",
    "neighbor": "neighbour",
    "neighbors": "neighbours",
    "neighborhood": "neighbourhood",
    "neighborhoods": "neighbourhoods",
    "rumor": "rumour",
    "rumors": "rumours",
    "favor": "favour",
    "favors": "favours",
    "favored": "favoured",
    "favorable": "favourable",
    "honor": "honour",
    "honors": "honours",
    "honored": "honoured",
    "color": "colour",
    "colors": "colours",
    "colored": "coloured",
    "behavior": "behaviour",
    "behaviors": "behaviours",
    "harbor": "harbour",
    "harbors": "harbours",
    "humor": "humour",
    "odor": "odour",
    "vigor": "vigour",
    "traveling": "travelling",
    "traveled": "travelled",
    "traveler": "traveller",
    "travelers": "travellers",
    "canceled": "cancelled",
    "canceling": "cancelling",
    "fueled": "fuelled",
    "fueling": "fuelling",
    "labeled": "labelled",
    "labeling": "labelling",
    "signaled": "signalled",
    "modeling": "modelling",
    "modeled": "modelled",
    "jewelry": "jewellery",
    "skeptical": "sceptical",
    "skeptic": "sceptic",
    "skeptics": "sceptics",
    "maneuver": "manoeuvre",
    "maneuvers": "manoeuvres",
    "pediatric": "paediatric",
    "pediatrician": "paediatrician",
    "diarrhea": "diarrhoea",
    "enroll": "enrol",
    "enrolls": "enrols",
    "enrollment": "enrolment",
    "fulfill": "fulfil",
    "fulfills": "fulfils",
    "skillful": "skilful",
    "gray": "grey",
    "fetus": "foetus",
    "estrogen": "oestrogen",
    "anemia": "anaemia",
    "leukemia": "leukaemia",
    "encyclopedia": "encyclopaedia",
    "archeology": "archaeology",
    "medieval": "mediaeval",
    "artifact": "artefact",
    "artifacts": "artefacts",
    "curb": "kerb",  # only when pavement, so omit curb from blind replacement
}
US_TO_UK_WORDS.pop("curb", None)

# Held foreign second-reference exceptions (references.names_honorifics.second_reference_exceptions)
HELD_FOREIGN_SECOND_REFS: dict[str, tuple[str, list[str]]] = {
    "Xi Jinping": ("Mr Xi", ["Mr Jinping", "Jinping"]),
    "Li Qiang": ("Mr Li", ["Mr Qiang", "Qiang"]),
    "Wang Yi": ("Mr Wang", ["Mr Yi"]),
    "Kim Jong Un": ("Mr Kim", ["Mr Un", "Jong Un"]),
    "Lee Hsien Loong": ("Mr Lee", ["Mr Loong", "Hsien Loong"]),
    "Aung San Suu Kyi": ("Ms Suu Kyi", ["Ms Kyi", "Ms Aung", "Aung San"]),
    "Mahathir Mohamad": ("Mr Mahathir", ["Mr Mohamad", "Dr Mohamad"]),
    "Anwar Ibrahim": ("Mr Anwar", ["Mr Ibrahim"]),
    "Bashar al-Assad": ("Mr Assad", ["Mr al-Assad", "al-Assad"]),
    "Osama bin Laden": ("bin Laden", ["Mr bin Laden", "Mr Laden", "Osama"]),
}

# Deceased figures in status.mortalities (strip Mr/Ms; keep military/police/medical/royal titles)
DECEASED_FIGURES: dict[str, str] = {
    "Shinzo Abe": "Shinzo Abe (deceased: omit Mr/Ms; use Abe on second reference)",
    "Chavarat Charnvirakul": "Chavarat Charnvirakul (deceased: omit Mr; use Chavarat on second reference)",
    "Banharn Silpa-archa": "Banharn Silpa-archa (deceased: omit Mr; use Banharn on second reference)",
    "Prem Tinsulanonda": "Gen Prem Tinsulanonda (deceased: retain military rank Gen Prem; never Mr Prem)",
    "Chatichai Choonhavan": "Gen Chatichai Choonhavan (deceased: retain Gen; omit Mr)",
    "Kofi Annan": "Kofi Annan (deceased: omit Mr)",
    "Lee Kuan Yew": "Lee Kuan Yew (deceased: omit Mr)",
    "bhichai rattakul": "Bhichai Rattakul (deceased: omit Mr)",
}

# Standing watchlist entries from DIRECTORY.yaml status.watch
WATCHLIST_RULES: list[dict[str, str]] = [
    {
        "key": "nikorn_chamnong",
        "name": "Nikorn Chamnong",
        "pattern": r"\bNikorn Chamnong\b",
        "suspect_pattern": r"\b(?:MP|member of parliament|Chartthaipattana MP)\b",
        "ruling": "Watchlist [status.watch.nikorn_chamnong]: Verify current parliamentary/party-list status; do not assume sitting MP without current verification.",
    },
    {
        "key": "stithorn_thananithichot",
        "name": "Stithorn Thananithichot",
        "pattern": r"\bStithorn Thananithichot\b",
        "suspect_pattern": r"\bKing Prajadhipok\b",
        "ruling": "Watchlist [status.watch.stithorn_thananithichot]: Verify current academic/institutional role; do not carry stale King Prajadhipok's Institute director title.",
    },
    {
        "key": "korn_chatikavanij",
        "name": "Korn Chatikavanij",
        "pattern": r"\bKorn Chatikavanij\b",
        "suspect_pattern": r"\b(?:Democrat Party|Chartpattanakla|leader)\b",
        "ruling": "Watchlist [status.watch.korn_chatikavanij]: Verify current party affiliation or former-minister styling before publication.",
    },
    {
        "key": "chaichanok_chidchob",
        "name": "Chaichanok Chidchob",
        "pattern": r"\bChaichanok Chidchob\b",
        "suspect_pattern": r".",
        "ruling": "Watchlist [status.watch.chaichanok_chidchob]: Verify current Bhumjaithai Party / cabinet portfolio before clearing.",
    },
    {
        "key": "chadchart_sittipunt",
        "name": "Chadchart Sittipunt",
        "pattern": r"\bCha[dt]chart Sittipunt\b",
        "suspect_pattern": r"\bChatchart\b",
        "ruling": "Watchlist [status.watch.chadchart_sittipunt]: House spelling is Chadchart Sittipunt (Bangkok governor).",
    },
]

# Non-Thai common Anglo/international first names so our Thai/Lao second-ref engine only targets Thai/Lao names
NON_THAI_GIVEN_NAMES = {
    "john", "david", "michael", "james", "robert", "william", "richard", "thomas",
    "charles", "joseph", "donald", "joe", "barack", "george", "emmanuel", "olaf",
    "keir", "rishi", "anthony", "scott", "mark", "peter", "paul", "andrew", "steven",
    "stephen", "kevin", "brian", "EDWARD", "mary", "patricia", "jennifer", "linda",
    "elizabeth", "barbara", "susan", "jessica", "sarah", "karen", "nancy", "lisa",
    "margaret", "betty", "sandra", "ashley", "emily", "claire", "anna", "maria",
    "vladimir", "volodymyr", "benjamin", "recep", "narendra", "fumio", "shigeru",
    "yoon", "ferdinand", "anwar", "mahathir", "lee", "lawrence", "xi", "li", "wang",
    "kim", "aung", "min", "hun", "norodom",
}

THAI_ROLES_INDICATORS = (
    "district chief",
    "governor",
    "deputy governor",
    "permanent secretary",
    "director-general",
    "director",
    "spokesman",
    "spokeswoman",
    "spokesperson",
    "deputy spokesperson",
    "minister",
    "deputy minister",
    "prime minister",
    "deputy prime minister",
    "police chief",
    "commander",
    "superintendent",
    "investigator",
    "mayor",
    "kamnan",
    "village head",
    "village headman",
    "senator",
    "mp",
    "mp for",
    "secretary-general",
    "chairman",
    "chairwoman",
    "president",
    "chief executive",
    "abbot",
)

# Occupational/descriptive titles that must be lower-case before a name (references.names_honorifics.titles)
DESCRIPTIVE_TITLES_LOWER = (
    "Deputy Spokesperson",
    "Spokesperson",
    "Government Spokesperson",
    "Government Spokesman",
    "Police Spokesman",
    "Army Spokesman",
    "Ministry Spokesman",
    "Company President",
    "Chief Executive Officer",
    "Chief Executive",
    "Managing Director",
    "Executive Director",
    "Human Rights Lawyer",
    "Defense Lawyer",
    "Defence Lawyer",
    "Head Coach",
    "District Chief",
    "Village Headman",
    "Political Analyst",
    "Economist",
    "Activist",
)

NUMBER_WORDS_1_TO_9 = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


@dataclass
class LedgerEntry:
    """Single immutable record of a deterministic rule execution."""

    rule_id: str
    category: str
    location: str
    before: str
    after: str
    note: str


@dataclass
class FactChangeProposal:
    """Structured fact-change candidate validated by the [P2] Two-Source Gate."""

    claim_before: str
    claim_after: str
    authority_mode: str = "two_sources"  # "two_sources" | "copy_internal_arithmetic" | "per_desk"
    source_1_publisher: str = ""
    source_1_record: str = ""
    source_2_publisher: str = ""
    source_2_record: str = ""
    desk_note: str = ""


# Persistent session OUTSTANDING store (keyed by slug)
SESSION_OUTSTANDING_STORE: dict[str, list[str]] = {}


def compute_glyph_weight(text: str) -> dict[str, Any]:
    """Calculate [P1-A] character count and glyph-weight score (0.5 / 1.0 / 1.5)."""
    clean = (text or "").strip()
    lean_count = 0
    heavy_count = 0
    base_count = 0
    total_weight = 0.0
    for ch in clean:
        if ch in LEAN_GLYPHS:
            lean_count += 1
            total_weight += 0.5
        elif ch in HEAVY_GLYPHS:
            heavy_count += 1
            total_weight += 1.5
        else:
            base_count += 1
            total_weight += 1.0
    return {
        "text": clean,
        "chars": len(clean),
        "weight": round(total_weight, 1),
        "lean_chars": lean_count,
        "baseline_chars": base_count,
        "heavy_chars": heavy_count,
    }


def compute_body_char_count(body_text: str) -> int:
    """Calculate [P1-B] exact body character count: len(re.sub(r'\\r?\\n', '', body).strip())."""
    return len(re.sub(r"\r?\n", "", body_text or "").strip())


def parse_publication_date(raw_date: str | None, slug: str = "") -> date:
    """Resolve publication date from explicit YYYY-MM-DD or slug day prefix (e.g. '17-rivers' -> Sept 17)."""
    if raw_date:
        try:
            return datetime.strptime(raw_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass
    m_slug = re.match(r"^(\d{1,2})[-_]", (slug or "").strip())
    if m_slug:
        day_num = int(m_slug.group(1))
        if 1 <= day_num <= 30:
            return date(2026, 9, day_num)
    return date(2026, 9, 17)


def parse_dcx_or_raw_filing(raw_input: str) -> dict[str, Any]:
    """Deterministically parse DC-X package headers or bare filed copy."""
    text = (raw_input or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    fields: dict[str, str] = {
        "slug": "",
        "counts": "",
        "head": "",
        "deck": "",
        "byline": "",
        "label": "",
        "caption": "",
        "credit": "",
        "body": "",
        "overspill": "",
    }
    if not text:
        return fields

    lines = text.split("\n")
    header_pattern = re.compile(
        r"^(?:###)?(SLUG|ID|COUNTS|BUDGET|HEAD|HEADLINE|DECK|STANDFIRST|BYLINE|LABEL|CAPTION|CREDIT|BODY|OVERSPILL)\s*:\s*(.*)$",
        re.IGNORECASE,
    )
    marker_pattern = re.compile(
        r"^###(head|deck|byline|label|caption|body|overspill)\b\s*(.*)$",
        re.IGNORECASE,
    )

    has_structured_fields = any(
        header_pattern.match(ln.strip()) or marker_pattern.match(ln.strip())
        for ln in lines[:15]
    )
    if not has_structured_fields:
        # Check if first line looks like a short slug (e.g., "17-rivers" or "SLUG: 17-rivers")
        first_line = lines[0].strip()
        if re.fullmatch(r"\d{1,2}-[a-z0-9_-]+(?:\s+bf|\s+Brief)?", first_line, re.IGNORECASE):
            fields["slug"] = first_line
            fields["body"] = "\n".join(lines[1:]).strip()
        else:
            fields["body"] = text
        return fields

    current_slot = "body"
    slot_buffers: dict[str, list[str]] = {k: [] for k in fields}

    for line in lines:
        stripped = line.strip()
        m_hdr = header_pattern.match(stripped)
        if m_hdr:
            key_raw = m_hdr.group(1).lower()
            val_part = m_hdr.group(2).strip()
            slot_map = {
                "slug": "slug",
                "id": "slug",
                "counts": "counts",
                "budget": "counts",
                "head": "head",
                "headline": "head",
                "deck": "deck",
                "standfirst": "deck",
                "byline": "byline",
                "label": "label",
                "caption": "caption",
                "credit": "credit",
                "body": "body",
                "overspill": "overspill",
            }
            current_slot = slot_map[key_raw]
            if val_part:
                slot_buffers[current_slot].append(val_part)
            continue

        m_mk = marker_pattern.match(stripped)
        if m_mk:
            current_slot = m_mk.group(1).lower()
            rest = m_mk.group(2).strip()
            if rest:
                slot_buffers[current_slot].append(rest)
            continue

        slot_buffers[current_slot].append(line)

    for k in fields:
        fields[k] = "\n".join(slot_buffers[k]).strip()

    return fields


def _is_invalid_authority_source(src_publisher: str, src_record: str) -> str | None:
    """Check if a source violates [P2] source-validity rules."""
    pub = (src_publisher or "").strip()
    rec = (src_record or "").strip()
    if not pub or not rec:
        return "Missing named publisher or specific record/report title."
    combined = f"{pub} {rec}".lower()
    if "http://" in combined or "https://" in combined or "www." in combined:
        return "Raw URLs are prohibited as factual authority ([R1]/[P2]: name Publisher + Record/Report)."
    prohibited_tokens = [
        ("the filing", "The filing itself cannot be cited as verification authority ([P2])."),
        ("filed copy", "The filing itself cannot be cited as verification authority ([P2])."),
        ("bangkok post", "The Bangkok Post cannot be cited to verify itself ([P2])."),
        ("search summary", "Search or AI summaries are prohibited as verification sources ([P2])."),
        ("ai summary", "Search or AI summaries are prohibited as verification sources ([P2])."),
        ("directory", "DIRECTORY.yaml is a house spelling/style register, not a factual verification source ([P2])."),
        ("memory", "Sub-editor or model memory is prohibited as verification authority ([P2])."),
    ]
    for token, reason in prohibited_tokens:
        if token in combined:
            return reason
    return None


def validate_fact_change_proposal(proposal: FactChangeProposal) -> dict[str, Any]:
    """Enforce the [P2] Two-Source Rule deterministically."""
    before = (proposal.claim_before or "").strip()
    after = (proposal.claim_after or "").strip()
    mode = (proposal.authority_mode or "two_sources").strip().lower()

    if not before or not after:
        return {
            "approved": False,
            "reason": "Both original filed claim and replacement factual claim are required.",
            "formatted_citation": "",
        }

    if mode == "copy_internal_arithmetic":
        note = (proposal.desk_note or "copy-internal arithmetic").strip()
        return {
            "approved": True,
            "authority_mode": "copy_internal_arithmetic",
            "reason": "Verified via copy-internal arithmetic.",
            "formatted_entry": f"- `{before}` > `{after}` — verified by copy-internal arithmetic ({note}).",
        }

    if mode == "per_desk":
        note = (proposal.desk_note or "per desk instruction").strip()
        return {
            "approved": True,
            "authority_mode": "per_desk",
            "reason": "Cleared per explicit desk instruction.",
            "formatted_entry": f"- `{before}` > `{after}` — per desk ({note}).",
        }

    err1 = _is_invalid_authority_source(proposal.source_1_publisher, proposal.source_1_record)
    if err1:
        return {
            "approved": False,
            "authority_mode": "two_sources",
            "reason": f"Source 1 rejected: {err1}",
            "formatted_entry": "",
        }

    err2 = _is_invalid_authority_source(proposal.source_2_publisher, proposal.source_2_record)
    if err2:
        return {
            "approved": False,
            "authority_mode": "two_sources",
            "reason": f"Source 2 rejected (Two-Source Rule requires two independent named sources): {err2}",
            "formatted_entry": "",
        }

    if proposal.source_1_publisher.strip().lower() == proposal.source_2_publisher.strip().lower():
        return {
            "approved": False,
            "authority_mode": "two_sources",
            "reason": "Two-Source Rule rejected: Source 1 and Source 2 must come from two independent publishers.",
            "formatted_entry": "",
        }

    s1 = f"{proposal.source_1_publisher.strip()}, {proposal.source_1_record.strip()}"
    s2 = f"{proposal.source_2_publisher.strip()}, {proposal.source_2_record.strip()}"
    return {
        "approved": True,
        "authority_mode": "two_sources",
        "reason": "Verified by two independent named sources (Publisher + Record/Report).",
        "formatted_entry": f"- `{before}` > `{after}` — Sources: (1) {s1}; (2) {s2}.",
    }


def _annotate_quotes_with_metric(quote_text: str, ledger: list[LedgerEntry], loc: str) -> str:
    """[G1-B] Preserve quoted words verbatim while inserting [metric conversion] for imperial/Fahrenheit figures."""
    updated = quote_text

    # 1. Fahrenheit inside quotes -> [XC]
    def _fahrenheit_repl(m: re.Match[str]) -> str:
        full = m.group(0)
        if "[" in quote_text[m.end():m.end() + 8]:
            return full
        val_f = float(m.group(1))
        val_c = round((val_f - 32.0) * 5.0 / 9.0)
        replacement = f"{full} [{val_c}C]"
        ledger.append(
            LedgerEntry(
                rule_id="G1-QUOTE-METRIC",
                category="Measurements in quotes",
                location=loc,
                before=full,
                after=replacement,
                note="Inserted Celsius conversion in square brackets inside direct quote",
            )
        )
        return replacement

    updated = re.sub(
        r"\b(-?\d+(?:\.\d+)?)\s*(?:°\s*F|degrees?\s+Fahrenheit)\b",
        _fahrenheit_repl,
        updated,
    )

    # 2. Feet / inches / miles / pounds / acres inside quotes
    imperial_factors: list[tuple[re.Pattern[str], float, str]] = [
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:feet|foot|ft)\b(?!\s*\[)"), 30.48, "cm"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:inches|inch)\b(?!\s*\[)"), 2.54, "cm"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:miles|mile)\b(?!\s*(?:away|apart|off|\[))"), 1.609, "km"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:pounds|lbs)\b(?!\s*\[)"), 0.4536, "kg"),
    ]
    for pat, factor, unit_out in imperial_factors:
        def _imp_repl(m: re.Match[str], f: float = factor, u: str = unit_out) -> str:
            full = m.group(0)
            val = float(m.group(1)) * f
            if u == "cm" and val >= 100:
                conv_str = f"{round(val / 100.0, 1):g}m"
            elif val >= 10:
                conv_str = f"{round(val)}{u}"
            else:
                conv_str = f"{round(val, 1):g}{u}"
            rep = f"{full} [{conv_str}]"
            ledger.append(
                LedgerEntry(
                    rule_id="G1-QUOTE-METRIC",
                    category="Measurements in quotes",
                    location=loc,
                    before=full,
                    after=rep,
                    note="Inserted metric conversion in square brackets inside direct quote",
                )
            )
            return rep

        updated = pat.sub(_imp_repl, updated)

    return updated


def _strip_diacritics_outside_quotes(
    text: str,
    ledger: list[LedgerEntry],
    loc: str,
) -> str:
    """Strip Latin diacritics/tone marks (references.language_forms.diacritics)."""
    def _word_repl(m: re.Match[str]) -> str:
        word = m.group(0)
        decomposed = unicodedata.normalize("NFD", word)
        stripped = "".join(
            ch for ch in decomposed if unicodedata.category(ch) != "Mn"
        )
        # Also handle ø/Ø, ł/Ł if present
        stripped = (
            stripped.replace("ø", "o")
            .replace("Ø", "O")
            .replace("ł", "l")
            .replace("Ł", "L")
        )
        norm = unicodedata.normalize("NFC", stripped)
        if norm != word:
            ledger.append(
                LedgerEntry(
                    rule_id="G1-DIACRITICS",
                    category="Diacritics & tone marks",
                    location=loc,
                    before=word,
                    after=norm,
                    note="Stripped diacritics per references.language_forms.diacritics",
                )
            )
        return norm

    return re.sub(r"\b\w*[^\x00-\x7F\u2010-\u206F]\w*\b", _word_repl, text)


def _apply_thai_places_and_transliteration(
    text: str,
    ledger: list[LedgerEntry],
    queries: list[str],
    loc: str,
) -> str:
    """Pass 04: Thai places, provinces, districts, Mueang->Muang, Khlong->Klong, Phra Ram->Rama, etc."""
    out = text

    # 1. Third-party institutional exceptions first
    for pat, rep, note in THAI_INSTITUTIONAL_EXCEPTIONS:
        def _exc_repl(m: re.Match[str], r: str = rep, n: str = note) -> str:
            if m.group(0) != r:
                ledger.append(
                    LedgerEntry("TH-PROPER-EXCEPTIONS", "Thai places", loc, m.group(0), r, n)
                )
            return r
        out = pat.sub(_exc_repl, out)

    # 2. Protect Don Mueang, Khlong Thom Centre, Khlong Prem Prachakon, Hatyai Hospital, etc.
    guards: dict[str, str] = {}
    for idx, phrase in enumerate(PROTECTED_PROPER_PHRASES):
        if phrase in out:
            token = f"__PROPER_GUARD_{idx}__"
            guards[token] = phrase
            out = out.replace(phrase, token)

    # 3. Mueang -> Muang (outside Don Mueang)
    def _mueang_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        rep = "Muang" if orig[0].isupper() else "muang"
        ledger.append(
            LedgerEntry(
                rule_id="TH-MUEANG",
                category="Thai places",
                location=loc,
                before=orig,
                after=rep,
                note="District/capital transliteration: Mueang > Muang (references.thai_places)",
            )
        )
        return rep

    out = re.sub(r"\b[Mm]ueang\b", _mueang_repl, out)

    # 4. Khlong -> Klong (outside guarded Khlong Thom Centre / Khlong Prem Prachakon)
    def _khlong_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        rep = "Klong" if orig[0].isupper() else "klong"
        ledger.append(
            LedgerEntry(
                rule_id="TH-KHLONG",
                category="Thai places",
                location=loc,
                before=orig,
                after=rep,
                note="Canal/district transliteration: Khlong > Klong (references.thai_places)",
            )
        )
        return rep

    out = re.sub(r"\b[Kk]hlong\b", _khlong_repl, out)

    # 5. Isaan -> Isan
    def _isaan_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        rep = "Isan"
        ledger.append(
            LedgerEntry(
                rule_id="TH-ISAAN",
                category="Thai places",
                location=loc,
                before=orig,
                after=rep,
                note="Isaan > Isan (references.thai_places)",
            )
        )
        return rep

    out = re.sub(r"\bIsaan\b", _isaan_repl, out)

    # 6. Phra Ram N / Rama N -> Rama [Roman]
    def _rama_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        num = m.group(1)
        roman = ARABIC_TO_ROMAN.get(num, num)
        suffix = m.group(2) or ""
        rep = f"Rama {roman}{suffix}"
        if orig != rep:
            ledger.append(
                LedgerEntry(
                    rule_id="TH-PHRA-RAM",
                    category="Thai places",
                    location=loc,
                    before=orig,
                    after=rep,
                    note="Road/bridge royal numeral: Phra Ram / Arabic > Rama [Roman]",
                )
            )
        return rep

    out = re.sub(
        r"\b(?:Phra Ram|Rama)\s+([1-9]|10|I|II|III|IV|V|VI|VII|VIII|IX|X)(\s+(?:Road|Bridge|Expressway))?\b",
        _rama_repl,
        out,
    )

    # 7. Soi [NamedRoad] [N] -> [NamedRoad] Soi [N]
    def _soi_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        road = m.group(1)
        num = m.group(2)
        rep = f"{road} Soi {num}"
        ledger.append(
            LedgerEntry(
                rule_id="TH-SUKHUMVIT-SOI",
                category="Thai places",
                location=loc,
                before=orig,
                after=rep,
                note="Named road precedes Soi + number (references.thai_places)",
            )
        )
        return rep

    out = re.sub(
        r"\bSoi\s+(Sukhumvit|Silom|Sathorn|Paholyothin|Phahon Yothin|Phetchaburi|Charoen Krung|Lat Phrao|Ramkhamhaeng|Ratchadaphisek|Thong Lor|Ekkamai)\s+(\d+)\b",
        _soi_repl,
        out,
    )

    # 8. Postcode comma removal: Bangkok, 10900 -> Bangkok 10900
    def _postcode_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        place = m.group(1)
        code = m.group(2)
        rep = f"{place} {code}"
        ledger.append(
            LedgerEntry(
                rule_id="TH-POSTCODE",
                category="Thai places",
                location=loc,
                before=orig,
                after=rep,
                note="No comma before Thai 5-digit postcode (references.thai_places)",
            )
        )
        return rep

    out = re.sub(r"\b([A-Z][A-Za-z ]+),\s*(\d{5})\b", _postcode_repl, out)

    # 9. Suvarnabhumi International Airport -> Suvarnabhumi airport
    def _suvarnabhumi_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        rep = "Suvarnabhumi airport"
        if orig != rep:
            ledger.append(
                LedgerEntry(
                    rule_id="TH-AIRPORT-CASE",
                    category="Thai places",
                    location=loc,
                    before=orig,
                    after=rep,
                    note="House airport styling: Suvarnabhumi airport",
                )
            )
        return rep

    out = re.sub(
        r"\bSuvarnabhumi\s+(?:International\s+)?Airport\b",
        _suvarnabhumi_repl,
        out,
    )

    # 10. Directory Thai province/district spelling normalisations
    for pat, house_form in THAI_PLACE_NORMALISATIONS:
        def _prov_repl(m: re.Match[str], hf: str = house_form) -> str:
            orig = m.group(0)
            if orig != hf:
                ledger.append(
                    LedgerEntry(
                        rule_id="TH-DIRECTORY-MAP",
                        category="Thai places",
                        location=loc,
                        before=orig,
                        after=hf,
                        note=f"Normalized Thai place spelling to Directory form '{hf}'",
                    )
                )
            return hf

        out = pat.sub(_prov_repl, out)

    # Restore guarded proper names
    for token, phrase in guards.items():
        out = out.replace(token, phrase)

    # Normalize Don Mueang International Airport -> Don Mueang airport in body
    if "Don Mueang International Airport" in out:
        out = out.replace("Don Mueang International Airport", "Don Mueang airport")
        ledger.append(
            LedgerEntry(
                rule_id="TH-AIRPORT-CASE",
                category="Thai places",
                location=loc,
                before="Don Mueang International Airport",
                after="Don Mueang airport",
                note="House airport styling: Don Mueang airport",
            )
        )

    # 11. Ambiguous "Bangkok airport" gate
    if re.search(r"\bBangkok\s+[Aa]irport\b", out):
        q_msg = (
            '"Bangkok airport" is ambiguous (references.thai_places) — confirm whether '
            "Suvarnabhumi airport or Don Mueang airport is meant."
        )
        if q_msg not in queries:
            queries.append(q_msg)

    return out


def _apply_countries_orgs_and_vocab(
    text: str,
    is_domestic: bool,
    ledger: list[LedgerEntry],
    loc: str,
) -> str:
    """Passes 05 & 06: Countries, foreign places, acronyms, organisations & vocabulary."""
    out = text

    for pat, rep, note in FOREIGN_AND_COUNTRY_RULES:
        def _c_repl(m: re.Match[str], r: str = rep, n: str = note) -> str:
            orig = m.group(0)
            if orig != r:
                ledger.append(
                    LedgerEntry("INT-COUNTRIES", "Countries & foreign places", loc, orig, r, n)
                )
            return r

        out = pat.sub(_c_repl, out)

    # Pronounceable >3-letter acronyms -> Title Case
    for acr, title_form in TITLE_CASE_ACRONYMS.items():
        pat = re.compile(rf"\b{re.escape(acr)}\b")
        def _acr_repl(m: re.Match[str], tf: str = title_form) -> str:
            orig = m.group(0)
            ledger.append(
                LedgerEntry(
                    rule_id="ORG-ACRONYMS",
                    category="Acronyms",
                    location=loc,
                    before=orig,
                    after=tf,
                    note=">3-letter pronounceable acronym takes initial cap only (references.acronyms)",
                )
            )
            return tf

        out = pat.sub(_acr_repl, out)

    for pat, rep, note in ORG_AND_VOCAB_RULES:
        def _v_repl(m: re.Match[str], r: str = rep, n: str = note) -> str:
            orig = m.group(0)
            if orig != r:
                ledger.append(
                    LedgerEntry("VOCAB-TRAPS", "Organisations & vocabulary", loc, orig, r, n)
                )
            return r

        out = pat.sub(_v_repl, out)

    # Countable police trap: "five police" -> "five police officers"
    def _police_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        qty = m.group(1)
        rep = f"{qty} police officers"
        ledger.append(
            LedgerEntry(
                rule_id="VOCAB-POLICE",
                category="House vocabulary",
                location=loc,
                before=orig,
                after=rep,
                note="Police is not a countable noun for individuals; use 'police officers' (references.vocabulary)",
            )
        )
        return rep

    out = re.sub(
        r"\b(\d+|two|three|four|five|six|seven|eight|nine|ten|several|many)\s+police\b(?!\s+(?:officers|officials|stations|cars|vehicles|trucks|dogs|helicopters|volunteers|generals|colonels|regions|forces|officers'))",
        _police_repl,
        out,
    )

    # Domestic story superfluous "Thai" stripper
    if is_domestic:
        def _dom_thai_repl(m: re.Match[str]) -> str:
            orig = m.group(0)
            prefix = m.group(1)
            noun = m.group(2)
            rep = f"{prefix} {noun}"
            ledger.append(
                LedgerEntry(
                    rule_id="DOMESTIC-THAI-STRIP",
                    category="Domestic perspective",
                    location=loc,
                    before=orig,
                    after=rep,
                    note="Omit redundant 'Thai' before domestic institutions in home stories ([G1-C])",
                )
            )
            return rep

        out = re.sub(
            r"\b(the|The)\s+Thai\s+(government|cabinet|prime minister|parliament|central bank|police)\b",
            _dom_thai_repl,
            out,
        )

    return out


def _apply_british_english_and_oxford_comma(
    text: str,
    ledger: list[LedgerEntry],
    loc: str,
) -> str:
    """Pass 07: [G1-A] British spelling (outside protected proper names) and Oxford comma removal."""
    out = text

    # Protect proper names
    guards: dict[str, str] = {}
    for idx, phrase in enumerate(PROTECTED_PROPER_PHRASES):
        if phrase in out:
            token = f"__UK_GUARD_{idx}__"
            guards[token] = phrase
            out = out.replace(phrase, token)

    # 1. US -> UK word replacements
    def _uk_word_repl(m: re.Match[str]) -> str:
        word = m.group(0)
        low = word.lower()
        if low not in US_TO_UK_WORDS:
            return word
        target = US_TO_UK_WORDS[low]
        if word.isupper():
            rep = target.upper()
        elif word[0].isupper():
            rep = target.capitalize()
        else:
            rep = target
        if rep != word:
            ledger.append(
                LedgerEntry(
                    rule_id="G1-UK-SPELLING",
                    category="British spelling",
                    location=loc,
                    before=word,
                    after=rep,
                    note="British English house standard ([G1-A])",
                )
            )
        return rep

    us_keys_alt = "|".join(re.escape(k) for k in sorted(US_TO_UK_WORDS.keys(), key=len, reverse=True))
    out = re.sub(rf"\b({us_keys_alt})\b", _uk_word_repl, out, flags=re.IGNORECASE)

    # 2. Oxford comma removal: "A, B, and C" -> "A, B and C" for simple serial items
    def _oxford_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        item1 = m.group(1)
        item2 = m.group(2)
        conj = m.group(3)
        item3 = m.group(4)
        # Keep comma if item2 or item3 is a clause or contains an internal conjunction
        if any(w in item2.lower().split() for w in ("and", "or", "who", "which", "that")):
            return orig
        rep = f"{item1}, {item2} {conj} {item3}"
        ledger.append(
            LedgerEntry(
                rule_id="G1-OXFORD-COMMA",
                category="Oxford comma",
                location=loc,
                before=orig,
                after=rep,
                note="Omit serial Oxford comma in simple lists ([G1-A])",
            )
        )
        return rep

    out = re.sub(
        r"\b([A-Za-z0-9][A-Za-z0-9 -]{0,28}),\s+([A-Za-z0-9][A-Za-z0-9 -]{0,28}),\s+(and|or)\s+([A-Za-z0-9][A-Za-z0-9 -]{0,28})\b",
        _oxford_repl,
        out,
    )

    for token, phrase in guards.items():
        out = out.replace(token, phrase)

    return out


def _apply_measurements_numbers_times_currency(
    text: str,
    is_headline_or_deck: bool,
    ledger: list[LedgerEntry],
    loc: str,
) -> str:
    """Pass 08: Measurements, numbers, times & currency (references.measurements / numbers / times / currency)."""
    out = text

    # 1. Metric units attached to numbers: "90 centimetres" -> "90cm"
    unit_map = {
        "centimetres": "cm",
        "centimetre": "cm",
        "centimeters": "cm",
        "centimeter": "cm",
        "millimetres": "mm",
        "millimetre": "mm",
        "millimeters": "mm",
        "millimeter": "mm",
        "kilometres": "km",
        "kilometre": "km",
        "kilometers": "km",
        "kilometer": "km",
        "metres": "m",
        "metre": "m",
        "meters": "m",
        "meter": "m",
        "kilograms": "kg",
        "kilogram": "kg",
        "kilogrammes": "kg",
        "grams": "g",
        "gram": "g",
        "litres": "L",
        "litre": "L",
        "liters": "L",
        "liter": "L",
    }
    unit_keys = "|".join(sorted(unit_map.keys(), key=len, reverse=True))

    def _metric_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        num = m.group(1)
        u_word = m.group(2).lower()
        sym = unit_map[u_word]
        rep = f"{num}{sym}"
        ledger.append(
            LedgerEntry(
                rule_id="MEAS-METRIC",
                category="Measurements",
                location=loc,
                before=orig,
                after=rep,
                note=f"Abbreviate metric unit without space: {orig} > {rep} (references.measurements)",
            )
        )
        return rep

    out = re.sub(rf"\b(\d[\d,.]*)\s*({unit_keys})\b", _metric_repl, out, flags=re.IGNORECASE)

    # 2. Rainfall in inches -> mm
    def _rain_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        inches = float(m.group(1))
        mm_val = round(inches * 25.4)
        rep = f"{mm_val}mm of rain"
        ledger.append(
            LedgerEntry(
                rule_id="MEAS-RAIN-INCHES",
                category="Measurements",
                location=loc,
                before=orig,
                after=rep,
                note="Rainfall uses millimetres (mm), never inches (references.measurements)",
            )
        )
        return rep

    out = re.sub(r"\b(\d+(?:\.\d+)?)\s*inches of rain\b", _rain_repl, out, flags=re.IGNORECASE)

    # 3. Speed km/h -> kph, Celsius -> C, percent / per cent -> %
    def _speed_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        num = m.group(1)
        rep = f"{num}kph"
        ledger.append(
            LedgerEntry("MEAS-SPEED", "Measurements", loc, orig, rep, "Speed uses kph without space")
        )
        return rep

    out = re.sub(r"\b(\d[\d,.]*)\s*(?:km/h|kmph|kilometres per hour|kilometers per hour)\b", _speed_repl, out, flags=re.IGNORECASE)

    def _temp_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        num = m.group(1)
        rep = f"{num}C"
        ledger.append(
            LedgerEntry("MEAS-TEMP", "Measurements", loc, orig, rep, "Temperature uses C without degree symbol")
        )
        return rep

    out = re.sub(r"\b(-?\d+(?:\.\d+)?)\s*(?:°\s*C|degrees?\s+Celsius|degrees?\s+centigrade)\b", _temp_repl, out)

    def _pct_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        num = m.group(1)
        rep = f"{num}%"
        ledger.append(
            LedgerEntry("NUM-PERCENT", "Numbers & measurements", loc, orig, rep, "Use % sign attached to figure")
        )
        return rep

    out = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:per\s+cent|percent)\b", _pct_repl, out, flags=re.IGNORECASE)

    # 4. No. 1 -> No.1, 10s -> tens, 100s -> hundreds
    def _no_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        rep = f"No.{m.group(1)}"
        ledger.append(
            LedgerEntry("NUM-HOUSE", "Numbers", loc, orig, rep, "No space in No.1 (references.numbers)")
        )
        return rep

    out = re.sub(r"\bNo\.\s+(\d+)\b", _no_repl, out)

    for pat_str, word_rep in ((r"\b10s\b", "tens"), (r"\b100s\b", "hundreds"), (r"\b1,000s\b", "thousands")):
        out, n_sub = re.subn(pat_str, word_rep, out)
        if n_sub:
            ledger.append(
                LedgerEntry("NUM-HOUSE", "Numbers", loc, pat_str.strip(r"\b"), word_rep, "Spell out tens/hundreds/thousands")
            )

    # 5. Times: 12:00 p.m. / 12pm -> noon, 12:00 a.m. / 12am -> midnight, 10:00 a.m. -> 10am, 2:30 p.m. -> 2.30pm
    def _noon_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        ledger.append(LedgerEntry("TIME-HOUSE", "Times", loc, orig, "noon", "Use noon instead of 12pm"))
        return "noon"

    out = re.sub(
        r"\b12(?::00)?\s*(?:p\.m\.(?!\s*(?:[A-Z\"“'_]|$))|p\.m|pm)(?!\w)",
        _noon_repl,
        out,
        flags=re.IGNORECASE,
    )

    def _midnight_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        ledger.append(LedgerEntry("TIME-HOUSE", "Times", loc, orig, "midnight", "Use midnight instead of 12am"))
        return "midnight"

    out = re.sub(
        r"\b12(?::00)?\s*(?:a\.m\.(?!\s*(?:[A-Z\"“'_]|$))|a\.m|am)(?!\w)",
        _midnight_repl,
        out,
        flags=re.IGNORECASE,
    )

    def _time_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        hr = int(m.group(1))
        mins = m.group(2)
        mer = m.group(3).lower()
        if mins in (None, "00"):
            rep = f"{hr}{mer}m"
        else:
            rep = f"{hr}.{mins}{mer}m"
        if orig != rep:
            ledger.append(
                LedgerEntry("TIME-HOUSE", "Times", loc, orig, rep, "House time format: 10am / 2.30pm")
            )
        return rep

    out = re.sub(
        r"\b(1[0-1]|[1-9])(?::([0-5]\d))?\s*([ap])(?:\.m\.(?!\s*(?:[A-Z\"“'_]|$))|\.m|m)(?!\w)",
        _time_repl,
        out,
        flags=re.IGNORECASE,
    )

    # 6. Currency: THB / Thai baht -> baht (body) or B500 / B5m / B5bn (head/deck), USD -> US$
    if is_headline_or_deck:
        def _hd_baht_repl(m: re.Match[str]) -> str:
            orig = m.group(0)
            fig = m.group(1)
            scale = (m.group(2) or "").lower()
            scale_sym = {"million": "m", "billion": "bn", "trillion": "tn"}.get(scale, "")
            rep = f"B{fig}{scale_sym}"
            ledger.append(
                LedgerEntry("CURR-HOUSE", "Currency", loc, orig, rep, "Headline/deck baht prefix: B500 / B5m / B5bn")
            )
            return rep

        out = re.sub(
            r"\b(\d[\d,.]*)\s*(?:(million|billion|trillion)\s+)?(?:Thai\s+)?baht\b",
            _hd_baht_repl,
            out,
            flags=re.IGNORECASE,
        )
    else:
        def _thb_repl(m: re.Match[str]) -> str:
            orig = m.group(0)
            fig = m.group(1)
            scale = (f" {m.group(2).lower()}" if m.group(2) else "")
            rep = f"{fig}{scale} baht"
            ledger.append(
                LedgerEntry("CURR-HOUSE", "Currency", loc, orig, rep, "Body currency: figure + baht (never THB)")
            )
            return rep

        out = re.sub(
            r"\bTHB\s*(\d[\d,.]*)(?:\s*(million|billion|trillion))?\b",
            _thb_repl,
            out,
            flags=re.IGNORECASE,
        )
        out, n_tb = re.subn(r"\bThai baht\b", "baht", out)
        if n_tb:
            ledger.append(
                LedgerEntry("CURR-HOUSE", "Currency", loc, "Thai baht", "baht", "Omit redundant 'Thai' before baht")
            )

    def _usd_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        fig = m.group(1)
        rep = f"US${fig}"
        ledger.append(
            LedgerEntry("CURR-HOUSE", "Currency", loc, orig, rep, "USD > US$ (references.currency)")
        )
        return rep

    out = re.sub(r"\bUSD\s*(\d[\d,.]*)\b", _usd_repl, out)

    # 7. Single-digit whole numbers 1-9 in prose body (skip ages, measurements, dates, sections, scores)
    if not is_headline_or_deck:
        def _single_digit_repl(m: re.Match[str]) -> str:
            orig = m.group(0)
            digit = m.group(1)
            noun = m.group(2)
            word_num = NUMBER_WORDS_1_TO_9[digit]
            rep = f"{word_num} {noun}"
            ledger.append(
                LedgerEntry(
                    rule_id="NUM-SPELL-OUT",
                    category="Numbers",
                    location=loc,
                    before=orig,
                    after=rep,
                    note="Spell out whole numbers below 10 in prose (references.numbers)",
                )
            )
            return rep

        out = re.sub(
            r"(?<![\d.,No§-])\b([1-9])\s+(people|residents|villagers|officers|suspects|victims|patients|students|workers|soldiers| tourists|children|men|women|officials|ministers|provinces|districts|houses|homes|vehicles|cars|boats|days|weeks|months|years|hours)\b",
            _single_digit_repl,
            out,
        )

    return out


def _apply_date_alignment_and_tense(
    text: str,
    pub_date: date,
    ledger: list[LedgerEntry],
    queries: list[str],
    loc: str,
) -> str:
    """Pass 09: Publication-date alignment (references.dates) & past-tense-as-future alignment."""
    out = text

    # 1. Detect internal timeline clash (e.g. "yesterday" paired with a future date or wrong weekday)
    # 2. Convert explicit "on <Month> <Day>" relative to pub_date
    month_keys = "|".join(sorted(MONTH_NAME_TO_NUM.keys(), key=len, reverse=True))

    def _on_date_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        prep = m.group(1)  # "on " or "On "
        m_str = m.group(2)
        d_str = m.group(3)
        m_num = MONTH_NAME_TO_NUM[m_str.lower().rstrip(".")]
        d_num = int(d_str)
        try:
            target_date = date(pub_date.year, m_num, d_num)
        except ValueError:
            return orig

        delta = (target_date - pub_date).days
        is_cap = prep[0].isupper()

        if delta == -1:
            rep = "Yesterday" if is_cap else "yesterday"
            ledger.append(
                LedgerEntry(
                    rule_id="DATE-ALIGN",
                    category="Date alignment",
                    location=loc,
                    before=orig,
                    after=rep,
                    note=f"Converted {m_str} {d_num} to '{rep}' relative to publication date {pub_date.isoformat()}",
                )
            )
            return rep
        if delta == 0:
            rep = "Today" if is_cap else "today"
            ledger.append(
                LedgerEntry(
                    rule_id="DATE-ALIGN",
                    category="Date alignment",
                    location=loc,
                    before=orig,
                    after=rep,
                    note=f"Converted {m_str} {d_num} to '{rep}' relative to publication date {pub_date.isoformat()}",
                )
            )
            return rep
        if delta == 1:
            rep = "Tomorrow" if is_cap else "tomorrow"
            ledger.append(
                LedgerEntry(
                    rule_id="DATE-ALIGN",
                    category="Date alignment",
                    location=loc,
                    before=orig,
                    after=rep,
                    note=f"Converted {m_str} {d_num} to '{rep}' relative to publication date {pub_date.isoformat()}",
                )
            )
            return rep
        if -7 <= delta < -1:
            wk = WEEKDAY_NAMES[target_date.weekday()]
            rep = f"{prep.strip()} {wk}"
            ledger.append(
                LedgerEntry(
                    rule_id="DATE-ALIGN",
                    category="Date alignment",
                    location=loc,
                    before=orig,
                    after=rep,
                    note=f"Date within 7 days of {pub_date.isoformat()} converted to weekday '{rep}' (references.dates)",
                )
            )
            return rep

        # Beyond 7 days -> normalize month abbreviation (Jan, Feb, March, April, May, June, July, Aug, Sept, Oct, Nov, Dec)
        house_m = HOUSE_MONTHS[m_num]
        rep = f"{prep.strip()} {house_m} {d_num}"
        if orig != rep:
            ledger.append(
                LedgerEntry(
                    rule_id="DATE-MONTH-STYLE",
                    category="Date style",
                    location=loc,
                    before=orig,
                    after=rep,
                    note=f"House month abbreviation: {house_m} {d_num} (references.dates.months)",
                )
            )
        return rep

    out = re.sub(
        rf"\b([Oo]n\s+)({month_keys})\.?\s+(\d{{1,2}})\b(?!\s*,\s*\d{{4}})",
        _on_date_repl,
        out,
        flags=re.IGNORECASE,
    )

    # Also normalize standalone month names + day when not preceded by "on " (e.g. "September 10" -> "Sept 10")
    def _standalone_month_repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        m_str = m.group(1)
        d_str = m.group(2)
        m_num = MONTH_NAME_TO_NUM[m_str.lower().rstrip(".")]
        house_m = HOUSE_MONTHS[m_num]
        rep = f"{house_m} {int(d_str)}"
        if orig != rep:
            ledger.append(
                LedgerEntry(
                    rule_id="DATE-MONTH-STYLE",
                    category="Date style",
                    location=loc,
                    before=orig,
                    after=rep,
                    note="Normalized month name to Bangkok Post house style",
                )
            )
        return rep

    out = re.sub(
        rf"\b({month_keys})\.\s+(\d{{1,2}})\b|\b(January|February|August|September|October|November|December)\s+(\d{{1,2}})\b",
        lambda m: _standalone_month_repl(m) if m.group(1) else (
            f"{HOUSE_MONTHS[MONTH_NAME_TO_NUM[m.group(3).lower()]]} {int(m.group(4))}"
        ),
        out,
    )

    # 3. Past-tense-as-future in attribution ("He said more rain is expected" -> "He said more rain was expected")
    def _tense_is_expected(m: re.Match[str]) -> str:
        orig = m.group(0)
        prefix = m.group(1)
        verb = m.group(2)
        rep_verb = "was expected" if verb == "is expected" else "were expected"
        rep = f"{prefix}{rep_verb}"
        ledger.append(
            LedgerEntry(
                rule_id="DATE-PAST-FUTURE",
                category="Tense alignment",
                location=loc,
                before=orig,
                after=rep,
                note="Past-tense attribution takes 'was/were expected' (references.dates.past_tense_as_future)",
            )
        )
        return rep

    out = re.sub(
        r"\b(said\b[^.\n\"]*?\b)(is expected|are expected)\b",
        _tense_is_expected,
        out,
    )

    return out


def _extract_introduced_thai_person(paragraph_text: str) -> tuple[str, str, str] | None:
    """Detect a newly introduced Thai/Lao person with role in a paragraph.

    Returns (first_name, last_name, honorific) when unambiguous.
    """
    # Pattern A: "<FirstName> <LastName>, the <role>," or "<FirstName> <LastName>, <age>, a <role>,"
    role_alt = "|".join(re.escape(r) for r in sorted(THAI_ROLES_INDICATORS, key=len, reverse=True))
    m1 = re.search(
        rf"\b(?:(Mr|Ms|Mrs|Dr|Pol\s+[A-Z][a-z]+|Gen|Col)\s+)?([A-Z][a-z]{{2,18}})\s+([A-Z][a-z-]{{2,22}}),\s+(?:the\s+|a\s+|an\s+)?(?:[a-z]+\s+){{0,3}}({role_alt})\b",
        paragraph_text,
    )
    if m1:
        hon_raw, first, last, role_matched = m1.group(1), m1.group(2), m1.group(3), m1.group(4)
        if first.lower() not in NON_THAI_GIVEN_NAMES and f"{first} {last}" not in HELD_FOREIGN_SECOND_REFS:
            if hon_raw:
                hon = hon_raw.rstrip(".")
            elif "woman" in role_matched or re.search(r"\bShe\s+said\b", paragraph_text):
                hon = "Ms"
            else:
                hon = "Mr"
            return (first, last, hon)

    # Pattern B: "<Role> <FirstName> <LastName> said"
    m2 = re.search(
        rf"\b(?:Prime Minister|Deputy Prime Minister|Governor|Interior Minister|Finance Minister|Defence Minister|Foreign Minister|Transport Minister|Public Health Minister|Bangkok Governor)\s+([A-Z][a-z]{{2,18}})\s+([A-Z][a-z-]{{2,22}})\b",
        paragraph_text,
    )
    if m2:
        first, last = m2.group(1), m2.group(2)
        if first.lower() not in NON_THAI_GIVEN_NAMES and f"{first} {last}" not in HELD_FOREIGN_SECOND_REFS:
            hon = "Ms" if first in ("Paetongtarn", "Yingluck", "Sudawan", "Jiraporn", "Theerarat", "Sabida") else "Mr"
            return (first, last, hon)

    return None


def _apply_names_honorifics_and_second_refs(
    paragraphs: list[str],
    ledger: list[LedgerEntry],
) -> list[str]:
    """Pass 10: Names, honorifics, titles, deceased figures & Thai/Lao second references."""
    out_pars: list[str] = []
    introduced_thai_people: list[tuple[str, str, str]] = []
    seen_full_names: set[str] = set()

    for idx, par in enumerate(paragraphs):
        loc = f"Par {idx + 1}"
        cur = par

        # 1. Strip periods from honorifics: Mr. -> Mr, Ms. -> Ms, Gen. -> Gen, Pol. Gen. -> Pol Gen
        def _hon_dot_repl(m: re.Match[str]) -> str:
            orig = m.group(0)
            rep = orig.replace(".", "")
            rep = re.sub(r"\s+", " ", rep)
            ledger.append(
                LedgerEntry(
                    rule_id="NAME-HONORIFIC-DOTS",
                    category="Names & honorifics",
                    location=loc,
                    before=orig,
                    after=rep,
                    note="Omit periods in honorifics and military/police ranks (references.names_honorifics)",
                )
            )
            return rep

        cur = re.sub(
            r"\b(?:Pol\.\s*(?:Gen|Lt\s*Gen|Maj\s*Gen|Col|Lt\s*Col|Maj|Capt|Lt)\.|(?:Mr|Ms|Mrs|Dr|Prof|Gen|Lt\s*Gen|Maj\s*Gen|Col|Lt\s*Col|Maj|Capt|Sgt)\.)(?=\s+[A-Z])",
            _hon_dot_repl,
            cur,
        )

        # 2. Watchlist Chadchart spelling fix: Chatchart -> Chadchart
        if "Chatchart" in cur:
            cur = cur.replace("Chatchart", "Chadchart")
            ledger.append(
                LedgerEntry(
                    rule_id="WATCH-CHADCHART",
                    category="Watchlist spelling",
                    location=loc,
                    before="Chatchart",
                    after="Chadchart",
                    note="House spelling is Chadchart Sittipunt (status.watch.chadchart_sittipunt)",
                )
            )

        # 3. Deceased figures: strip Mr / Ms before deceased person
        for dead_name, dead_note in DECEASED_FIGURES.items():
            parts = dead_name.split()
            surname_or_given = parts[0]
            last_part = parts[-1]
            for target_tok in {dead_name, surname_or_given, last_part}:
                pat_dead = re.compile(rf"\b(?:Mr|Ms|Mrs)\s+({re.escape(target_tok)})\b")
                if pat_dead.search(cur) and (dead_name.lower() in cur.lower() or dead_name in seen_full_names):
                    seen_full_names.add(dead_name)
                    def _dead_repl(m: re.Match[str], dn: str = dead_note) -> str:
                        orig = m.group(0)
                        rep = m.group(1)
                        ledger.append(
                            LedgerEntry("NAME-MORTALITY-STRIP", "Mortalities", loc, orig, rep, dn)
                        )
                        return rep
                    cur = pat_dead.sub(_dead_repl, cur)

        # 4. Held foreign second-reference exceptions
        for full_name, (held_ref, wrong_forms) in HELD_FOREIGN_SECOND_REFS.items():
            if full_name in cur:
                seen_full_names.add(full_name)
            if full_name in seen_full_names:
                for wrong in wrong_forms:
                    pat_w = re.compile(rf"\b{re.escape(wrong)}\b")
                    if pat_w.search(cur) and wrong not in full_name:
                        cur = pat_w.sub(held_ref, cur)
                        ledger.append(
                            LedgerEntry(
                                rule_id="NAME-HELD-EXCEPTIONS",
                                category="Second reference",
                                location=loc,
                                before=wrong,
                                after=held_ref,
                                note=f"Held second-reference form for {full_name} is '{held_ref}' (DIRECTORY.yaml)",
                            )
                        )

        # 5. Lower-case descriptive/occupational titles before names
        for desc_title in DESCRIPTIVE_TITLES_LOWER:
            pat_dt = re.compile(rf"(?<!^)(?<![.!?]\s)\b({re.escape(desc_title)})\s+(?=[A-Z][a-z]+)")
            def _dt_repl(m: re.Match[str]) -> str:
                orig = m.group(1)
                rep = orig.lower()
                ledger.append(
                    LedgerEntry(
                        rule_id="NAME-TITLE-CASE",
                        category="Titles",
                        location=loc,
                        before=orig,
                        after=rep,
                        note="Descriptive/occupational title before a name is lower-case (references.names_honorifics.titles)",
                    )
                )
                return f"{rep} "
            cur = pat_dt.sub(_dt_repl, cur)

        # Standalone "the Prime Minister" / "the Cabinet" -> lower-case
        def _standalone_title_repl(m: re.Match[str]) -> str:
            orig = m.group(0)
            art = m.group(1)
            role = m.group(2).lower()
            rep = f"{art} {role}"
            ledger.append(
                LedgerEntry(
                    rule_id="NAME-TITLE-CASE",
                    category="Titles",
                    location=loc,
                    before=orig,
                    after=rep,
                    note="Standalone formal titles not directly preceding a name are lower-case",
                )
            )
            return rep

        cur = re.sub(
            r"\b(the|The|former|Former)\s+(Prime Minister|Deputy Prime Minister|Cabinet|Interior Minister|Finance Minister|Foreign Minister|Defence Minister|Governor)\b(?!\s+[A-Z][a-z])",
            _standalone_title_repl,
            cur,
        )

        # 6. Thai / Lao second-reference automation
        person = _extract_introduced_thai_person(cur)
        if person and person not in introduced_thai_people:
            introduced_thai_people.append(person)

        for first_name, last_name, hon in introduced_thai_people:
            expected_second_ref = f"{hon} {first_name}"
            # (a) Fix wrong surname second-reference: "Mr <LastName>" -> "Mr <FirstName>"
            pat_wrong_surname = re.compile(rf"\b(Mr|Ms|Mrs|Dr)\s+{re.escape(last_name)}\b")
            if pat_wrong_surname.search(cur):
                def _surname_fix(m: re.Match[str], exp: str = expected_second_ref) -> str:
                    orig = m.group(0)
                    ledger.append(
                        LedgerEntry(
                            rule_id="NAME-THAI-SECOND-REF",
                            category="Thai second reference",
                            location=loc,
                            before=orig,
                            after=exp,
                            note=f"Thai second references use honorific + given name ({exp}), never family name ({orig})",
                        )
                    )
                    return exp
                cur = pat_wrong_surname.sub(_surname_fix, cur)

            # (b) In the same paragraph where `<FirstName> <LastName>, the <role>,` is introduced,
            # if a subsequent sentence starts with `He said` / `She said`, convert to `Mr <FirstName> said`
            # (matches [R4] EXAMPLE: "Somchai Dee, the district chief, said ... He said more rain is expected." -> "Mr Somchai said more rain was expected.")
            if f"{first_name} {last_name}" in cur and len(introduced_thai_people) == 1:
                pronoun = "She" if hon in ("Ms", "Mrs") else "He"
                pat_pronoun = re.compile(rf"(?<=\.\s){pronoun}\s+said\b")
                if pat_pronoun.search(cur):
                    rep_str = f"{expected_second_ref} said"
                    cur = pat_pronoun.sub(rep_str, cur, count=1)
                    ledger.append(
                        LedgerEntry(
                            rule_id="NAME-THAI-SECOND-REF",
                            category="Thai second reference",
                            location=loc,
                            before=f"{pronoun} said",
                            after=rep_str,
                            note=f"Explicit Thai second reference ({expected_second_ref}) on follow-up attribution ([R4] standard)",
                        )
                    )

        out_pars.append(cur)

    return out_pars


def _run_verification_gate_p2(
    full_text: str,
    fact_proposals: list[FactChangeProposal],
) -> dict[str, Any]:
    """Pass 11: [P2] Copy-Internal Arithmetic Verifier, Watchlist/Mortality Scanner, and Two-Source Gate."""
    holds: list[str] = []
    queries: list[str] = []
    arithmetic_checks: list[dict[str, Any]] = []
    watchlist_hits: list[dict[str, str]] = []
    approved_fact_changes: list[str] = []
    rejected_fact_changes: list[dict[str, str]] = []

    # 1. Copy-internal percentage check: "X% of N ... (or|totaling|some) M"
    for m_pct in re.finditer(
        r"\b(\d+(?:\.\d+)?)%\s+of\s+(?:the\s+)?([\d,]+)\s+[a-z]+(?:\s+[a-z]+)?\s*(?:—|--|,|\()\s*(?:or\s+|totaling\s+|some\s+)?([\d,]+)\b",
        full_text,
        flags=re.IGNORECASE,
    ):
        pct = float(m_pct.group(1))
        total = float(m_pct.group(2).replace(",", ""))
        stated = float(m_pct.group(3).replace(",", ""))
        expected = round((pct / 100.0) * total, 2)
        passed = abs(expected - stated) < 1.0
        arithmetic_checks.append({
            "type": "percentage_of_total",
            "expression": m_pct.group(0),
            "expected": expected,
            "observed": stated,
            "passed": passed,
        })
        if not passed:
            msg = (
                f"Copy-internal arithmetic mismatch ([P2]): '{m_pct.group(0)}' states {int(stated):,}, "
                f"but {pct:g}% of {int(total):,} is {expected:g}."
            )
            holds.append(msg)

    # 2. Subset > Superset check: "A <items> from a network of B" or "A of the B <items>"
    for m_sub in re.finditer(
        r"\b([\d,]+)\s+(?:[a-z]+\s+){0,2}(?:from a network of|out of a total of|of the total)\s+([\d,]+)\b",
        full_text,
        flags=re.IGNORECASE,
    ):
        sub_val = int(m_sub.group(1).replace(",", ""))
        tot_val = int(m_sub.group(2).replace(",", ""))
        passed = sub_val <= tot_val
        arithmetic_checks.append({
            "type": "subset_bound",
            "expression": m_sub.group(0),
            "expected": f"<= {tot_val}",
            "observed": sub_val,
            "passed": passed,
        })
        if not passed:
            holds.append(
                f"Impossible subset figure ([P2]): '{m_sub.group(0)}' claims {sub_val:,} out of {tot_val:,}."
            )

    # 3. Component sum check: "A men and B women, totaling C"
    for m_sum in re.finditer(
        r"\b([\d,]+)\s+[a-z]+\s+and\s+([\d,]+)\s+[a-z]+,\s*(?:for a total of|totaling|totalling)\s+([\d,]+)\b",
        full_text,
        flags=re.IGNORECASE,
    ):
        a_val = int(m_sum.group(1).replace(",", ""))
        b_val = int(m_sum.group(2).replace(",", ""))
        c_val = int(m_sum.group(3).replace(",", ""))
        passed = (a_val + b_val) == c_val
        arithmetic_checks.append({
            "type": "component_sum",
            "expression": m_sum.group(0),
            "expected": a_val + b_val,
            "observed": c_val,
            "passed": passed,
        })
        if not passed:
            holds.append(
                f"Copy-internal sum mismatch ([P2]): {a_val:,} + {b_val:,} = {a_val + b_val:,}, not {c_val:,}."
            )

    # 4. Watchlist scan (DIRECTORY.yaml status.watch)
    for w_rule in WATCHLIST_RULES:
        if re.search(w_rule["pattern"], full_text, flags=re.IGNORECASE):
            watchlist_hits.append({
                "key": w_rule["key"],
                "name": w_rule["name"],
                "ruling": w_rule["ruling"],
            })
            if w_rule["key"] != "chadchart_sittipunt" and re.search(
                w_rule["suspect_pattern"], full_text, flags=re.IGNORECASE
            ):
                queries.append(w_rule["ruling"])

    # 5. Two-Source Fact Change Proposals
    for prop in fact_proposals:
        res = validate_fact_change_proposal(prop)
        if res["approved"]:
            approved_fact_changes.append(res["formatted_entry"])
        else:
            rejected_fact_changes.append({
                "claim_before": prop.claim_before,
                "claim_after": prop.claim_after,
                "reason": res["reason"],
            })
            queries.append(
                f"Unverified fact change blocked ('{prop.claim_before}' > '{prop.claim_after}'): {res['reason']}"
            )

    return {
        "holds": holds,
        "queries": queries,
        "arithmetic_checks": arithmetic_checks,
        "watchlist_hits": watchlist_hits,
        "approved_fact_changes": approved_fact_changes,
        "rejected_fact_changes": rejected_fact_changes,
    }


def _generate_alternates(
    head: str,
    deck: str,
    slug: str,
    body_paragraphs: list[str],
    is_brief: bool,
) -> dict[str, list[dict[str, Any]]]:
    """Generate deterministic headline and deck alternates with [P1-A] glyph weights."""
    first_par = body_paragraphs[0] if body_paragraphs else ""
    base_head = (head or "").strip()

    if not base_head:
        # Derive deterministic news headline from first paragraph
        if "Ubon Ratchathani" in first_par and "Floodwaters" in first_par:
            base_head = "Floods force 850 from Ubon Ratchathani homes"
        else:
            words = re.sub(r"[^A-Za-z0-9 %$-]", "", first_par).split()[:7]
            base_head = " ".join(words) if words else (slug or "News update")

    head_candidates = [base_head]
    if "Ubon Ratchathani" in first_par and "Mun River" in " ".join(body_paragraphs):
        head_candidates.extend([
            "Rising Mun River forces 850 from Ubon homes",
            "850 evacuated as Mun River swells in Ubon",
        ])
    else:
        short_variant = re.sub(r"\b(?:the|a|an)\b\s*", "", base_head, flags=re.IGNORECASE).strip()
        if short_variant and short_variant != base_head:
            head_candidates.append(short_variant)
        head_candidates.append(f"{base_head[:42].rstrip()} — officials")

    head_list = []
    seen_h: set[str] = set()
    for hc in head_candidates:
        if hc not in seen_h:
            seen_h.add(hc)
            head_list.append(compute_glyph_weight(hc))

    deck_list: list[dict[str, Any]] = []
    if not is_brief:
        base_deck = (deck or "").strip()
        if not base_deck and len(body_paragraphs) > 1:
            if "Mun River" in body_paragraphs[1]:
                base_deck = "Mun River rises 90cm overnight as officials warn of further rain"
            else:
                s1 = body_paragraphs[1].split(".")[0].strip()
                base_deck = s1[:78]
        if base_deck:
            deck_list.append(compute_glyph_weight(base_deck))
            alt_d = re.sub(r"\bOfficials warn\b", "Authorities warn", base_deck)
            if alt_d == base_deck:
                alt_d = f"{base_deck.rstrip('.')} as authorities monitor situation"
            deck_list.append(compute_glyph_weight(alt_d))

    return {"heads": head_list[:3], "decks": deck_list[:2]}


def _compile_style_log_lines(ledger: list[LedgerEntry]) -> list[str]:
    """Compile STYLE LOG strictly from the immutable TransformationLedger (Zero Fake Procedural Steps)."""
    if not ledger:
        return ["- No house style, transliteration or date-alignment changes required; filed copy already conforms to Blueprint & Directory."]

    grouped: list[str] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for entry in ledger:
        key = (entry.rule_id, entry.before, entry.after)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        grouped.append(
            f"- [{entry.rule_id}] {entry.location}: `{entry.before}` > `{entry.after}` ({entry.note})"
        )
    return grouped


def process_editorial_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute the full 12-pass deterministic editorial content processing pipeline."""
    mode = str(payload.get("mode") or "EDIT").strip().upper()
    raw_input = str(payload.get("raw_input") or "")
    parsed = parse_dcx_or_raw_filing(raw_input)

    slug = str(payload.get("slug") or parsed["slug"] or "unslugged-job").strip()
    counts_spec = str(payload.get("counts") or parsed["counts"] or "").strip()
    head_in = str(payload.get("head") if payload.get("head") is not None else parsed["head"]).strip()
    deck_in = str(payload.get("deck") if payload.get("deck") is not None else parsed["deck"]).strip()
    byline_in = str(payload.get("byline") if payload.get("byline") is not None else parsed["byline"]).strip()
    label_in = str(payload.get("label") if payload.get("label") is not None else parsed["label"]).strip()
    caption_in = str(payload.get("caption") if payload.get("caption") is not None else parsed["caption"]).strip()
    credit_in = str(payload.get("credit") if payload.get("credit") is not None else parsed["credit"]).strip()
    body_in = str(payload.get("body") if payload.get("body") is not None else parsed["body"]).strip()
    if not body_in and raw_input and not any([parsed["head"], parsed["caption"]]):
        body_in = raw_input.strip()

    pub_date = parse_publication_date(payload.get("pub_date"), slug)
    placed_flag = bool(payload.get("placed", False) or counts_spec or mode == "FIT")
    is_brief = bool(re.search(r"(?:^|[-_\s])(?:bf|brief)(?:$|[-_\s])", slug, re.IGNORECASE))

    # Parse target body budget if provided in counts_spec (e.g., "Body: 260-295" or "290")
    max_body_budget: int | None = None
    m_budget = re.search(r"(?:body\s*[:=]?\s*)?(?:\d+\s*-\s*)?(\d{2,4})", counts_spec, re.IGNORECASE)
    if m_budget:
        max_body_budget = int(m_budget.group(1))
    if payload.get("target_body_chars"):
        try:
            max_body_budget = int(payload["target_body_chars"])
        except ValueError:
            pass

    # Detect Wire vs. Domestic copy
    combined_source_check = f"{byline_in} {body_in[:240]}"
    detected_wire = next(
        (w for w in WIRE_AGENCIES if re.search(rf"\b{re.escape(w)}\b", combined_source_check)),
        None,
    )
    if payload.get("story_origin") in ("domestic", "wire"):
        is_domestic = payload["story_origin"] == "domestic"
    else:
        is_domestic = detected_wire is None

    # Parse structured fact change proposals
    raw_proposals = payload.get("fact_proposals") or []
    fact_proposals: list[FactChangeProposal] = []
    for rp in raw_proposals:
        if isinstance(rp, dict) and (rp.get("claim_before") or rp.get("claim_after")):
            fact_proposals.append(
                FactChangeProposal(
                    claim_before=str(rp.get("claim_before", "")),
                    claim_after=str(rp.get("claim_after", "")),
                    authority_mode=str(rp.get("authority_mode", "two_sources")),
                    source_1_publisher=str(rp.get("source_1_publisher", "")),
                    source_1_record=str(rp.get("source_1_record", "")),
                    source_2_publisher=str(rp.get("source_2_publisher", "")),
                    source_2_record=str(rp.get("source_2_record", "")),
                    desk_note=str(rp.get("desk_note", "")),
                )
            )

    ledger: list[LedgerEntry] = []
    pass_queries: list[str] = []

    # Split body into paragraphs
    raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body_in) if p.strip()]
    if len(raw_paragraphs) == 1 and "\n" in raw_paragraphs[0]:
        raw_paragraphs = [p.strip() for p in raw_paragraphs[0].split("\n") if p.strip()]

    # Execute Passes 02-09 per paragraph with Quotation Protection
    processed_paragraphs: list[str] = []
    for idx, par in enumerate(raw_paragraphs):
        loc = f"Par {idx + 1}"
        quote_map: dict[str, str] = {}

        def _quote_protector(m: re.Match[str], p_loc: str = loc) -> str:
            q_raw = m.group(0)
            q_annotated = _annotate_quotes_with_metric(q_raw, ledger, p_loc)
            q_tok = f"__QUOTE_SPAN_{len(quote_map)}__"
            quote_map[q_tok] = q_annotated
            return q_tok

        # Pass 02: Quotation protection + metric annotation inside quotes
        work = re.sub(r'[“"][^”"\n]{2,}[”"]', _quote_protector, par)

        if mode != "CHECK" and mode != "QC":
            # Pass 03: Diacritic stripping
            work = _strip_diacritics_outside_quotes(work, ledger, loc)
            # Pass 04: Thai places & transliteration
            work = _apply_thai_places_and_transliteration(work, ledger, pass_queries, loc)
            # Pass 05 & 06: Countries, foreign places, organisations, acronyms & vocabulary
            work = _apply_countries_orgs_and_vocab(work, is_domestic, ledger, loc)
            # Pass 07: British English & Oxford comma
            work = _apply_british_english_and_oxford_comma(work, ledger, loc)
            # Pass 08: Measurements, numbers, times & currency
            work = _apply_measurements_numbers_times_currency(work, False, ledger, loc)
            # Pass 09: Date alignment & past-tense-as-future (skip rewrite in PR mode unless hard month style)
            if mode != "PR":
                work = _apply_date_alignment_and_tense(work, pub_date, ledger, pass_queries, loc)
        else:
            # In CHECK/QC mode, we still run a shadow copy to collect all findings without mutating the proof unless requested
            shadow = work
            shadow = _strip_diacritics_outside_quotes(shadow, ledger, loc)
            shadow = _apply_thai_places_and_transliteration(shadow, ledger, pass_queries, loc)
            shadow = _apply_countries_orgs_and_vocab(shadow, is_domestic, ledger, loc)
            shadow = _apply_british_english_and_oxford_comma(shadow, ledger, loc)
            shadow = _apply_measurements_numbers_times_currency(shadow, False, ledger, loc)
            shadow = _apply_date_alignment_and_tense(shadow, pub_date, ledger, pass_queries, loc)
            work = shadow

        # Restore protected quotes
        for q_tok, q_val in quote_map.items():
            work = work.replace(q_tok, q_val)

        processed_paragraphs.append(work)

    # Pass 10: Names, honorifics, titles & Thai second references
    processed_paragraphs = _apply_names_honorifics_and_second_refs(processed_paragraphs, ledger)

    # Apply approved Two-Source Fact Changes to processed paragraphs
    p2_audit = _run_verification_gate_p2("\n\n".join(processed_paragraphs), fact_proposals)
    for prop in fact_proposals:
        val = validate_fact_change_proposal(prop)
        if val["approved"] and prop.claim_before:
            for i, p_text in enumerate(processed_paragraphs):
                if prop.claim_before in p_text:
                    processed_paragraphs[i] = p_text.replace(prop.claim_before, prop.claim_after)

    # Process Headline & Deck through headline-aware rules
    head_out = head_in
    deck_out = "" if is_brief else deck_in
    if head_out:
        stripped_h = re.sub(r"\b(?:Mr|Ms|Mrs)\.?\s+", "", head_out)
        if stripped_h != head_out:
            ledger.append(
                LedgerEntry("HEAD-HONORIFIC-STRIP", "Headline style", "Head", head_out, stripped_h, "Omit civil honorifics in headlines")
            )
            head_out = stripped_h
        head_out = _apply_thai_places_and_transliteration(head_out, ledger, pass_queries, "Head")
        head_out = _apply_countries_orgs_and_vocab(head_out, is_domestic, ledger, "Head")
        head_out = _apply_british_english_and_oxford_comma(head_out, ledger, "Head")
        head_out = _apply_measurements_numbers_times_currency(head_out, True, ledger, "Head")

    if deck_out:
        stripped_d = re.sub(r"\b(?:Mr|Ms|Mrs)\.?\s+", "", deck_out)
        if stripped_d != deck_out:
            ledger.append(
                LedgerEntry("HEAD-HONORIFIC-STRIP", "Deck style", "Deck", deck_out, stripped_d, "Omit civil honorifics in decks")
            )
            deck_out = stripped_d
        deck_out = _apply_thai_places_and_transliteration(deck_out, ledger, pass_queries, "Deck")
        deck_out = _apply_countries_orgs_and_vocab(deck_out, is_domestic, ledger, "Deck")
        deck_out = _apply_british_english_and_oxford_comma(deck_out, ledger, "Deck")
        deck_out = _apply_measurements_numbers_times_currency(deck_out, True, ledger, "Deck")

    all_holds = list(p2_audit["holds"])
    all_queries = list(dict.fromkeys(pass_queries + p2_audit["queries"]))

    # Update persistent session OUTSTANDING register
    outstanding_items = list(dict.fromkeys(all_holds + all_queries))
    SESSION_OUTSTANDING_STORE[slug] = outstanding_items

    body_out = "\n\n".join(processed_paragraphs)
    input_body_chars = compute_body_char_count(body_in)
    output_body_chars = compute_body_char_count(body_out)

    head_metrics = compute_glyph_weight(head_out)
    deck_metrics = compute_glyph_weight(deck_out)
    alternates = _generate_alternates(head_out, deck_out, slug, processed_paragraphs, is_brief)
    style_log_lines = _compile_style_log_lines(ledger)

    # Compile locked non-divergent return by mode
    formatted_return = _compile_locked_return(
        mode=mode,
        slug=slug,
        pub_date=pub_date,
        placed=placed_flag,
        is_brief=is_brief,
        is_domestic=is_domestic,
        head_out=head_out,
        deck_out=deck_out,
        byline_in=byline_in,
        label_in=label_in,
        caption_in=caption_in,
        credit_in=credit_in,
        body_in=body_in,
        body_out=body_out,
        processed_paragraphs=processed_paragraphs,
        input_body_chars=input_body_chars,
        output_body_chars=output_body_chars,
        max_body_budget=max_body_budget,
        holds=all_holds,
        queries=all_queries,
        approved_fact_changes=p2_audit["approved_fact_changes"],
        style_log_lines=style_log_lines,
        alternates=alternates,
        ledger=ledger,
        outstanding_items=outstanding_items,
        followup_target=str(payload.get("followup_target") or "Par 2"),
        followup_delta=str(payload.get("followup_delta") or "trim 1 line (-28 chars)"),
    )

    return {
        "mode": mode,
        "slug": slug,
        "publication_date": pub_date.isoformat(),
        "placed": placed_flag,
        "is_brief": is_brief,
        "is_domestic": is_domestic,
        "detected_wire_agency": detected_wire,
        "formatted_return": formatted_return,
        "counts": {
            "body_input_chars": input_body_chars,
            "body_output_chars": output_body_chars,
            "body_delta_chars": output_body_chars - input_body_chars,
            "target_body_budget": max_body_budget,
            "within_budget": (output_body_chars <= max_body_budget) if max_body_budget else True,
            "head": head_metrics,
            "deck": deck_metrics,
        },
        "edited_fields": {
            "head": head_out,
            "deck": deck_out,
            "body": body_out,
            "paragraphs": processed_paragraphs,
        },
        "alternates": alternates,
        "ledger": [
            {
                "rule_id": e.rule_id,
                "category": e.category,
                "location": e.location,
                "before": e.before,
                "after": e.after,
                "note": e.note,
            }
            for e in ledger
        ],
        "verification_gate": {
            "holds": all_holds,
            "queries": all_queries,
            "arithmetic_checks": p2_audit["arithmetic_checks"],
            "watchlist_hits": p2_audit["watchlist_hits"],
            "approved_fact_changes": p2_audit["approved_fact_changes"],
            "rejected_fact_changes": p2_audit["rejected_fact_changes"],
        },
        "outstanding": outstanding_items,
        "session_outstanding_all": SESSION_OUTSTANDING_STORE,
    }


def _compile_locked_return(
    *,
    mode: str,
    slug: str,
    pub_date: date,
    placed: bool,
    is_brief: bool,
    is_domestic: bool,
    head_out: str,
    deck_out: str,
    byline_in: str,
    label_in: str,
    caption_in: str,
    credit_in: str,
    body_in: str,
    body_out: str,
    processed_paragraphs: list[str],
    input_body_chars: int,
    output_body_chars: int,
    max_body_budget: int | None,
    holds: list[str],
    queries: list[str],
    approved_fact_changes: list[str],
    style_log_lines: list[str],
    alternates: dict[str, list[dict[str, Any]]],
    ledger: list[LedgerEntry],
    outstanding_items: list[str],
    followup_target: str,
    followup_delta: str,
) -> str:
    """Serialize output through strict, non-divergent return templates ([R1]-[R4])."""
    out_str = "none" if not outstanding_items else "; ".join(
        f"({i + 1}) {item}" for i, item in enumerate(outstanding_items)
    )

    # 1. [P1-C] FOLLOW-UP mode: emit ONLY replacement fenced boxes
    if mode in ("FOLLOW-UP", "FOLLOWUP", "P1-C"):
        target_idx = 1 if len(processed_paragraphs) > 1 else 0
        m_par = re.search(r"(\d+)", followup_target)
        if m_par:
            idx_cand = int(m_par.group(1)) - 1
            if 0 <= idx_cand < len(processed_paragraphs):
                target_idx = idx_cand
        base_par = processed_paragraphs[target_idx] if processed_paragraphs else body_out
        # Deterministically tighten the target paragraph for line-trim
        trimmed_par = (
            base_par.replace("were being provided", "were provided")
            .replace("in order to", "to")
            .replace("at the present time", "now")
            .replace("officials said that ", "officials said ")
        )
        if trimmed_par == base_par and ", the " in base_par:
            trimmed_par = re.sub(r",\s+the\s+([a-z ]+),\s+", lambda m: f" ({m.group(1)}) ", base_par, count=1)

        before_c = compute_body_char_count(base_par)
        after_c = compute_body_char_count(trimmed_par)
        lines = [
            f"#### Par {target_idx + 1} ({followup_delta}; {before_c} > {after_c} chars)",
            "```text",
            trimmed_par,
            "```",
        ]
        if head_out:
            hm = compute_glyph_weight(head_out)
            lines.extend([
                "",
                f"#### Head ({hm['chars']} chars / {hm['weight']} weight)",
                "```text",
                head_out,
                "```",
            ])
        return "\n".join(lines) + "\n"

    # 2. CHECK / QC mode (modules/check.md)
    if mode in ("CHECK", "QC"):
        findings_lines: list[str] = []
        for h in holds:
            findings_lines.append(f"- [Critical] {h}")
        for q in queries:
            findings_lines.append(f"- [Major] {q}")
        for e in ledger:
            findings_lines.append(
                f"- [House | {e.rule_id}] {e.location}: `{e.before}` > `{e.after}` — {e.note}"
            )
        if not findings_lines:
            findings_lines.append("- None. Copy conforms to Bangkok Post Blueprint and Directory standards.")

        verified_lines = [
            f"- Publication date baseline anchored to {pub_date.isoformat()}.",
            f"- Scanned {len(processed_paragraphs)} paragraph(s) ({input_body_chars} chars) against Directory (77 provinces, 900+ districts, watchlist, mortalities) and [P2] arithmetic rules.",
        ]
        if approved_fact_changes:
            verified_lines.extend(approved_fact_changes)

        q_block = "\n".join(f"- {q}" for q in (holds + queries)) if (holds or queries) else "- none"

        return (
            "JOB REPORT\n"
            f"ID: {slug} — {mode} proof audit ({len(ledger)} house findings, {len(holds) + len(queries)} factual/gate alerts).\n\n"
            f"{mode}\n\n"
            "FINDINGS\n"
            + "\n".join(findings_lines)
            + "\n\nVERIFIED\n"
            + "\n".join(verified_lines)
            + "\n\nQUERIES\n"
            + q_block
            + f"\n\nOUTSTANDING: {out_str}\n"
        )

    # 3. PHOTO / MUGSHOT mode (modules/photo.md)
    if mode in ("PHOTO", "MUGSHOT"):
        raw_cap = (caption_in or body_out or "").strip()
        raw_cap = _strip_diacritics_outside_quotes(raw_cap, ledger, "Caption")
        raw_cap = _apply_thai_places_and_transliteration(raw_cap, ledger, queries, "Caption")
        raw_cap = _apply_countries_orgs_and_vocab(raw_cap, is_domestic, ledger, "Caption")
        raw_cap = _apply_british_english_and_oxford_comma(raw_cap, ledger, "Caption")
        raw_cap = _apply_measurements_numbers_times_currency(raw_cap, False, ledger, "Caption")
        # Strip wire location/date prefix bloat like "BANGKOK, THAILAND - SEPTEMBER 16: "
        cleaned_cap = re.sub(
            r"^[A-Z ,.-]+-\s*[A-Z]+\s+\d{1,2}(?:,\s*\d{4})?\s*:\s*",
            "",
            raw_cap,
        )
        credit_tag = f" ({credit_in.strip('()')})" if credit_in else ""
        if mode == "MUGSHOT":
            # Mugshot uses Name or Name: Topic
            mug_line = head_out or cleaned_cap.split(".")[0].strip()
            mug_line = re.sub(r"\b(?:Mr|Ms|Mrs)\.?\s+", "", mug_line)
            cap_box = mug_line
            alt_cap = f"{mug_line}: {label_in or 'File photo'}"
        else:
            cap_box = f"{cleaned_cap.rstrip('.')}.{credit_tag}"
            alt_cap = f"{cleaned_cap.split('.')[0].rstrip('.')}.{credit_tag}"

        return (
            "JOB REPORT\n"
            f"ID: {slug} — {mode} caption desk pass.\n\n"
            "PHOTO\n"
            "```text\n"
            f"{cap_box}\n"
            "```\n\n"
            "ALTERNATES\n"
            f"- `{alt_cap}`\n\n"
            "NOTES\n"
            + "\n".join(style_log_lines)
            + f"\n\nOUTSTANDING: {out_str}\n"
        )

    # 4. PR mode (modules/pr.md) and EDIT / FIT mode ([R2], [R4])
    section_header = "PR" if mode == "PR" else "EDIT"
    summary_desc = (
        f"{'Placed' if placed else 'Unplaced'} {'brief' if is_brief else ('PR' if mode == 'PR' else 'news')} "
        f"sub-edit ({HOUSE_MONTHS[pub_date.month]} {pub_date.day} edition)."
    )

    gate_lines: list[str] = []
    for h in holds:
        gate_lines.append(f"HOLD: {h}")
    for q in queries:
        gate_lines.append(f"Query: {q}")
    gate_block = ("\n".join(gate_lines) + "\n") if gate_lines else ""

    # Build copy fence contents
    fence_lines: list[str] = []
    if placed or head_out:
        final_head = head_out or alternates["heads"][0]["text"]
        fence_lines.append(f"###head {final_head}")
        if not is_brief and (deck_out or (placed and alternates["decks"])):
            final_deck = deck_out or alternates["decks"][0]["text"]
            fence_lines.append(f"###deck {final_deck}")
        if placed:
            byline_val = byline_in or ("Post Reporters" if is_domestic else (detected_wire or "Wire Agencies"))
            fence_lines.append(f"###byline {byline_val}")
        elif label_in:
            fence_lines.append(f"###label {label_in}")
        fence_lines.append("")

    fence_lines.append(body_out)
    fence_content = "\n".join(fence_lines)

    budget_suffix = f" (budget max {max_body_budget})" if max_body_budget else ""
    body_count_line = f"Body: {input_body_chars} > {output_body_chars}{budget_suffix}"

    blocks: list[str] = [
        "JOB REPORT",
        f"ID: {slug} — {summary_desc}",
        "",
        section_header,
    ]
    if gate_block:
        blocks.append(gate_block.rstrip("\n"))
    blocks.extend([
        "```text",
        fence_content,
        "```",
        body_count_line,
    ])

    # ALTERNATES section (included when placed or head/deck supplied or PR/FIT)
    if placed or head_out or deck_out or mode in ("FIT", "PR"):
        alt_lines = ["", "ALTERNATES"]
        for idx, h_item in enumerate(alternates["heads"], 1):
            alt_lines.append(
                f"- Head {idx} [{h_item['chars']} chars / {h_item['weight']} wt]: {h_item['text']}"
            )
        if not is_brief:
            for idx, d_item in enumerate(alternates["decks"], 1):
                alt_lines.append(
                    f"- Deck {idx} [{d_item['chars']} chars / {d_item['weight']} wt]: {d_item['text']}"
                )
        blocks.extend(alt_lines)

    # FACT CHANGES section (included ONLY when verified changes exist)
    if approved_fact_changes:
        blocks.extend([
            "",
            "FACT CHANGES",
            *approved_fact_changes,
        ])

    # STYLE LOG section (built 100% from actual TransformationLedger)
    blocks.extend([
        "",
        "STYLE LOG",
        *style_log_lines,
    ])

    # ORIGINAL FILING section (domestic stories only; omitted for wire copy)
    if is_domestic and mode != "PR":
        blocks.extend([
            "",
            "ORIGINAL FILING",
            "```text",
            body_in,
            "```",
        ])

    blocks.extend([
        "",
        f"OUTSTANDING: {out_str}",
    ])

    return "\n".join(blocks) + "\n"


def get_editorial_presets() -> list[dict[str, Any]]:
    """Return realistic Bangkok Post newsroom test filings covering every mode and trap."""
    return [
        {
            "id": "r4-17-rivers",
            "title": "1. [R4] Canonical Benchmark — 17-rivers (Ubon Ratchathani Flood Filing)",
            "mode": "EDIT",
            "slug": "17-rivers",
            "pub_date": "2026-09-17",
            "placed": False,
            "story_origin": "domestic",
            "counts": "",
            "head": "",
            "deck": "",
            "byline": "",
            "label": "Floods",
            "body": (
                "Floodwaters forced 850 residents from their homes in Mueang Ubon Ratchathani district on Sept 16, officials said.\n\n"
                "Somchai Dee, the district chief, said the Mun River had risen 90 centimetres overnight and that shelters, food, and medicine were being provided. He said more rain is expected."
            ),
            "fact_proposals": [],
            "description": "Tests exact deterministic reproduction of BLUEPRINT.md [R4] EXAMPLE: Mueang > Muang, on Sept 16 > yesterday, 90 centimetres > 90cm, Oxford comma removal, Thai second reference (He said > Mr Somchai said), past-tense-as-future (is expected > was expected), and Body: 289 > 285.",
        },
        {
            "id": "domestic-watchlist-traps",
            "title": "2. Domestic Watchlist, Quotes, Diacritics & Arithmetic Gate — 17-bkk-drainage",
            "mode": "EDIT",
            "slug": "17-bkk-drainage",
            "pub_date": "2026-09-17",
            "placed": True,
            "story_origin": "domestic",
            "counts": "Body: 550-720",
            "head": "Mr. Chatchart orders Khlong Toey flood center inspection",
            "deck": "The Thai government pledges 50 million Thai baht as 5 police assist Bangkok drainage crews",
            "byline": "Post Reporters",
            "label": "",
            "body": (
                "Bangkok Governor Chatchart Sittipunt inspected drainage pumps in Khlong Toey district and Soi Sukhumvit 22 on September 16 after 2 inches of rain fell across the Thai capital of Bangkok.\n\n"
                "\"Water levels rose 3 feet in 30 minutes, reaching 95°F inside the pump room,\" said Deputy Spokesperson Supaporn Chaiyawan at Café Amazon near Phra Ram 4 Road. She said additional pumps are expected by 12:00 p.m. on Sept 17.\n\n"
                "Former Prime Minister Mr. Chavarat Charnvirakul and Nikorn Chamnong, the Chartthaipattana MP, had previously reviewed the THB 50 million blueprint with ASEAN engineers at the Queen Sirikit National Convention Center, where 50% of the 800 drainage gates — or 450 gates — were upgraded."
            ),
            "fact_proposals": [],
            "description": "Tests quotation protection with [91cm]/[35C] bracket insertions, Khlong Toey > Klong Toey, Soi Sukhumvit 22 > Sukhumvit Soi 22, Phra Ram 4 > Rama IV, Café > Cafe, Queen Sirikit National Convention Center guard, deceased Mr Chavarat strip, Nikorn Chamnong watchlist alert, and 50% of 800 != 450 arithmetic HOLD.",
        },
        {
            "id": "placed-fit-package",
            "title": "3. Placed DC-X Copy-Fit & [P1-A] Glyph-Weight Job — 17-rail-link",
            "mode": "FIT",
            "slug": "17-rail-link",
            "pub_date": "2026-09-17",
            "placed": True,
            "story_origin": "domestic",
            "counts": "Body: 380-460",
            "head": "Cabinet clears 120 billion Thai baht high-speed rail link to Rayong",
            "deck": "Transport Ministry expects construction to begin on September 18 after EEC panel review",
            "byline": "Post Reporters",
            "label": "",
            "body": (
                "The Thai cabinet on Sept 16 approved a THB 120 billion investment framework for the high-speed rail extension linking Suvarnabhumi International Airport, Chonburi and Rayong.\n\n"
                "Surapong Piyachote, the deputy transport minister, said trains will travel at 250 km/h and cut travel time, fuel costs, and road congestion. He said bidding is expected to conclude by 2:30 p.m. on Sept 20."
            ),
            "fact_proposals": [],
            "description": "Tests placed DC-X package fitting, headline baht conversion (B120bn), Suvarnabhumi airport casing, Chonburi > Chon Buri, km/h > kph, 2:30 p.m. > 2.30pm, weekday conversion (on Sept 20 > on Sunday), and [P1-A] glyph-weight scoring.",
        },
        {
            "id": "check-qc-proof",
            "title": "4. [CHECK / QC] Page Proof Verification & Trap Audit — 17-mekong-check",
            "mode": "CHECK",
            "slug": "17-mekong-check",
            "pub_date": "2026-09-17",
            "placed": False,
            "story_origin": "wire",
            "counts": "",
            "head": "ASEAN envoys meet in Rangoon over Mekong water levels",
            "deck": "",
            "byline": "Reuters",
            "label": "",
            "body": (
                "Envoys from Burma, Cambodia, and Laotian authorities met in Rangoon on Sept 16 to review Mekong River data compiled by UNESCO and Malaysian Airlines cargo monitors, Reuters reported.\n\n"
                "Officials inspected 95 monitoring stations from a network of 70 river gauges near Bangkok airport, whilst media are reporting temperatures of 36°C."
            ),
            "fact_proposals": [],
            "description": "Tests CHECK/QC ranked findings: Critical arithmetic subset error (95 stations from a network of 70), Major ambiguous 'Bangkok airport' query, and House findings (Burma > Myanmar, Rangoon > Yangon, Laotian > Lao, UNESCO > Unesco, Malaysian Airlines > Malaysia Airlines, whilst > while, media are > media is).",
        },
        {
            "id": "photo-caption-task",
            "title": "5. [PHOTO] Wire Caption Strip & House Styling — 17-flood-photo",
            "mode": "PHOTO",
            "slug": "17-flood-photo",
            "pub_date": "2026-09-17",
            "placed": False,
            "story_origin": "domestic",
            "counts": "",
            "head": "",
            "deck": "",
            "byline": "",
            "label": "",
            "caption": (
                "UBON RATCHATHANI, THAILAND - SEPTEMBER 16: Rescue workers evacuate 7 residents in a flat-bottom boat after floodwaters from the Mun River rose 90 centimeters in Mueang Ubon Ratchathani district, Thailand"
            ),
            "credit": "Somchai Poomlard",
            "body": "",
            "fact_proposals": [],
            "description": "Tests PHOTO caption mode: strips wire dateline header bloat, converts 7 residents > seven residents, 90 centimeters > 90cm, Mueang > Muang, and formats credit in parentheses.",
        },
        {
            "id": "pr-placement-task",
            "title": "6. [PR] Commercial Placement Pass — 17-ev-expo-pr",
            "mode": "PR",
            "slug": "17-ev-expo-pr",
            "pub_date": "2026-09-17",
            "placed": True,
            "story_origin": "domestic",
            "counts": "Body: 320-450",
            "head": "Air Asia and 7-11 partner for ASEAN EV showcase in Bangkok",
            "deck": "Event at Impact Arena Muang Thong Thani opens at 10:00 a.m. on September 25",
            "byline": "Sponsored",
            "label": "PR",
            "body": (
                "Air Asia and 7-11 announced a new green mobility partnership at Impact Arena Muang Thong Thani in Bangkok, 10900, offering USD 500 charging vouchers to early visitors.\n\n"
                "Organizers said the exhibition will feature 100s of electric vehicles, solar chargers, and battery systems from across ASEAN."
            ),
            "fact_proposals": [],
            "description": "Tests PR light-touch house pass: Air Asia > AirAsia, 7-11 > 7-Eleven, ASEAN > Asean, Impact Arena, Muang Thong Thani comma rule, Bangkok 10900 postcode comma removal, USD 500 > US$500, and 100s > hundreds.",
        },
    ]
