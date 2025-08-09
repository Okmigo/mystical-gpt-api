# main.py — Mystical GPT API Server (SentenceTransformer, 384‑dim)

import os, sqlite3
from fastapi import FastAPI
from typing import Optional, List, Dict
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
    """
    Schema for search requests.  The `query` string describes the concept to search
    for (e.g. a tradition name).  The optional `limit` determines how many top
    documents to return.  If `limit` is omitted or invalid, a default will be
    applied.

    Including a limit allows the client to request more than just the single best
    match so it can derive richer metadata (such as activity windows) from the
    corpus.  Without a limit the API will return a reasonable default.
    """
    query: str
    limit: Optional[int] = None

app = FastAPI()

# 🔎 Cosine similarity search
@app.post("/search")
def search_docs(request: QueryRequest) -> Dict[str, object]:
    """
    Perform a semantic search across all documents using cosine similarity on
    sentence-transformer embeddings.  Returns a list of top matching documents
    with their scores and snippets, as well as an aggregated time window for
    the query based on all matched documents.

    The similarity search scans every document in the SQLite database, so
    behaviour scales linearly with the number of documents.  The client may
    specify `limit` in the request body to control how many of the top results
    are returned; if omitted a default of 10 is used.  Each result includes
    the document title, a short snippet from its beginning, and the
    similarity score.  The API also attempts to derive a plausible activity
    window for the query by extracting years and centuries from all matched
    document texts.
    """
    query: str = request.query
    limit: int = request.limit if isinstance(request.limit, int) and request.limit > 0 else 10

    # Compute the embedding for the query once
    query_embedding = model.encode(query)

    # Prepare lists for results and years
    results: List[tuple] = []  # (score, title, text)
    years: List[int] = []

    # Open SQLite database and iterate over all documents
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, text, embedding FROM documents")
    for row in cursor.fetchall():
        try:
            # Parse stored embedding (comma-separated floats)
            emb = [float(x) for x in row[4].split(",")]
            score = float(util.cos_sim(query_embedding, emb).item())
            results.append((score, row[1], row[3]))
            # Collect year candidates from the text for later aggregation
            years.extend(_extract_years(row[3]))
        except Exception:
            # Skip malformed rows without failing the entire request
            continue
    conn.close()

    # If no documents were processed, return early
    if not results:
        return {"query": query, "results": [], "time_window": None}

    # Sort by descending similarity
    results.sort(key=lambda x: x[0], reverse=True)

    # Compose top-N results with snippet and score
    top_results = []
    for score, title, text in results[:limit]:
        snippet = (text or "")[:300].replace("\n", " ").strip()
        top_results.append({
            "title": title,
            "score": score,
            "snippet": snippet
        })

    # Aggregate activity window across all candidate years
    window = _compute_time_window(years) if years else None

    return {
        "query": query,
        "results": top_results,
        "time_window": window
    }


def _extract_years(text: str) -> List[int]:
    """
    Extract candidate years from a block of text.  Recognises patterns like
    "12th century BCE", "300 BC", "c. 500 CE", and plain four-digit years.  Returns
    a list of signed integers representing years (negative for BCE/BC).

    To avoid conflating publication dates with the activity period of a
    tradition, values greater than 1900 are ignored.  Plain four-digit
    numbers are only treated as years if they are between 500 and 1900.
    """
    import re
    candidates: List[int] = []
    if not text:
        return candidates
    s = text
    # Century patterns (e.g. "12th century BCE", "15th century AD")
    century_pattern = re.compile(r"(\d{1,2})(st|nd|rd|th)?\s*century\s*(BCE|BC|CE|AD)?", re.IGNORECASE)
    # Year patterns (e.g. "300 BC", "c. 500 CE", "1200")
    year_pattern = re.compile(r"(c\.\s*)?(\d{1,4})\s*(BCE|BC|CE|AD)?", re.IGNORECASE)

    # Scan for centuries
    for match in century_pattern.finditer(s):
        century_num = int(match.group(1))
        era = (match.group(3) or "").upper()
        if era in ("BC", "BCE"):
            # In BCE centuries, the nth century BCE spans years [-(n*100) + 1, -(n-1)*100]
            high = -((century_num - 1) * 100)
            low = -century_num * 100 + 1
        else:
            # CE centuries span [(n-1)*100, n*100 - 1]
            low = (century_num - 1) * 100
            high = century_num * 100 - 1
        candidates.extend([low, high])

    # Scan for explicit years
    for match in year_pattern.finditer(s):
        num = int(match.group(2))
        era = (match.group(3) or "").upper()
        if era in ("BC", "BCE"):
            year = -num
        else:
            year = num
        # Ignore implausible modern years
        if abs(year) > 1900:
            continue
        # Exclude small numbers that are unlikely to be years
        if year < -3000:
            continue
        # For plain numbers without era, restrict to 500–1900 to avoid picking up
        # page numbers or ID codes
        if not era and not (500 <= year <= 1900):
            continue
        candidates.append(year)

    return candidates


def _compute_time_window(years: List[int]) -> Optional[Dict[str, int]]:
    """
    Given a list of integer years, compute an aggregated time window.
    Returns a dictionary with keys `start_low`, `start_high`, `end_low`, and
    `end_high`, or None if the list is empty.  A 25‑year padding is applied
    around the earliest and latest years to account for uncertainty.
    """
    if not years:
        return None
    years_sorted = sorted(set(years))
    earliest = years_sorted[0]
    latest = years_sorted[-1]
    padding = 25
    return {
        "start_low": earliest - padding,
        "start_high": earliest,
        "end_low": latest,
        "end_high": latest + padding
    }

# 🔁 Health check
@app.get("/ping")
def ping():
    return {"message": "pong"}

# ⬇️ GCS Download
def download_db():
    bucket_name = "mysticalbucket"
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
