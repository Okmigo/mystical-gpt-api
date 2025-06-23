from flask import Flask, request, jsonify
from main_cloud_func import embed_pdfs, download_pdfs_from_drive
import logging
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/download", methods=["POST"])
def trigger_download():
    try:
        logging.info("POST /download received")
        download_pdfs_from_drive()
        return jsonify({"status": "pdfs_downloaded"})
    except Exception as e:
        logging.exception("Download failed")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/embed", methods=["POST"])
def trigger_embedding():
    try:
        limit = int(request.args.get("limit", "1"))
        force = request.args.get("force", "false").lower() == "true"
        logging.info("POST /embed received, force=%s, limit=%d", force, limit)
        modified = embed_pdfs(force=force, limit_files=limit)
        return jsonify({"status": "done", "modified": modified})
    except Exception as e:
        logging.exception("Embedding failed")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status", methods=["GET"])
def check_status():
    status = os.path.exists("/tmp/embeddings.db")
    if status:
        return jsonify({"status": "ready"})
    return jsonify({"status": "missing", "message": "embeddings.db not found"})
