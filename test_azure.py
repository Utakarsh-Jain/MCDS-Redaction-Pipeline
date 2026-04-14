from azure.storage.blob import BlobServiceClient
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# ── Test 1: Blob Storage ──────────────────────────────
print("Testing Azure Blob Storage...")

# Use environment variable for sensitive credentials
import os
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=<account-name>;AccountKey=<account-key>;EndpointSuffix=core.windows.net")

try:
    bsc = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    
    # Upload a test file
    container = bsc.get_container_client("redacted-output")
    test_data = b"Hello from MCDS Redaction Pipeline! Azure is working."
    container.upload_blob("test/hello.txt", test_data, overwrite=True)
    print("[PASS] Blob upload SUCCESS")
    
    # Download it back
    downloaded = container.download_blob("test/hello.txt").readall()
    print(f"[PASS] Blob download SUCCESS: {downloaded.decode()}")
    
    # List blobs
    blobs = list(container.list_blobs())
    print(f"[PASS] Container has {len(blobs)} blob(s)")

except Exception as e:
    print(f"[FAIL] Blob Storage FAILED: {e}")

# ── Test 2: Key Vault ─────────────────────────────────
print("\nTesting Azure Key Vault...")

VAULT_URL = "https://mcdskeyvault2005.vault.azure.net/"

try:
    from azure.identity import InteractiveBrowserCredential
    credential = InteractiveBrowserCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)
    
    secret = client.get_secret("azure-blob-connection-string")
    print(f"[PASS] Key Vault SUCCESS: secret retrieved ({len(secret.value)} chars)")

except Exception as e:
    print(f"[FAIL] Key Vault FAILED: {e}")

print("\nDone!")