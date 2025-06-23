from flask import Flask, request, jsonify
from main_cloud_func import embed_pdfs
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/", methods=["POST"])
def trigger_embedding():
    force = request.args.get("force", "false").lower() == "true"
    try:
        logging.info("POST / received, force=%s", force)
        # Test with a single file first
        modified = embed_pdfs(force=force, limit_files=1)
        return jsonify({"status": "done", "modified": modified})
    except Exception as e:
        logging.exception("Error during embedding")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status", methods=["GET"])
def check_status():
    import os
    status = os.path.exists("embeddings.db")
    if status:
        return jsonify({"status": "ready"})
    return jsonify({"status": "missing", "message": "embeddings.db not found"})
