# main.py — Mystical GPT API (optimized)
import os, sqlite3, json, logging, math
from typing import List, Optional, Tuple
from functools import lru_cache

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer, util

# Optional: fetch embeddings.db from GCS at startup if not present
GCS_ENABLED = True
try:
    from google.cloud import storage
except Exception:
    GCS_ENABLED = False

# ---------- Settings ----------
MODEL_NAME = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
DB_PATH    = os.getenv("DB_PATH", "/app/embeddings.db")
BUCKET     = os.getenv("BUCKET_NAME")           # e.g. mysticalbucket
DB_OBJECT  = os.getenv("DB_OBJECT", "embeddings.db")
MAX_SNIPPET_CHARS_DEFAULT = 600

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mystical-gpt")

# ---------- App ----------
app = FastAPI(title="Mystical GPT API", version="1.1.0")

# ---------- Models ----------
class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural-language query")

class SearchDocsRequest(BaseModel):
    query: str = Field(..., description="Natural-language query")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return")
    min_score: float = Field(0.18, ge=-1.0, le=1.0, description="Cosine similarity threshold")
    max_snippet_chars: int = Field(MAX_SNIPPET_CHARS_DEFAULT, ge=120, le=4000)
    include_text: bool = Field(False, description="Return full text (big responses)")

# ---------- Startup helpers ----------
def _download_db_if_needed():
    """Download embeddings.db from GCS if DB_PATH is missing and env is set."""
    if os.path.exists(DB_PATH):
        log.info("DB present at %s", DB_PATH)
        return
    if not (GCS_ENABLED and BUCKET and DB_OBJECT):
        log.warning("DB missing and GCS not configured; expected at %s", DB_PATH)
        return
    log.info("Downloading gs://%s/%s -> %s", BUCKET, DB_OBJECT, DB_PATH)
    client = storage.Client()
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(DB_OBJECT)
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    blob.download_to_filename(DB_PATH)
    log.info("DB downloaded: %s (%.2f MB)", DB_PATH, os.path.getsize(DB_PATH)/1e6)

def _load_db() -> Tuple[np.ndarray, List[dict]]:
    """Load embeddings.db -> (emb_matrix[n, d], rows_meta list)."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"DB not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Expect: documents(id TEXT, title TEXT, url TEXT, text TEXT, embedding TEXT)
    rows = c.execute("SELECT id, title, url, text, embedding FROM documents").fetchall()
    conn.close()

    meta: List[dict] = []
    vecs: List[np.ndarray] = []
    bad, dim = 0, None

    for (id_, title, url, text, emb_text) in rows:
        try:
            arr = np.fromstring(emb_text, sep=",", dtype=np.float32)
            if dim is None:
                dim = arr.shape[0]
            if arr.shape[0] != dim or dim == 0:
                bad += 1
                continue
            # Normalize for cosine via dot product
            norm = np.linalg.norm(arr)
            if norm == 0:
                bad += 1
                continue
            arr = arr / norm
            vecs.append(arr)
            meta.append({
                "id": id_,
                "title": title,
                "url": url,
                "text": text
            })
        except Exception:
            bad += 1
            continue

    if not vecs:
        raise RuntimeError("No valid embeddings found in DB")
    emb = np.vstack(vecs)  # [n, d]
    log.info("Loaded %d rows (skipped %d), dim=%d", emb.shape[0], bad, emb.shape[1])
    return emb, meta

def _snippet(text: str, query: str, max_chars: int) -> str:
    """
    Cheap snippet: try to center around the first occurrence of a query token; else head.
    """
    if not text:
        return ""
    toks = [t for t in query.split() if len(t) > 3]
    idx = -1
    for t in toks:
        idx = text.lower().find(t.lower())
        if idx >= 0:
            break
    if idx < 0:
        return text[:max_chars]
    start = max(0, idx - max_chars // 2)
    end = min(len(text), start + max_chars)
    return text[start:end]

# ---------- Global state (loaded once) ----------
_download_db_if_needed()
log.info("Loading model: %s", MODEL_NAME)
model = SentenceTransformer(MODEL_NAME)

# emb_matrix: L2-normalized; docs_meta: list of dicts (id,title,url,text)
emb_matrix, docs_meta = _load_db()
emb_dim = emb_matrix.shape[1]

# ---------- Search core ----------
@lru_cache(maxsize=256)
def _encode_query_normed(q: str) -> np.ndarray:
    v = model.encode(q, convert_to_numpy=True, normalize_embeddings=True)
    # Some ST versions already normalize; ensure L2 norm ~1
    n = np.linalg.norm(v)
    if n == 0:
        return v
    return v / n

def _topk(query: str, top_k: int) -> List[Tuple[int, float]]:
    qv = _encode_query_normed(query)  # [d]
    # cosine = dot because both normalized
    sims = emb_matrix @ qv  # [n]
    # argsort desc
    idx = np.argpartition(-sims, kth=min(top_k, sims.size-1))[:top_k]
    # sort properly
    idx = idx[np.argsort(-sims[idx])]
    return [(int(i), float(sims[i])) for i in idx]

# ---------- Routes ----------
@app.get("/ping")
def ping():
    return {"message": "pong"}

@app.post("/search")
def search_simple(req: QueryRequest):
    """Back-compat: returns a single best answer string."""
    pairs = _topk(req.query, top_k=1)
    if not pairs:
        return {"answer": "No results found."}
    i, score = pairs[0]
    meta = docs_meta[i]
    snippet = _snippet(meta["text"], req.query, MAX_SNIPPET_CHARS_DEFAULT)
    answer = f"📘 {meta['title']}\n\n{snippet}"
    return {"answer": answer}

@app.post("/searchDocs")
def search_docs(req: SearchDocsRequest):
    pairs = _topk(req.query, top_k=max(req.top_k, 1))
    results = []
    for i, score in pairs:
        if score < req.min_score:
            continue
        meta = docs_meta[i]
        item = {
            "id": meta["id"],
            "title": meta["title"],
            "url": meta["url"],
            "score": round(score, 4),
            "snippet": _snippet(meta["text"], req.query, req.max_snippet_chars),
        }
        if req.include_text:
            item["text"] = meta["text"]
        results.append(item)

    return {
        "query": req.query,
        "count": len(results),
        "results": results,
        "used": {
            "model": MODEL_NAME,
            "db_path": DB_PATH,
            "rows_indexed": emb_matrix.shape[0],
            "embed_dim": emb_dim
        }
    }

# ---------- Local run ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=False)
