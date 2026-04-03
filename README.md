# MCDS-Redaction-Pipeline
Data engineering scripts for CoNLL and OntoNotes datasets.

# MCDS Dataset Preparation Scripts

This repository contains the Data Engineering scripts for our Mastering Cloud Data Services project. These scripts will automatically download the CoNLL-2003 and OntoNotes 5.0 datasets and combine them into our unified, AI-ready schema.

## Prerequisites
Before running these scripts, ensure you have the correct, slightly older version of the datasets library installed to bypass the legacy code block. Open your **Command Prompt (cmd)** and run:
`pip install datasets==3.6.0`

## Execution Order
Please run the scripts in your Command Prompt strictly in the following order:

### Step 1: Download the Raw Data
Navigate to the folder where you saved these scripts in your Command Prompt and run:
`python download_datasets.py`
*(Note: If you get a Timeout Error during the OntoNotes download, just run the command again. It will pick up where it left off!)*

### Step 2: Combine and Map the Labels
Once Step 1 says "Success!", run the combination script to unify the schemas:
`python combine_datasets.py`

When finished, your local machine will have the fully mapped and merged dataset cached and ready for the BERT model training phase!
