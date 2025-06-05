# File: generate_db.py
import os
import json
import sqlite3
import requests
import tempfile
import numpy as np
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer

# Load index
with open("drive_index.json", "r") as f:
    index = json.load(f)

model = SentenceTransformer("all-MiniLM-L6-v2")

def extract_pdf_text(file_path):
    reader = PdfReader(file_path)
    return "\n".join([page.extract_text() or "" for page in reader.pages])

def download_file(url):
    file_id = url.split("/d/")[1].split("/")[0]
    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(direct_url)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(response.content)
        return tmp.name

def init_db():
    conn = sqlite3.connect("embeddings.db")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS documents")
    cursor.execute("""
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            text TEXT,
            embedding TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_document(doc):
    conn = sqlite3.connect("embeddings.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?)", (
        doc['id'], doc['title'], doc['url'], doc['text'], doc['embedding']
    ))
    conn.commit()
    conn.close()

init_db()

for entry in index:
    print(f"Processing: {entry['title']}")
    try:
        pdf_path = download_file(entry['url'])
        text = extract_pdf_text(pdf_path)
        os.remove(pdf_path)
        
        emb = model.encode(text)
        emb_str = ",".join(map(str, emb))

        insert_document({
            "id": entry['id'],
            "title": entry['title'],
            "url": entry['url'],
            "text": text[:3000],  # Limit size
            "embedding": emb_str
        })
        print("✅ Done")
    except Exception as e:
        print(f"❌ Failed: {e}")
