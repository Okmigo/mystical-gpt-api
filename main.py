# main.py — Mystical GPT API Server (SentenceTransformer, 384-dim)

import os, sqlite3, json
from fastapi import FastAPI, Request
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util
import uvicorn
from google.cloud import storage

# ✅ Load model (must match embedding generation)
model = SentenceTransformer("all-MiniLM-L6-v2")

# ✅ Load DB
DB_PATH = "embeddings.db"

# 🔍 Request schema
class QueryRequest(BaseModel):
    query: str

app = FastAPI()

# 🔎 Cosine similarity search
@app.post("/search")
def search_docs(request: QueryRequest):
    query = request.query
    query_embedding = model.encode(query)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, text, embedding FROM documents")
    results = []

    for row in cursor.fetchall():
        try:
            emb = list(map(float, row[4].split(",")))
            score = util.cos_sim(query_embedding, emb).item()
            results.append((score, row[1], row[3]))
        except:
            continue

    conn.close()

    if not results:
        return {"answer": "No results found."}

    # 🥇 Best match
    results.sort(reverse=True)
    top_score, top_title, top_text = results[0]

    return {"answer": f"📘 {top_title}\n\n{top_text[:1200]}..."}

# 🔁 Health check
@app.get("/ping")
def ping():
    return {"message": "pong"}

# ⬇️ GCS Download
def download_db():
    bucket_name = "mystical-gpt-bucket"
    source_blob_name = "embeddings.db"
    destination_file_name = "embeddings.db"

    if os.path.exists(destination_file_name):
        return

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)
    print("✅ Downloaded embeddings.db from GCS")

# 🖥️ Run server
if __name__ == "__main__":
    download_db()
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
