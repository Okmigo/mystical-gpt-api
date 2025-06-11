import base64, json, os, tempfile, sqlite3, fitz
from googleapiclient.discovery import build
from google.oauth2 import service_account
from sentence_transformers import SentenceTransformer
from google.cloud import storage

FOLDER_ID = "1XtKZcNHAjCf_FNPJMPOwT8QfqbdD9uvW"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DB_BUCKET = "mystical-gpt-db"
DB_FILE = "embeddings.db"
SERVICE_ACCOUNT_FILE = "service_account.json"

def download_and_embed(event, context):
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    drive = build("drive", "v3", credentials=creds)
    storage_client = storage.Client()

    model = SentenceTransformer("all-MiniLM-L6-v2")
    docs = []

    result = drive.files().list(
        q=f"'{FOLDER_ID}' in parents and trashed=false and mimeType='application/pdf'",
        fields="files(id, name)"
    ).execute()

    for f in result.get("files", []):
        request = drive.files().get_media(fileId=f["id"])
        fh = tempfile.NamedTemporaryFile(delete=False)
        downloader = drive._http.request(request.uri)
        fh.write(downloader[1])
        fh.close()

        text = ""
        with fitz.open(fh.name) as doc:
            for page in doc:
                text += page.get_text()
        os.remove(fh.name)

        trimmed = text[:8000]
        emb = model.encode(trimmed).tolist()

        docs.append((f["id"], f["name"],
                     f"https://drive.google.com/file/d/{f['id']}/view",
                     trimmed, ",".join(map(str, emb))))

    tmpdb = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    conn = sqlite3.connect(tmpdb.name)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS documents")
    c.execute("""CREATE TABLE documents (id TEXT, title TEXT, url TEXT, text TEXT, embedding TEXT)""")
    c.executemany("INSERT INTO documents VALUES (?, ?, ?, ?, ?)", docs)
    conn.commit()
    conn.close()

    bucket = storage_client.bucket(DB_BUCKET)
    blob = bucket.blob(DB_FILE)
    blob.upload_from_filename(tmpdb.name)
    os.remove(tmpdb.name)
    print("✅ Uploaded latest embeddings.db")
