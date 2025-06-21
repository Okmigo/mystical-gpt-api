import os
import io
import fitz  # PyMuPDF
import sqlite3
import tempfile
import time
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from google.cloud import storage
from google.cloud import secretmanager

BUCKET_NAME = "mystical-gpt-bucket"
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "all-MiniLM-L6-v2")
DB_PATH = os.path.join(tempfile.gettempdir(), "embeddings.db")
PDF_DIR = os.path.join(tempfile.gettempdir(), "pdfs")

os.makedirs(PDF_DIR, exist_ok=True)

model = SentenceTransformer(MODEL_PATH)

def download_secret(secret_id: str, version_id: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def download_existing_db():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    if blob.exists():
        blob.download_to_filename(DB_PATH)
        print("EXISTING DB DOWNLOADED")

def save_to_db(data: list[tuple[str, str, list[float]]]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        text TEXT,
        embedding BLOB
    )''')
    for filename, text, embedding in data:
        c.execute("INSERT INTO documents (filename, text, embedding) VALUES (?, ?, ?)", (filename, text, sqlite3.Binary(bytearray(embedding))))
    conn.commit()
    conn.close()

def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    return text

def embed_pdfs(force: bool = False) -> bool:
    download_existing_db()
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix="pdfs/")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        text TEXT,
        embedding BLOB
    )""")
    c.execute("SELECT filename FROM documents")
    existing_files = {row[0] for row in c.fetchall()}
    conn.close()

    new_data = []
    for blob in blobs:
        if not blob.name.endswith(".pdf"):
            continue

        filename = os.path.basename(blob.name)
        if not force and filename in existing_files:
            continue

        local_path = os.path.join(PDF_DIR, filename)
        blob.download_to_filename(local_path)
        print(f"PROCESSING: {filename}")

        try:
            text = extract_text_from_pdf(local_path)
            if not text.strip():
                continue
            embeddings = model.encode([text])[0]
            new_data.append((filename, text, embeddings))
        except Exception as e:
            print(f"ERROR processing {filename}: {e}")

    if new_data:
        save_to_db(new_data)
        return True
    return False

def upload_to_bucket():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob("embeddings.db")
    blob.upload_from_filename(DB_PATH)
    print("UPLOAD: embeddings.db uploaded to GCS")
