# File: main.py
import os
import json
import numpy as np
import sqlite3
import requests
from flask import Flask, request, jsonify, send_file
from sentence_transformers import SentenceTransformer

app = Flask(__name__)
model = SentenceTransformer('all-MiniLM-L6-v2')

GCS_URL = 'https://storage.googleapis.com/mystical-gpt-bucket/embeddings.db'
DB_PATH = 'embeddings.db'

# Download from GCS if missing
def download_embeddings():
    if not os.path.exists(DB_PATH):
        print(f"⬇ Downloading {DB_PATH} from {GCS_URL}...")
        r = requests.get(GCS_URL)
        with open(DB_PATH, 'wb') as f:
            f.write(r.content)
        print("✅ Download complete.")
    print(f"💾 Checking if {DB_PATH} exists:", os.path.exists(DB_PATH))
    print("📦 Contents of current dir:", os.listdir())

# Load vectors from database
def load_embeddings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, text, embedding FROM documents")
    data = []
    for row in cursor.fetchall():
        doc_id, title, url, text, emb_str = row
        embedding = np.fromstring(emb_str, sep=',')
        data.append({
            'id': doc_id,
            'title': title,
            'url': url,
            'text': text,
            'embedding': embedding
        })
    conn.close()
    return data

try:
    download_embeddings()
    data = load_embeddings()
    corpus_embeddings = np.array([doc['embedding'] for doc in data])
except Exception as e:
    print(f"❌ Failed to load embeddings: {e}")
    data = []
    corpus_embeddings = np.array([])

@app.route('/search', methods=['POST'])
def search():
    try:
        body = request.get_json()
        query = body.get('query', '')
        if not query:
            return jsonify({'error': 'Missing query'}), 400

        query_vec = model.encode(query)
        scores = np.dot(corpus_embeddings, query_vec)
        top_idx = np.argsort(scores)[::-1][:5]

        results = []
        for i in top_idx:
            doc = data[i]
            results.append({
                'title': doc['title'],
                'url': doc['url'],
                'score': float(scores[i]),
                'snippet': doc['text'][:500] + '...'
            })
        return jsonify(results)

    except Exception as e:
        print(f"❌ Exception in /search: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/openapi.yaml')
def serve_openapi_yaml():
    try:
        return send_file('docs/openapi.yaml', mimetype='text/yaml')
    except Exception as e:
        return jsonify({'error': f'Missing openapi.yaml: {e}'}), 500

@app.route('/ping')
def ping():
    return '✅ API is alive!'

def create_app():
    return app

# Required by Cloud Run
if __name__ != '__main__':
    gunicorn_app = app

# Local run fallback
if __name__ == '__main__':
    print("📢 Running Flask development server...")
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
