# File: gpt_query_api.py
import json
import numpy as np
from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer

app = Flask(__name__)

# Load embeddings
with open('embedded_data.json', 'r') as f:
    data = json.load(f)

# Model for encoding queries
model = SentenceTransformer('all-MiniLM-L6-v2')

# Preload all embeddings
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
