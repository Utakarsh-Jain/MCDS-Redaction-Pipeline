from datasets import load_dataset, Dataset, concatenate_datasets

print("Loading cached datasets...")
# Step 1: Load both datasets [cite: 355]
conll = load_dataset("conll2003")
ontonotes = load_dataset("conll2012_ontonotesv5", "english_v12")

# Step 2: Define label mapping dictionaries [cite: 360]
CONLL_ID_TO_UNIFIED = {
    0: "O",
    1: "B-PERSON", 2: "I-PERSON",
    3: "B-ORG", 4: "I-ORG",
    5: "B-LOCATION", 6: "I-LOCATION",
    7: "B-MISC", 8: "I-MISC"
}

ONTO_TO_UNIFIED = {
    "O": "O",
    "B-PERSON": "B-PERSON", "I-PERSON": "I-PERSON",
    "B-ORG": "B-ORG", "I-ORG": "I-ORG",
    "B-GPE": "B-LOCATION", "I-GPE": "I-LOCATION",
    "B-LOC": "B-LOCATION", "I-LOC": "I-LOCATION",
    "B-MONEY": "B-MONEY", "I-MONEY": "I-MONEY",
    "B-DATE": "B-DATE", "I-DATE": "I-DATE",
    "B-CARDINAL": "B-ID", "I-CARDINAL": "I-ID",
    "B-LAW": "B-LAW", "I-LAW": "I-LAW",
}

# Step 3: Write normalisation functions [cite: 399]
def normalize_conll_sample(sample):
    return {
        "tokens": sample["tokens"],
        "labels": [CONLL_ID_TO_UNIFIED[tag] for tag in sample["ner_tags"]]
    }

def normalize_onto_sample(sample):
    label_names = ontonotes["train"].features["sentences"][0]["named_entities"].feature.names
    return {
        "tokens": sample["sentences"][0]["words"],
        "labels": [ONTO_TO_UNIFIED.get(label_names[t], "O") for t in sample["sentences"][0]["named_entities"]]
    }

print("Normalizing and combining datasets. This might take a minute...")

# Step 4: Normalise and concatenate into one unified dataset [cite: 415]
conll_normalized = [normalize_conll_sample(s) for s in conll["train"]]
onto_normalized = [normalize_onto_sample(s) for s in ontonotes["train"]]

conll_ds = Dataset.from_list(conll_normalized)
onto_ds = Dataset.from_list(onto_normalized)

combined = concatenate_datasets([conll_ds, onto_ds])

print(f"Success! Combined dataset now contains {len(combined)} samples in a single unified schema.")