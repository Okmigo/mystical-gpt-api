import os
import sqlite3
import time
from flask import Flask, request, jsonify
from main_cloud_func import embed_pdfs, upload_to_bucket

app = Flask(__name__)
DB_PATH = "/tmp/embeddings.db"

@app.route("/", methods=["POST"])
def trigger_embedding():
    force = request.args.get("force", "false").lower() == "true"
    try:
        print("TRIGGER: HTTP POST received")
        if force and os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            print("FORCE: Removed existing embeddings.db")

        print("START: embed_pdfs")
        start_time = time.time()
        modified = embed_pdfs(force=force)
        duration = time.time() - start_time
        print(f"DONE: embed_pdfs in {duration:.2f}s")

        if modified:
            print("START: upload_to_bucket")
            upload_to_bucket()
            print("DONE: upload_to_bucket")
        else:
            print("SKIP: No new documents embedded. Upload skipped.")

        return jsonify({
            "status": "success",
            "message": "Embedding completed",
            "duration_seconds": duration,
            "new_docs_embedded": modified
        }), 200
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status", methods=["GET"])
def status():
    exists = os.path.exists(DB_PATH)
    if exists:
        size = os.path.getsize(DB_PATH)
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM documents")
            count = c.fetchone()[0]
            conn.close()
        except Exception as e:
            count = "error"
            print("ERROR reading DB count:", e)
        return jsonify({"status": "ok", "message": "embeddings.db exists", "size_bytes": size, "doc_count": count})
    else:
        return jsonify({"status": "missing", "message": "embeddings.db not found"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
