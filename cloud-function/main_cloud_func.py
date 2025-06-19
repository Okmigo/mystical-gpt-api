import os
import json
import sqlite3
import fitz  # PyMuPDF
import tempfile
import numpy as np
from sentence_transformers import SentenceTransformer
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google.cloud import storage
from google.cloud import secretmanager_v1 as secretmanager

FOLDER_ID = "1XtKZcNHAjCf_FNPJMPOwT8QfqbdD9uvW"
BUCKET_NAME = "mystical-gpt-bucket"
MODEL_PATH = "all-MiniLM-L6-v2"
DB_PATH = "/tmp/embeddings.db"
MAX_CHUNKS_PER_FILE = 50  # safety cap

def get_secret():
    print("STEP: Fetching secret from Secret Manager")
    project_id = os.environ["GCP_PROJECT"]
    secret_id = "my-service-account-key"
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    service_account_info = json.loads(response.payload.data.decode("UTF-8"))
    return service_account.Credentials.from_service_account_info(service_account_info)

def get_drive_service():
    return build("drive", "v3", credentials=get_secret())

def download_pdf(file_id, out_path):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    with open(out_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

def extract_text(path):
    doc = fitz.open(path)
    return "\n".join([p.get_text() for p in doc])

def chunk_text(text, max_tokens=500):
    sentences = text.split('. ')
    chunks, current = [], []
    tokens = 0
    for sentence in sentences:
        sentence_tokens = len(sentence.split())
        if tokens + sentence_tokens > max_tokens:
            chunks.append(' '.join(current))
            current, tokens = [], 0
        current.append(sentence)
        tokens += sentence_tokens
    if current:
        chunks.append(' '.join(current))
    return chunks[:MAX_CHUNKS_PER_FILE]

def embed_pdfs(force=False):
    print("START: embed_pdfs called with force=", force)
    creds = get_secret()
    drive = get_drive_service()
    model_dir = download_model_from_gcs()
    model = SentenceTransformer(model_dir)

    query = f"'{FOLDER_ID}' in parents and mimeType='application/pdf' and trashed=false"
    files = drive.files().list(q=query, fields="files(id, name)").execute().get("files", [])

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            text TEXT,
            embedding TEXT
        )
    """)

    c.execute("SELECT id FROM documents")
    existing_ids = {row[0] for row in c.fetchall()}

    modified = False

    for f in files:
        file_id, name = f["id"], f["name"]
        if file_id in existing_ids:
            print(f"SKIPPED: {name} already embedded")
            continue

        tmp_path = f"/tmp/{file_id}.pdf"
        print(f"PROCESSING: {name}")
        download_pdf(file_id, tmp_path)
        text = extract_text(tmp_path)
        chunks = chunk_text(text)

        if not chunks:
            print(f"SKIPPED: No extractable text in {name}")
            continue

        vecs = [model.encode([chunk])[0] for chunk in chunks]
        avg_vec = np.mean(vecs, axis=0).tolist()
        vec_str = ",".join(map(str, avg_vec))
        url = f"https://drive.google.com/file/d/{file_id}/view"

        c.execute("REPLACE INTO documents VALUES (?, ?, ?, ?, ?)", (file_id, name, url, text, vec_str))
        print(f"EMBEDDED: {name} with {len(chunks)} chunks")
        modified = True

    conn.commit()
    conn.close()
    print("DONE: All eligible documents embedded.")
    return modified

def download_model_from_gcs():
    print("STEP: Loading model from GCS")
    client = storage.Client(credentials=get_secret())
    bucket = client.bucket(BUCKET_NAME)
    temp_dir = tempfile.mkdtemp()
    blobs = list(bucket.list_blobs(prefix=MODEL_PATH))

    for blob in blobs:
        if not blob.name.endswith("/"):
            rel_path = os.path.relpath(blob.name, MODEL_PATH)
            target_path = os.path.join(temp_dir, rel_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            blob.download_to_filename(target_path)
            print(f"DOWNLOADED: {blob.name}")

    return temp_dir

def upload_to_bucket():
    print("STEP: Uploading embeddings.db to GCS")
    client = storage.Client(credentials=get_secret())
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    blob.upload_from_filename(DB_PATH)
    print("UPLOAD COMPLETE")
