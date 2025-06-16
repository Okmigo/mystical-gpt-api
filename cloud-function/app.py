from flask import Flask, request, jsonify
from threading import Thread
import os

from main_cloud_func import embed_pdfs, upload_to_bucket

app = Flask(__name__)

STATUS_FILE = "embeddings/embeddings.db"

# Background embedding process
def run_embedding(force: bool = False):
    try:
        print("START: embed_pdfs")
        embed_pdfs(force=force)
        print("DONE: embed_pdfs")

        print("START: upload_to_bucket")
        upload_to_bucket()
        print("DONE: upload_to_bucket")
    except Exception as e:
        print("ERROR in background thread:", str(e))

# POST endpoint
@app.route("/", methods=["POST"])
def trigger():
    force = request.args.get("force", "false").lower() == "true"
    Thread(target=run_embedding, args=(force,)).start()
    return jsonify({"status": "accepted", "message": "Embedding started in background"}), 202

# Status endpoint
@app.route("/status", methods=["GET"])
def status():
    if os.path.exists(STATUS_FILE):
        size = os.path.getsize(STATUS_FILE)
        return jsonify({"status": "ready", "size": size, "message": "embeddings.db available"})
    return jsonify({"status": "missing", "message": "embeddings.db not found"}), 404

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
