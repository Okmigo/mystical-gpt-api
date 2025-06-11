# embed.py — Local Embedding Builder (No OpenAI API Required)

# ✅ STEP 1: Install dependencies (run only once)
# pip install pymupdf sentence-transformers google-api-python-client

import os, json, sqlite3, fitz
from io import BytesIO
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from sentence_transformers import SentenceTransformer

# 📁 Google Drive API auth (service account file required)
from google.oauth2 import service_account
creds = service_account.Credentials.from_service_account_file('service_account.json', scopes=["https://www.googleapis.com/auth/drive"])
drive_service = build('drive', 'v3', credentials=creds)
FOLDER_ID = '1XtKZcNHAjCf_FNPJMPOwT8QfqbdD9uvW'  # update if needed

# 🔤 Load local model for embeddings
model = SentenceTransformer('all-MiniLM-L6-v2')

# 📄 Fetch PDF file list
results = drive_service.files().list(
    q=f"'{FOLDER_ID}' in parents and trashed=false and mimeType='application/pdf'",
    fields="files(id, name)"
).execute()
files_list = results.get('files', [])

# 📚 Extract and embed
docs = []
for f in files_list:
    print("📄 Downloading:", f["name"])
    try:
        request = drive_service.files().get_media(fileId=f["id"])
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        # Extract text
        doc_text = ""
        with fitz.open(stream=fh.getvalue(), filetype="pdf") as pdf:
            for page in pdf:
                doc_text += page.get_text()

        trimmed = doc_text[:8000]
        embedding = model.encode(trimmed).tolist()

        docs.append({
            "id": f["id"],
            "title": f["name"],
            "url": f"https://drive.google.com/file/d/{f['id']}/view?usp=drivesdk",
            "text": trimmed,
            "embedding": embedding
        })

    except Exception as e:
        print("❌ Skipped:", f["name"], e)

# 💾 Save to embeddings.json
with open("embeddings.json", "w") as f:
    json.dump(docs, f, indent=2)

# 💾 Save to SQLite
conn = sqlite3.connect("embeddings.db")
cursor = conn.cursor()
cursor.execute("DROP TABLE IF EXISTS documents")
cursor.execute("""
CREATE TABLE documents (
    id TEXT,
    title TEXT,
    url TEXT,
    text TEXT,
    embedding TEXT
)
""")

for doc in docs:
    cursor.execute("""
        INSERT INTO documents (id, title, url, text, embedding)
        VALUES (?, ?, ?, ?, ?)
    """, (
        doc["id"],
        doc["title"],
        doc["url"],
        doc["text"],
        ",".join(map(str, doc["embedding"]))
    ))

conn.commit()
conn.close()

print("✅ Done: embeddings.db and embeddings.json generated locally.")
