import os
import json
import subprocess
from google.cloud import storage
from google.oauth2 import service_account
from datetime import datetime
import google.auth
from googleapiclient.discovery import build

def embed_and_upload():
    # Generate embeddings.db using local embed.py
    subprocess.run(["python3", "embed.py"], check=True)

    # Upload to GCS
    credentials = service_account.Credentials.from_service_account_file("service_account.json")
    client = storage.Client(credentials=credentials)
    bucket = client.bucket("mystical-gpt-bucket")
    blob = bucket.blob("embeddings.db")
    blob.upload_from_filename("embeddings.db")
    print("[✓] Uploaded embeddings.db to GCS")

def trigger_rebuild():
    # Use gcloud CLI to build + deploy
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
        embed_and_upload()
        trigger_rebuild()
        return ("Success: embedding + redeploy complete", 200)
    except Exception as e:
        return (f"Error: {str(e)}", 500)
