"""
MCDS PII Redaction Web UI
=========================
Flask app that lets users upload a file (PDF/TXT),
runs the spaCy NER + heuristic redaction pipeline,
and returns the redacted file + PII mapping.

Azure integration:
- Fetches blob connection string from Azure Key Vault at startup
- Uploads redacted output + PII mapping to Azure Blob Storage after each job
"""

import os
import sys
import re
import uuid
import json
import time
from collections import OrderedDict
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify, send_file

# Azure SDK
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.keyvault.secrets import SecretClient
from azure.identity import InteractiveBrowserCredential

# Add lambda lib to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lambda"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# Azure — Key Vault + Blob Storage
# ---------------------------------------------------------------------------
KEY_VAULT_URL = "https://mcdskeyvault2005.vault.azure.net/"
SECRET_NAME = "azure-blob-connection-string"
AZURE_CONTAINER = "redacted-output"


def init_azure():
    """Fetch connection string from Key Vault and build a BlobServiceClient."""
    print("[*] Connecting to Azure Key Vault...", flush=True)
    try:
        credential = InteractiveBrowserCredential()
        kv_client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
        secret = kv_client.get_secret(SECRET_NAME)
        conn_str = secret.value
        print(f"[*] Key Vault: retrieved secret ({len(conn_str)} chars)", flush=True)

        bsc = BlobServiceClient.from_connection_string(conn_str)
        # Quick health-check: make sure the container exists
        container = bsc.get_container_client(AZURE_CONTAINER)
        container.get_container_properties()  # throws if container doesn't exist
        print(f"[*] Azure Blob Storage: connected to container '{AZURE_CONTAINER}'", flush=True)
        app.config["AZURE_BLOB_CLIENT"] = bsc
    except Exception as e:
        print(f"[!] Azure init failed: {e}", flush=True)
        print("[!] Redacted files will NOT be uploaded to Azure.", flush=True)
        app.config["AZURE_BLOB_CLIENT"] = None


def upload_to_azure(job_id: str, filename: str, redacted_text: str, mapping_json: str) -> dict:
    """Upload redacted file + mapping to Azure Blob. Returns blob metadata or None."""
    bsc = app.config.get("AZURE_BLOB_CLIENT")
    if bsc is None:
        return None
    try:
        container = bsc.get_container_client(AZURE_CONTAINER)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        folder = f"{ts}_{job_id}"

        # Upload redacted text
        blob_name = f"{folder}/{filename}_redacted.txt"
        blob = container.get_blob_client(blob_name)
        blob.upload_blob(
            redacted_text.encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type="text/plain; charset=utf-8"),
        )

        # Upload PII mapping JSON
        mapping_blob_name = f"{folder}/{filename}_pii_mapping.json"
        blob_map = container.get_blob_client(mapping_blob_name)
        blob_map.upload_blob(
            mapping_json.encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
        )

        print(f"[*] Azure upload SUCCESS: {blob_name}", flush=True)
        return {
            "uploaded": True,
            "container": AZURE_CONTAINER,
            "redacted_blob": blob_name,
            "mapping_blob": mapping_blob_name,
            "account": bsc.account_name,
        }
    except Exception as e:
        print(f"[!] Azure upload failed: {e}", flush=True)
        return {"uploaded": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Common English words (to filter out false-positive name detections)
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
    "performance", "execution", "aiming",
    "summary", "result", "results", "overview", "details",
}

# ---------------------------------------------------------------------------
# Load spaCy model once at startup
# ---------------------------------------------------------------------------
import spacy
print("[*] Loading spaCy en_core_web_lg model (this takes a moment)...")
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    print("[!] en_core_web_lg not found, falling back to en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")
print("[*] Model loaded successfully!")


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------
def extract_text(filepath: str) -> str:
    if filepath.lower().endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        pages = [p.extract_text() for p in reader.pages if p.extract_text()]
        return "\n".join(pages)
    else:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()


def clean_text(text: str) -> str:
    lines = text.split("\n")
    return "\n".join(re.sub(r'  +', ' ', line).strip() for line in lines)


def _overlaps_any(span, tagged):
    s, e = span
    for ts, te in tagged:
        if s < te and e > ts:
            return True
    return False


def heuristic_name_detection(text, already_tagged):
    extra = []

    # Title-Case names (2-4 words)
    for m in re.finditer(r'\b([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,3})\b', text):
        words = m.group().lower().split()
        if all(w in COMMON_WORDS for w in words):
            continue
        span = (m.start(), m.end())
        if _overlaps_any(span, already_tagged):
            continue
        extra.append({"start": m.start(), "end": m.end(), "type": "PERSON", "text": m.group()})

    # ALL-CAPS names (2-4 words)
    for m in re.finditer(r'\b([A-Z]{2,20}(?:\s+[A-Z]{2,20}){1,3})\b', text):
        words = m.group().lower().split()
        if all(w in COMMON_WORDS for w in words):
            continue
        span = (m.start(), m.end())
        if _overlaps_any(span, already_tagged):
            continue
        extra.append({"start": m.start(), "end": m.end(), "type": "PERSON", "text": m.group()})

    # Single capitalized word on its own line
    for m in re.finditer(r'(?:^|\n)\s*([A-Z][a-z]{2,20})\s*(?:\n|$)', text):
        word = m.group(1).lower()
        if word in COMMON_WORDS:
            continue
        span = (m.start(1), m.end(1))
        if _overlaps_any(span, already_tagged):
            continue
        extra.append({"start": m.start(1), "end": m.end(1), "type": "PERSON", "text": m.group(1)})

    # Single capitalized word near existing entity
    for m in re.finditer(r'\b([A-Z][a-z]{2,20})\b', text):
        word = m.group(1).lower()
        if word in COMMON_WORDS:
            continue
        span = (m.start(), m.end())
        if _overlaps_any(span, already_tagged):
            continue
        nearby = False
        for ts, te in already_tagged:
            if abs(m.start() - te) <= 3 or abs(ts - m.end()) <= 3:
                nearby = True
                break
        if not nearby:
            continue
        extra.append({"start": m.start(), "end": m.end(), "type": "PERSON", "text": m.group(1)})
        already_tagged.add(span)

    return extra


def detect_entities(text):
    nlp.max_length = max(len(text) + 1000, nlp.max_length)
    entities = []

    doc = nlp(text)
    for ent in doc.ents:
        entities.append({"start": ent.start_char, "end": ent.end_char, "type": ent.label_, "text": ent.text})

    for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        entities.append({"start": m.start(), "end": m.end(), "type": "EMAIL", "text": m.group()})
    for m in re.finditer(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text):
        entities.append({"start": m.start(), "end": m.end(), "type": "PHONE", "text": m.group()})
    for m in re.finditer(r'\b\d{3}-\d{2}-\d{4}\b', text):
        entities.append({"start": m.start(), "end": m.end(), "type": "SSN", "text": m.group()})
    for m in re.finditer(r'\b(?:\d[ -]*?){13,16}\b', text):
        entities.append({"start": m.start(), "end": m.end(), "type": "CREDIT_CARD", "text": m.group()})

    already_tagged = set((e["start"], e["end"]) for e in entities)
    heuristic = heuristic_name_detection(text, already_tagged)
    entities.extend(heuristic)

    entities.sort(key=lambda e: e["start"])
    return entities


def build_pseudonym_map(entities):
    counters = {}
    mapping = OrderedDict()
    for ent in entities:
        etype = ent["type"]
        raw = ent["text"].strip()
        if not raw:
            continue
        key = f"{etype}::{raw.lower()}"
        if key not in mapping:
            counters[etype] = counters.get(etype, 0) + 1
            mapping[key] = f"{etype}_{counters[etype]}"
    return mapping


def redact_text(text, entities, pseudonym_map):
    entities_sorted = sorted(entities, key=lambda x: (x["start"], -(x["end"] - x["start"])))
    filtered = []
    last_end = -1
    for ent in entities_sorted:
        if ent["start"] >= last_end:
            filtered.append(ent)
            last_end = ent["end"]

    filtered.sort(key=lambda x: x["start"], reverse=True)
    out = text
    for ent in filtered:
        key = f"{ent['type']}::{ent['text'].strip().lower()}"
        pseudo = pseudonym_map.get(key, f"[{ent['type']}]")
        out = out[:ent["start"]] + pseudo + out[ent["end"]:]
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/redact", methods=["POST"])
def api_redact():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".txt", ".pdf", ".csv", ".md", ".log"):
        return jsonify({"error": f"Unsupported file type: {ext}. Use .txt or .pdf"}), 400

    # Save upload
    job_id = uuid.uuid4().hex[:12]
    safe_name = f"{job_id}{ext}"
    upload_path = os.path.join(UPLOAD_FOLDER, safe_name)
    file.save(upload_path)

    try:
        start_time = time.time()

        # Extract and clean
        raw_text = extract_text(upload_path)
        text = clean_text(raw_text)

        # Detect entities
        entities = detect_entities(text)

        # Build pseudonym map
        pseudonym_map = build_pseudonym_map(entities)

        # Redact
        redacted = redact_text(text, entities, pseudonym_map)

        elapsed = round(time.time() - start_time, 2)

        # Save redacted file locally
        redacted_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_redacted.txt")
        with open(redacted_path, "w", encoding="utf-8") as f:
            f.write(redacted)

        # Build mapping table for the UI
        mapping_list = []
        for key, pseudo in pseudonym_map.items():
            etype, raw = key.split("::", 1)
            mapping_list.append({"pseudonym": pseudo, "type": etype, "original": raw})

        # Type stats
        type_counts = {}
        for key in pseudonym_map:
            etype = key.split("::")[0]
            type_counts[etype] = type_counts.get(etype, 0) + 1

        # Upload to Azure Blob Storage
        azure_result = upload_to_azure(
            job_id,
            os.path.splitext(file.filename)[0],
            redacted,
            json.dumps(mapping_list, indent=2),
        )

        return jsonify({
            "success": True,
            "job_id": job_id,
            "original_filename": file.filename,
            "original_text": text[:5000] + ("..." if len(text) > 5000 else ""),
            "redacted_text": redacted[:5000] + ("..." if len(redacted) > 5000 else ""),
            "original_length": len(text),
            "redacted_length": len(redacted),
            "entity_count": len(entities),
            "unique_pii_count": len(pseudonym_map),
            "type_counts": type_counts,
            "mapping": mapping_list,
            "elapsed_seconds": elapsed,
            "azure": azure_result,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Clean up uploaded file
        if os.path.exists(upload_path):
            os.remove(upload_path)


@app.route("/api/download/<job_id>")
def download_redacted(job_id):
    path = os.path.join(UPLOAD_FOLDER, f"{job_id}_redacted.txt")
    if not os.path.exists(path):
        return jsonify({"error": "File not found or expired"}), 404
    return send_file(path, as_attachment=True, download_name="redacted_output.txt")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  MCDS PII Redaction UI")
    print("  Open in your browser: http://localhost:5000")
    print("=" * 60 + "\n")
    init_azure()  # Connect Key Vault -> Blob Storage
    app.run(debug=False, port=5000)
