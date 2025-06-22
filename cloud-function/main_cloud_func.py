import os
import io
import fitz  # PyMuPDF
import sqlite3
import tempfile
import time
import json
import gc
import logging
from typing import Generator
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from google.cloud import storage
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
import google.auth
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BUCKET_NAME = "mystical-gpt-bucket"
MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_LOCAL_DIR = os.path.join(tempfile.gettempdir(), MODEL_NAME)
DB_PATH = os.path.join(tempfile.gettempdir(), "embeddings.db")
PDF_DIR = os.path.join(tempfile.gettempdir(), "pdfs")
DRIVE_FOLDER_ID = "1XtKZcNHAjCf_FNPJMPOwT8QfqbdD9uvW"

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(MODEL_LOCAL_DIR, exist_ok=True)

SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
else:
    credentials, _ = google.auth.default()

def download_model_from_gcs():
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=MODEL_NAME + "/")
    for blob in blobs:
        rel_path = os.path.relpath(blob.name, MODEL_NAME)
        local_path = os.path.join(MODEL_LOCAL_DIR, rel_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob.download_to_filename(local_path)
        logger.info("MODEL FILE DOWNLOADED: %s", blob.name)

    config_path = os.path.join(MODEL_LOCAL_DIR, "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError("config.json missing from model directory")
    with open(config_path) as f:
        cfg = json.load(f)
        if not isinstance(cfg, dict) or "model_type" not in cfg:
            raise ValueError("Invalid config.json: missing 'model_type'")

logger.info("DOWNLOADING MODEL FROM GCS")
download_model_from_gcs()
model = SentenceTransformer(MODEL_LOCAL_DIR)

def download_existing_db():
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    if blob.exists():
        blob.download_to_filename(DB_PATH)
        logger.info("EXISTING DB DOWNLOADED")

def save_record_to_db(filename: str, text: str, embedding: np.ndarray):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            text TEXT,
            embedding BLOB
        )''')
        c.execute("INSERT INTO documents (filename, text, embedding) VALUES (?, ?, ?)",
                  (filename, text, sqlite3.Binary(embedding.astype(np.float32).tobytes())))
        conn.commit()

def extract_text_from_pdf(pdf_path: str) -> list[str]:
    reader = PdfReader(pdf_path)
    return [page.extract_text() for page in reader.pages if page.extract_text()]

def split_text(text: str, max_length: int = 300) -> Generator[str, None, None]:
    for i in range(0, len(text), max_length):
        yield text[i:i + max_length]

def download_pdfs_from_drive():
    service = build("drive", "v3", credentials=credentials)
    query = f"'{DRIVE_FOLDER_ID}' in parents and mimeType='application/pdf' and trashed=false"
    response = service.files().list(q=query, fields="files(id, name)").execute()
    files = response.get("files", [])

    for file in files:
        request = service.files().get_media(fileId=file["id"])
        local_path = os.path.join(PDF_DIR, file["name"])
        fh = io.FileIO(local_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            try:
                _, done = downloader.next_chunk()
            except Exception as e:
                logger.warning("DOWNLOAD FAILED FOR %s: %s", file['name'], str(e))
                break
        logger.info("DOWNLOADED FROM DRIVE: %s", file['name'])

def embed_pdfs(force: bool = False) -> bool:
    try:
        download_existing_db()
        download_pdfs_from_drive()

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                text TEXT,
                embedding BLOB
            )""")
            c.execute("SELECT filename FROM documents")
            existing_files = {row[0] for row in c.fetchall()}

        embedded_any = False
        for filename in os.listdir(PDF_DIR):
            if not filename.endswith(".pdf"):
                continue
            if not force and filename in existing_files:
                continue

            local_path = os.path.join(PDF_DIR, filename)
            logger.info("PROCESSING: %s", filename)
            try:
                text_chunks = extract_text_from_pdf(local_path)
                if not text_chunks:
                    continue

                for chunk in text_chunks:
                    for piece in split_text(chunk):
                        emb = model.encode(piece, convert_to_numpy=True).astype(np.float32)
                        save_record_to_db(filename, piece, emb)
                        del emb
                        gc.collect()

                embedded_any = True
            except Exception as e:
                logger.warning("ERROR processing %s: %s", filename, str(e))

        if embedded_any:
            upload_to_bucket()
        return embedded_any

    except Exception as global_err:
        logger.error("EMBEDDING FAILED: %s", str(global_err))
        return False

def upload_to_bucket():
    client = storage.Client(credentials=credentials)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    blob.upload_from_filename(DB_PATH)
    logger.info("UPLOAD: embeddings.db uploaded to GCS")
