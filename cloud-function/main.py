import os
import json
import subprocess
import hashlib
from google.cloud import storage, secretmanager
from google.oauth2 import service_account
from datetime import datetime

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

def embed_and_upload():
    subprocess.run(["python3", "embed.py"], check=True)

    credentials = get_service_account_credentials()
    client = storage.Client(credentials=credentials)
    bucket = client.bucket("mystical-gpt-bucket")
    blob = bucket.blob("embeddings.db")

    local_md5 = calculate_md5("embeddings.db")
    remote_md5 = None
    if blob.exists():
        blob.reload()
        remote_md5 = blob.md5_hash

    if remote_md5 and remote_md5 == blob._get_md5_hash(local_md5):
        print("[⏭] Skipping upload and rebuild: embeddings.db unchanged")
        return False

    blob.upload_from_filename("embeddings.db")
    print("[✓] Uploaded embeddings.db to GCS")
    return True

def trigger_rebuild():
    subprocess.run([
        "gcloud", "builds", "submit", "--tag", "gcr.io/corded-nature-462101-b4/mystical-gpt-api"
    ], check=True)
    print("[✓] Cloud Build submitted")

    subprocess.run([
        "gcloud", "run", "deploy", "mystical-gpt-api",
        "--image", "gcr.io/corded-nature-462101-b4/mystical-gpt-api",
        "--region", "europe-west1",
        "--platform", "managed",
        "--allow-unauthenticated",
        "--timeout", "600",
        "--memory", "2Gi"
    ], check=True)
    print("[✓] Cloud Run redeployed")

def main(request):
    try:
        updated = embed_and_upload()
        if updated:
            trigger_rebuild()
            return ("Success: embedding + redeploy complete", 200)
        else:
            return ("Skipped: embeddings.db not changed", 200)
    except Exception as e:
        return (f"Error: {str(e)}", 500)
