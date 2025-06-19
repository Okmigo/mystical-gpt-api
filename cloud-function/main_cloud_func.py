# main_cloud_func.py

import os
import io
import time
import tempfile
import logging
import sqlite3
from typing import List

from google.cloud import storage, secretmanager
from sentence_transformers import SentenceTransformer
from PyPDF2 import PdfReader
import torch

logging.basicConfig(level=logging.INFO)

BUCKET_NAME = "mystical-gpt-bucket"
MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_PATH = f"models/{MODEL_NAME}"
DB_PATH = "/tmp/embeddings.db"
CHUNK_SIZE = 1000
BATCH_SIZE = 8


def fetch_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{os.environ['GCP_PROJECT']}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode("UTF-8")


def download_model():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    for blob in bucket.list_blobs(prefix=MODEL_PATH):
        dest_path = os.path.join("/tmp", blob.name)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        blob.download_to_filename(dest_path)
        logging.info(f"DOWNLOADED: {blob.name}")
    return SentenceTransformer(os.path.join("/tmp", MODEL_PATH))


def download_embeddings_db():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    if blob.exists():
        blob.download_to_filename(DB_PATH)
        logging.info("EXISTING DB DOWNLOADED")
    else:
        logging.info("NO EXISTING DB FOUND — WILL CREATE NEW")


def upload_embeddings_db():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    blob.upload_from_filename(DB_PATH)
    logging.info("UPLOAD COMPLETE")


def fetch_pdfs() -> List[tuple[str, bytes]]:
    from googleapiclient.discovery import build
    from google.oauth2 import service_account

    creds_dict = eval(fetch_secret("gdrive-service-key"))
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    service = build("drive", "v3", credentials=creds)
    
    folder_id = fetch_secret("gdrive-folder-id")
    query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed = false"
    response = service.files().list(q=query, fields="files(id, name)").execute()

    files = []
    for file in response.get("files", []):
        file_id, name = file["id"], file["name"]
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        files.append((name, fh.getvalue()))
    return files


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]


def embed_pdfs(force: bool = False) -> dict:
    logging.info("START: embed_pdfs called with force= %s", force)
    download_embeddings_db()
    model = download_model()

    files = fetch_pdfs()
    embedded_doc_ids = set()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT, content TEXT, embedding BLOB)")

    if not force:
        cur.execute("SELECT DISTINCT id FROM documents")
        embedded_doc_ids = {row[0] for row in cur.fetchall()}

    new_files = [(name, data) for name, data in files if name not in embedded_doc_ids]
    logging.info(f"FILES TO EMBED: {len(new_files)}")

    if not new_files:
        conn.close()
        return {"modified": False, "new_docs": 0}

    for name, data in new_files:
        logging.info(f"PROCESSING: {name}")
        reader = PdfReader(io.BytesIO(data))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        chunks = chunk_text(full_text)

        all_vectors = []
        with torch.no_grad():
            for i in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[i:i + BATCH_SIZE]
                vecs = model.encode(batch)
                all_vectors.extend(vecs.tolist())

        doc_vec = torch.tensor(all_vectors).mean(dim=0).tolist()
        cur.execute("INSERT INTO documents VALUES (?, ?, ?)", (name, full_text, sqlite3.Binary(pickle.dumps(doc_vec))))

        # Save intermediate .tmp backup
        with open("/tmp/embeddings.partial.db", "wb") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n".encode("utf-8"))

    conn.commit()
    conn.close()

    upload_embeddings_db()
    return {"modified": True, "new_docs": len(new_files)}
