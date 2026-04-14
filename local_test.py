"""
Local PII Redaction Test Script (v3)
=====================================
Uses spaCy en_core_web_lg for NER + smart heuristics to catch
names that spaCy misses (especially Indian/South-Asian names).

Pseudonymizes every unique PII value:
   "Utkarsh Singh" -> PERSON_1 (every occurrence)
   "joydip@x.com"  -> EMAIL_1

Output saved to <input_filename>_redacted.txt
"""

import os
import sys
import re
import argparse
from collections import OrderedDict

# Fix Windows terminal encoding
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Fix imports for the lambda lib modules
sys.path.append(os.path.join(os.path.dirname(__file__), "lambda"))

# ---------------------------------------------------------------------------
# Common English words (to avoid tagging "The Event" as a person name)
# ---------------------------------------------------------------------------
COMMON_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "he", "she", "they",
    "we", "you", "i", "me", "him", "her", "us", "them", "my", "your",
    "his", "our", "their", "not", "no", "yes", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "than",
    "too", "very", "just", "about", "above", "after", "again", "below",
    "between", "during", "before", "under", "over", "through", "into",
    "out", "up", "down", "off", "then", "once", "here", "there", "when",
    "where", "why", "how", "what", "which", "who", "whom", "if", "so",
    # Common non-name words that appear capitalized in documents
    "date", "event", "title", "report", "page", "section", "table",
    "image", "photo", "figure", "list", "below", "above", "total",
    "name", "college", "university", "institute", "engineering",
    "technology", "department", "track", "theme", "team", "project",
    "prize", "pool", "winner", "winners", "judges", "sponsor",
    "ceremony", "opening", "closing", "round", "phase", "day",
    "online", "offline", "hybrid", "national", "international",
    "hackathon", "hacks", "community", "club", "chapter",
    "statement", "financial", "budget", "expenditure", "revenue",
    "signature", "convener", "conveners", "coordinator", "head",
    "future", "outlook", "success", "participation", "impact",
    "innovation", "collaboration", "learning", "problem", "solving",
    "coding", "solutions", "networking", "communication", "about",
    "photos", "participants", "participating", "colleges",
    "hall", "mini", "venue", "location", "time", "duration",
    "type", "mode", "conduction", "organised", "organized",
    "evaluated", "evaluating", "distribution", "during", "actively",
    "track", "tracks", "open", "based", "projects", "industry",
    "experts", "served", "offered", "encouraged", "bridged",
    "academic", "expectations", "real", "world", "practical",
    "mentorship", "internship", "opportunities", "exposure",
    "total", "external", "sponsoring", "agency", "nil",
    "inaugural", "special", "honourable", "mention", "outstanding",
    "performance", "innovation", "execution", "impact", "aiming",
    "summary", "result", "results", "overview", "details",
}

# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------
def extract_text(filepath: str) -> str:
    if filepath.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            pages = [page.extract_text() for page in reader.pages if page.extract_text()]
            return "\n".join(pages)
        except ImportError:
            print("Error: 'pypdf' is required for PDF files. pip install pypdf")
            sys.exit(1)
    else:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()


# ---------------------------------------------------------------------------
# Pre-clean text (normalize PDF extraction artifacts)
# ---------------------------------------------------------------------------
def clean_text(text: str) -> str:
    """Normalize multi-spaces from PDF extraction while preserving newlines."""
    # Replace multiple spaces with single space (per line)
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        cleaned.append(re.sub(r'  +', ' ', line).strip())
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Heuristic name detector (catches names spaCy misses)
# ---------------------------------------------------------------------------
def heuristic_name_detection(text: str, already_tagged: set[tuple[int, int]]) -> list[dict]:
    """
    Detect person names that spaCy missed using pattern matching.
    Catches:
      - Title-case sequences: "Utkarsh Singh", "Joydip Deb"
      - ALL-CAPS names: "HEMASREE KUDUM", "ZIYA KHAN"
      - Single capitalized words on their own line (participant lists)
    """
    extra_entities = []

    # --- Pattern 1: Title-Case names (2-4 words) ---
    # e.g., "Atharv Singh Baghel", "Ann Mary Jo"
    for m in re.finditer(r'\b([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,3})\b', text):
        words = m.group().lower().split()
        # Skip if ALL words are common English words
        if all(w in COMMON_WORDS for w in words):
            continue
        # Skip if already tagged by spaCy
        span = (m.start(), m.end())
        if _overlaps_any(span, already_tagged):
            continue
        extra_entities.append({
            "start": m.start(), "end": m.end(),
            "type": "PERSON", "text": m.group()
        })

    # --- Pattern 2: ALL-CAPS names (2-4 words, at least 2 chars each) ---
    # e.g., "HEMASREE KUDUM", "SHASHANK SINGH"
    for m in re.finditer(r'\b([A-Z]{2,20}(?:\s+[A-Z]{2,20}){1,3})\b', text):
        words = m.group().lower().split()
        if all(w in COMMON_WORDS for w in words):
            continue
        span = (m.start(), m.end())
        if _overlaps_any(span, already_tagged):
            continue
        extra_entities.append({
            "start": m.start(), "end": m.end(),
            "type": "PERSON", "text": m.group()
        })

    # --- Pattern 3: Single capitalized word on its own line (participant lists) ---
    # Lines like "Sanjay\n", "Rupali\n", "Mithra\n", "Shreyansh\n", "Vishal\n"
    for m in re.finditer(r'(?:^|\n)\s*([A-Z][a-z]{2,20})\s*(?:\n|$)', text):
        word = m.group(1).lower()
        if word in COMMON_WORDS:
            continue
        name_start = m.start(1)
        name_end = m.end(1)
        span = (name_start, name_end)
        if _overlaps_any(span, already_tagged):
            continue
        extra_entities.append({
            "start": name_start, "end": name_end,
            "type": "PERSON", "text": m.group(1)
        })

    # --- Pattern 4: Single capitalized word NOT on own line (catches stragglers) ---
    # e.g., "Garvit Singh Rathore" where spaCy only got "Singh Rathore"
    for m in re.finditer(r'\b([A-Z][a-z]{2,20})\b', text):
        word = m.group(1).lower()
        if word in COMMON_WORDS:
            continue
        span = (m.start(), m.end())
        if _overlaps_any(span, already_tagged):
            continue
        # Only tag if nearby (within 3 chars) there's already a PERSON entity
        nearby_person = False
        for ts, te in already_tagged:
            if abs(m.start() - te) <= 3 or abs(ts - m.end()) <= 3:
                nearby_person = True
                break
        if not nearby_person:
            continue
        extra_entities.append({
            "start": m.start(), "end": m.end(),
            "type": "PERSON", "text": m.group(1)
        })
        already_tagged.add(span)

    return extra_entities


def _overlaps_any(span: tuple[int, int], tagged: set[tuple[int, int]]) -> bool:
    """Check if span overlaps with any already-tagged span."""
    s, e = span
    for ts, te in tagged:
        if s < te and e > ts:
            return True
    return False


# ---------------------------------------------------------------------------
# Entity detection (spaCy NER + regex + heuristics)
# ---------------------------------------------------------------------------
def detect_entities(text: str) -> list[dict]:
    import spacy

    # Use the LARGE model for much better accuracy
    try:
        nlp = spacy.load("en_core_web_lg")
    except OSError:
        print("Warning: en_core_web_lg not found, falling back to en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")

    nlp.max_length = max(len(text) + 1000, nlp.max_length)

    entities: list[dict] = []

    # --- Pass 1: spaCy NER ---
    doc = nlp(text)
    for ent in doc.ents:
        entities.append({
            "start": ent.start_char,
            "end":   ent.end_char,
            "type":  ent.label_,
            "text":  ent.text,
        })

    # --- Pass 2: Regex for EMAIL, PHONE, SSN, CREDIT_CARD ---
    for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        entities.append({"start": m.start(), "end": m.end(), "type": "EMAIL", "text": m.group()})

    for m in re.finditer(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text):
        entities.append({"start": m.start(), "end": m.end(), "type": "PHONE", "text": m.group()})

    for m in re.finditer(r'\b\d{3}-\d{2}-\d{4}\b', text):
        entities.append({"start": m.start(), "end": m.end(), "type": "SSN", "text": m.group()})

    for m in re.finditer(r'\b(?:\d[ -]*?){13,16}\b', text):
        entities.append({"start": m.start(), "end": m.end(), "type": "CREDIT_CARD", "text": m.group()})

    # --- Pass 3: Heuristic name detection (catches what spaCy misses) ---
    already_tagged = set()
    for e in entities:
        already_tagged.add((e["start"], e["end"]))

    heuristic_names = heuristic_name_detection(text, already_tagged)
    entities.extend(heuristic_names)

    # Sort by start position
    entities.sort(key=lambda e: e["start"])
    return entities


# ---------------------------------------------------------------------------
# Pseudonymization
# ---------------------------------------------------------------------------
def build_pseudonym_map(entities: list[dict]) -> dict[str, str]:
    counters: dict[str, int] = {}
    mapping: OrderedDict[str, str] = OrderedDict()

    for ent in entities:
        etype = ent["type"]
        raw   = ent["text"].strip()
        if not raw:
            continue
        key = f"{etype}::{raw.lower()}"
        if key not in mapping:
            counters[etype] = counters.get(etype, 0) + 1
            mapping[key] = f"{etype}_{counters[etype]}"

    return mapping


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------
def redact_text(text: str, entities: list[dict], pseudonym_map: dict[str, str]) -> str:
    # De-duplicate overlapping spans (keep longer span)
    entities_sorted = sorted(entities, key=lambda x: (x["start"], -(x["end"] - x["start"])))
    filtered: list[dict] = []
    last_end = -1

    for ent in entities_sorted:
        if ent["start"] >= last_end:
            filtered.append(ent)
            last_end = ent["end"]

    # Replace from end to start
    filtered.sort(key=lambda x: x["start"], reverse=True)

    out = text
    for ent in filtered:
        key = f"{ent['type']}::{ent['text'].strip().lower()}"
        pseudo = pseudonym_map.get(key, f"[{ent['type']}]")
        out = out[:ent["start"]] + pseudo + out[ent["end"]:]

    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Local PII redaction test (spaCy + heuristics + pseudonymization)")
    parser.add_argument("file", help="Path to .txt or .pdf file to redact")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        sys.exit(1)

    # 1. Extract and clean text
    print("[1/5] Extracting text...")
    raw_text = extract_text(args.file)
    text = clean_text(raw_text)
    print(f"      Extracted {len(text)} characters.\n")

    # 2. Detect entities
    print("[2/5] Running NER (spaCy en_core_web_lg + regex + heuristics)...")
    entities = detect_entities(text)
    print(f"      Found {len(entities)} entity spans.\n")

    # 3. Build pseudonym map
    print("[3/5] Building pseudonym map...")
    pseudonym_map = build_pseudonym_map(entities)

    # Count by type
    type_counts: dict[str, int] = {}
    for key in pseudonym_map:
        etype = key.split("::")[0]
        type_counts[etype] = type_counts.get(etype, 0) + 1

    print(f"      {len(pseudonym_map)} unique PII values detected:\n")
    print(f"      Summary by type:")
    for t, c in sorted(type_counts.items()):
        print(f"        {t}: {c}")
    print()

    # Print the full mapping table
    print(f"      {'Pseudonym':<25} {'Type':<15} {'Original Value'}")
    print(f"      {'-'*25} {'-'*15} {'-'*40}")
    for key, pseudo in pseudonym_map.items():
        etype, raw = key.split("::", 1)
        display = raw if len(raw) <= 40 else raw[:37] + "..."
        print(f"      {pseudo:<25} {etype:<15} {display}")
    print()

    # 4. Redact and save
    print("[4/5] Redacting...")
    redacted = redact_text(text, entities, pseudonym_map)

    base, _ = os.path.splitext(args.file)
    output_path = f"{base}_redacted.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(redacted)

    # 5. Also save the mapping as a separate reference file
    mapping_path = f"{base}_pii_mapping.txt"
    with open(mapping_path, "w", encoding="utf-8") as f:
        f.write("PII PSEUDONYM MAPPING\n")
        f.write("=" * 80 + "\n")
        f.write(f"Source: {args.file}\n")
        f.write(f"Total unique PII values: {len(pseudonym_map)}\n")
        f.write(f"Total entity spans redacted: {len(entities)}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"{'Pseudonym':<25} {'Type':<15} {'Original Value'}\n")
        f.write(f"{'-'*25} {'-'*15} {'-'*50}\n")
        for key, pseudo in pseudonym_map.items():
            etype, raw = key.split("::", 1)
            f.write(f"{pseudo:<25} {etype:<15} {raw}\n")

    print(f"\n[SUCCESS] Output files saved:")
    print(f"  Redacted text : {output_path}")
    print(f"  PII mapping   : {mapping_path}")
    print(f"\n  Original length  : {len(text)} chars")
    print(f"  Redacted length  : {len(redacted)} chars")
    print(f"  Entities redacted: {len(entities)}")
    print(f"  Unique PII values: {len(pseudonym_map)}")


if __name__ == "__main__":
    main()
