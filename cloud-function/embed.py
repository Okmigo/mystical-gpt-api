import os
import json
import hashlib
import sqlite3
from google.cloud import storage, secretmanager
from google.oauth2 import service_account

TMP_DB_PATH = "/workspace/embeddings.db"  # ✅ Fixed path for Gen2

def get_service_account_credentials():
    secret_client = secretmanager.SecretManagerServiceClient()
    secret_name = "projects/corded-nature-462101-b4/secrets/my-service-account-key/versions/latest"
    response = secret_client.access_secret_version(request={"name": secret_name})
    payload = response.payload.data.decode("UTF-8")
    service_account_info = json.loads(payload)
    return service_account.Credentials.from_service_account_info(service_account_info)

def calculate_md5(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def generate_embeddings():
    print(f"[⚙️] Creating database at: {TMP_DB_PATH}")
    try:
        with sqlite3.connect(TMP_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS dummy (id INTEGER PRIMARY KEY, content TEXT)")
            cursor.execute("INSERT INTO dummy (content) VALUES (?)", ("Example embedding",))
            conn.commit()
        print("[✓] embeddings.db created")
    except Exception as e:
        print(f"[❌] Failed to write to {TMP_DB_PATH}: {e}")
        raise

def embed_and_upload():
    generate_embeddings()

    if not os.path.exists(TMP_DB_PATH):
        print(f"[❌] File not found after generate_embeddings: {TMP_DB_PATH}")
        raise FileNotFoundError("embeddings.db was not created")

    credentials = get_service_account_credentials()
    client = storage.Client(project="corded-nature-462101-b4", credentials=credentials)
    bucket = client.bucket("mystical-gpt-bucket")
    blob = bucket.blob("embeddings.db")

    local_md5 = calculate_md5(TMP_DB_PATH)

    remote_md5 = None
    if blob.exists():
        blob.reload()
        remote_md5 = blob.md5_hash

    if remote_md5 and remote_md5 == blob._get_md5_hash(local_md5):
        print("[⏭] Skipping upload: embeddings.db unchanged")
        return False

    blob.upload_from_filename(TMP_DB_PATH)
    print("[✓] Uploaded embeddings.db to GCS")
    return True

def main(request):
    try:
        updated = embed_and_upload()
        return ("Success" if updated else "Skipped", 200)
    except Exception as e:
        print(f"[❌] Exception: {e}")
        return (f"Error: {e}", 500)
