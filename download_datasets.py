from datasets import load_dataset

print("Downloading CONLL-2003...")
# Added trust_remote_code=True to bypass the security block
conll = load_dataset("conll2003", trust_remote_code=True) 

print("Downloading OntoNotes 5.0...")
# Added trust_remote_code=True to bypass the security block
ontonotes = load_dataset("conll2012_ontonotesv5", "english_v12", trust_remote_code=True)

print("Success! Datasets downloaded and cached.")