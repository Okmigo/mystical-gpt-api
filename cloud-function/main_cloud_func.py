# main_cloud_func.py

import os
import io
import sqlite3
import fitz  # PyMuPDF
import tempfile
from datetime import datetime
from sentence_transformers import SentenceTransformer
from google.cloud import storage, secretmanager
from googleapiclient.discovery import build
from google.oauth2 import service_account
from PyPDF2 import PdfReader

MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_PATH = f"/tmp/models/{MODEL_NAME}"
EMBEDDINGS_DB = "/tmp/embeddings.db"
BUCKET_NAME = "your-gcs-bucket-name"
SECRET_NAME = "your-secret-name"
PDF_FOLDER_ID = "your-google-drive-folder-id"


def get_model():
    if not os.path.exists(MODEL_PATH):
        model = SentenceTransformer(MODEL_NAME)
        model.save(MODEL_PATH)
    return SentenceTransformer(MODEL_PATH)


def fetch_secret(secret_name: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.environ["GCP_PROJECT"]
    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(name=secret_path)
    return response.payload.data.decode("UTF-8")


def get_drive_service():
    creds_json = fetch_secret(SECRET_NAME)
    creds = service_account.Credentials.from_service_account_info(eval(creds_json))
    return build("drive", "v3", credentials=creds)


def list_pdfs_in_drive(folder_id: str):
    drive_service = get_drive_service()
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
        fields="files(id, name)"
    ).execute()
    return results.get("files", [])


def download_pdf(file_id: str):
    drive_service = get_drive_service()
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh


def embed_pdfs(force: bool = False):
    print("START: embed_pdfs called with force=", force)
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)

    if not force and bucket.blob("embeddings.db").exists():
        bucket.blob("embeddings.db").download_to_filename(EMBEDDINGS_DB)
        print("EXISTING DB DOWNLOADED")

    model = get_model()

    conn = sqlite3.connect(EMBEDDINGS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            text TEXT,
            embedding BLOB,
            timestamp TEXT
        )
    """)
    conn.commit()

    embedded_ids = set(row[0] for row in cursor.execute("SELECT id FROM documents").fetchall())
    pdfs = list_pdfs_in_drive(PDF_FOLDER_ID)

    for pdf in pdfs:
        if pdf["id"] in embedded_ids:
            continue

        print("PROCESSING:", pdf["name"])
        pdf_stream = download_pdf(pdf["id"])
        reader = PdfReader(pdf_stream)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        if not text.strip():
            print("EMPTY PDF SKIPPED")
            continue

        embedding = model.encode(text)
        cursor.execute("INSERT INTO documents VALUES (?, ?, ?, ?)",
                       (pdf["id"], text, embedding.tobytes(), datetime.utcnow().isoformat()))
        conn.commit()

    conn.close()
    bucket.blob("embeddings.db").upload_from_filename(EMBEDDINGS_DB)
    print("UPLOAD COMPLETE")

    return {"status": "success", "message": "Embeddings updated."}
