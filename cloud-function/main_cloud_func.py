import os
import io
import fitz  # PyMuPDF
import sqlite3
import time
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from google.cloud import storage, secretmanager

TMP_DIR = "/tmp"
BUCKET_NAME = "mystical-gpt-embeddings"
EMBEDDINGS_DB = os.path.join(TMP_DIR, "embeddings.db")
MODEL_PATH = os.path.join(TMP_DIR, "models", "all-MiniLM-L6-v2")


def fetch_secret(secret_id: str, project_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def download_existing_db():
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    if blob.exists():
        blob.download_to_filename(EMBEDDINGS_DB)
        print("EXISTING DB DOWNLOADED")


def upload_to_bucket():
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    blob.upload_from_filename(EMBEDDINGS_DB)
    print("UPLOAD COMPLETE")


def embed_pdfs(force: bool = False) -> bool:
    os.makedirs(os.path.dirname(EMBEDDINGS_DB), exist_ok=True)

    download_existing_db()

    conn = sqlite3.connect(EMBEDDINGS_DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            page INTEGER,
            text TEXT,
            embedding BLOB
        )
    """)
    conn.commit()

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)

    model = SentenceTransformer(MODEL_PATH)
    print("MODEL LOADED")

    processed_files = set(row[0] for row in c.execute("SELECT DISTINCT filename FROM documents"))
    print(f"SKIP LIST: {processed_files}")

    new_data = False
    for blob in bucket.list_blobs(prefix="pdfs/"):
        filename = os.path.basename(blob.name)
        if not filename.endswith(".pdf") or filename in processed_files:
            continue

        print(f"PROCESSING: {filename}")
        data = blob.download_as_bytes()
        pdf = PdfReader(io.BytesIO(data))

        for page_num, page in enumerate(pdf.pages):
            try:
                text = page.extract_text()
                if text:
                    embedding = model.encode(text)
                    c.execute("INSERT INTO documents (filename, page, text, embedding) VALUES (?, ?, ?, ?)",
                              (filename, page_num, text, embedding.tobytes()))
            except Exception as e:
                print(f"ERROR processing page {page_num} of {filename}: {e}")

        new_data = True
        conn.commit()

    conn.close()
    return new_data
