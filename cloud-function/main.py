import os
import json
import subprocess
import hashlib
from google.cloud import storage
from google.oauth2 import service_account
from datetime import datetime
import google.auth
from googleapiclient.discovery import build

def calculate_md5(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def embed_and_upload():
    # Generate embeddings.db using local embed.py
    subprocess.run(["python3", "embed.py"], check=True)

    # Compare hash to previous uploaded file
    credentials = service_account.Credentials.from_service_account_file("service_account.json")
    client = storage.Client(credentials=credentials)
    bucket = client.bucket("mystical-gpt-bucket")
    blob = bucket.blob("embeddings.db")

    local_md5 = calculate_md5("embeddings.db")
    remote_md5 = None
    if blob.exists():
        blob.reload()
        remote_md5 = blob.md5_hash  # base64 encoded

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
