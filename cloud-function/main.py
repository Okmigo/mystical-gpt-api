import os
import sqlite3
import fitz  # PyMuPDF
import tempfile
from flask import jsonify
from sentence_transformers import SentenceTransformer
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google.cloud import storage

FOLDER_ID = "1XtKZcNHAjCf_FNPJMPOwT8QfqbdD9uvW"
BUCKET_NAME = "mystical-gpt-bucket"
MODEL_NAME = "all-MiniLM-L6-v2"
DB_PATH = "/tmp/embeddings.db"

def get_credentials():
    return service_account.Credentials.from_service_account_file("service_account.json")

def get_drive_service():
    return build("drive", "v3", credentials=get_credentials())

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
    return "\\n".join([p.get_text() for p in doc])

def embed_pdfs():
    creds = get_credentials()
    drive = get_drive_service()
    model = SentenceTransformer(MODEL_NAME)

    query = f"'{FOLDER_ID}' in parents and mimeType='application/pdf' and trashed=false"
    files = drive.files().list(q=query, fields="files(id, name)").execute().get("files", [])

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS documents")
    c.execute(\"\"\"\n        CREATE TABLE documents (\n            id TEXT PRIMARY KEY,\n            title TEXT,\n            url TEXT,\n            text TEXT,\n            embedding TEXT\n        )\n    \"\"\")

    for f in files:
        file_id, name = f["id"], f["name"]
        tmp_path = f"/tmp/{file_id}.pdf"
        download_pdf(file_id, tmp_path)
        text = extract_text(tmp_path)
        vec = model.encode(text).tolist()
        vec_str = ",".join(map(str, vec))
        url = f"https://drive.google.com/file/d/{file_id}/view"
        c.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?)", (file_id, name, url, text, vec_str))

    conn.commit()
    conn.close()

def upload_to_bucket():
    client = storage.Client(credentials=get_credentials())
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    blob.upload_from_filename(DB_PATH)

def main(request):
    try:
        embed_pdfs()
        upload_to_bucket()
        return jsonify({"status": "success", "message": "embeddings.db updated in GCS"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
