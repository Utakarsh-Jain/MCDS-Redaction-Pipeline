# MCDS-Redaction-Pipeline

Data engineering scripts for CoNLL and OntoNotes datasets, plus a **production-oriented hybrid AWS–Azure PII redaction API** (Lambda, Cognito, API Gateway, SageMaker, Azure Blob), and a **local Web UI** for testing PII redaction with ML-powered NER.

---

## 🚀 Quick Start - Local Web UI (Demo / Testing)

The fastest way to test the PII redaction pipeline locally **without any AWS/Azure credentials**:

### Prerequisites

```bash
pip install datasets==3.6.0 flask spacy pypdf
python -m spacy download en_core_web_lg
```

### Run the Web UI

```bash
python web/app.py
```

Then open **http://localhost:5000** in your browser. You can:

- **Upload** a `.pdf` or `.txt` file via drag-and-drop
- **View** a side-by-side comparison of original vs. redacted text
- **Download** the fully redacted output file
- **Inspect** the PII mapping table (which pseudonym replaced which real value)

### Run via CLI (no browser needed)

```bash
python local_test.py "path/to/your/file.pdf"
```

This creates two output files next to your input:
- `<filename>_redacted.txt` — The fully redacted document
- `<filename>_pii_mapping.txt` — Reference table of pseudonym → original value

---

## 🔍 How Redaction Works

The pipeline uses a **4-layer entity detection** system:

| Layer | What It Detects | How |
|-------|----------------|-----|
| **spaCy NER** (`en_core_web_lg`) | PERSON, ORG, GPE, DATE, MONEY, etc. | 400MB ML model |
| **Regex Pass** | EMAIL, PHONE, SSN, CREDIT_CARD | Pattern matching |
| **Heuristic Pass 1** | Title-Case & ALL-CAPS multi-word names | Pattern + dictionary filter |
| **Heuristic Pass 2** | Single-word names near other entities | Proximity-based detection |

### Pseudonymization

Each unique PII value gets a **consistent label** across the entire document:

| Original | Pseudonym |
|----------|-----------|
| Utkarsh Singh | `PERSON_1` |
| community@githubsrmist.in | `EMAIL_1` |
| SRM Institute | `ORG_1` |
| 08/04/2026 | `DATE_1` |

The same real value always maps to the same pseudonym — so if "Utkarsh Singh" appears 5 times, all 5 are replaced with `PERSON_1`.

---

## ☁️ Hybrid PII Redaction API (AWS + Azure) — Production

| Path | Purpose |
|------|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | End-to-end flow and diagrams |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Build Lambda zip, Terraform apply, secrets, curl example |
| [docs/SECURITY.md](docs/SECURITY.md) | IAM, secrets, network notes |
| [docs/ASYNC_AND_OBSERVABILITY.md](docs/ASYNC_AND_OBSERVABILITY.md) | SQS, batch, metrics, X-Ray |
| [lambda/](lambda/) | Python handler and modules |
| [terraform/](terraform/) | Cognito, REST API + authorizer, Lambda, Secrets Manager shell |
| [iam/](iam/) | IAM policy template + example Azure secret JSON |

Quick start: run `scripts/build_lambda_zip.ps1` (Windows) or `scripts/build_lambda_zip.sh`, then follow `docs/DEPLOYMENT.md`.

---

## 📊 MCDS Dataset Preparation Scripts

This repository contains the Data Engineering scripts for our Mastering Cloud Data Services project. These scripts will automatically download the CoNLL-2003 and OntoNotes 5.0 datasets and combine them into our unified, AI-ready schema.

### What the Datasets Contain

| Dataset | Samples | Entity Types | Source |
|---------|---------|-------------|--------|
| **CoNLL-2003** | 14,041 | PERSON, ORG, LOC, MISC | Reuters news articles |
| **OntoNotes 5.0** | 10,539 | PERSON, ORG, GPE, LOC, DATE, MONEY, CARDINAL, LAW + 10 more | News, broadcast, web |
| **Combined** | **24,580** | PERSON, ORG, LOCATION, MISC, MONEY, DATE, ID, LAW | Unified schema |

### Prerequisites

```bash
pip install datasets==3.6.0
```

### Execution Order

#### Step 1: Download the Raw Data

```bash
python download_datasets.py
```

*(Note: If you get a Timeout Error during the OntoNotes download, just run the command again. It will pick up where it left off!)*

#### Step 2: Combine and Map the Labels

```bash
python combine_datasets.py
```

When finished, your local machine will have the fully mapped and merged dataset cached and ready for the BERT model training phase!

---

## 📁 Project Structure

```
MCDS-Redaction-Pipeline/
├── web/                        # Local Web UI for testing
│   ├── app.py                  # Flask backend + redaction pipeline
│   ├── templates/index.html    # Frontend UI
│   └── uploads/                # Temporary file storage
├── lambda/                     # AWS Lambda handler (production)
│   ├── redact_handler.py       # API Gateway → Lambda → SageMaker → Azure
│   ├── lib/
│   │   ├── inference.py        # SageMaker endpoint invocation
│   │   ├── redaction.py        # PII span parsing & index-safe redaction
│   │   └── storage.py          # Azure Blob upload
│   └── tests/
│       └── test_redaction.py   # Unit tests
├── terraform/                  # Infrastructure as Code
├── iam/                        # IAM policies
├── docs/                       # Architecture, deployment, security docs
├── scripts/                    # Build scripts
├── local_test.py               # CLI redaction tool
├── download_datasets.py        # Dataset downloader
├── combine_datasets.py         # Dataset combiner + label mapping
└── sample.txt                  # Sample test file
```
