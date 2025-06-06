# File: drive_search_api.py
import os
import json
import numpy as np
import sqlite3
from flask import Flask, request, jsonify, send_file
from sentence_transformers import SentenceTransformer

app = Flask(__name__)
model = SentenceTransformer('all-MiniLM-L6-v2')

DB_PATH = 'embeddings.db'

def init_db():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError("Database not found. Please generate 'embeddings.db' before running the API.")

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

init_db()
data = load_embeddings()
corpus_embeddings = np.array([doc['embedding'] for doc in data])

@app.route('/search', methods=['POST'])
def search():
    query = request.json.get('query', '')
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

@app.route('/openapi.yaml')
def serve_openapi_yaml():
    return send_file('openapi.yaml', mimetype='text/yaml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
