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
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

BUCKET_NAME = "mystical-gpt-bucket"
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "all-MiniLM-L6-v2")
DB_PATH = os.path.join(tempfile.gettempdir(), "embeddings.db")
PDF_DIR = os.path.join(tempfile.gettempdir(), "pdfs")
DRIVE_FOLDER_ID = "1XtKZcNHAjCf_FNPJMPOwT8QfqbdD9uvW"

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

def download_pdfs_from_drive():
    credentials = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
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
            _, done = downloader.next_chunk()
        print(f"DOWNLOADED FROM DRIVE: {file['name']}")

def embed_pdfs(force: bool = False) -> bool:
    download_existing_db()
    download_pdfs_from_drive()

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
    for filename in os.listdir(PDF_DIR):
        if not filename.endswith(".pdf"):
            continue

        if not force and filename in existing_files:
            continue

        local_path = os.path.join(PDF_DIR, filename)
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
