from flask import Flask, request, jsonify
from main_cloud_func import embed_pdfs

app = Flask(__name__)


@app.route("/", methods=["POST"])
def trigger_embedding():
    force = request.args.get("force", "false").lower() == "true"
    try:
        modified = embed_pdfs(force=force)
        return jsonify({"status": "done", "modified": modified})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/status", methods=["GET"])
def check_status():
    import os
    if os.path.exists("embeddings.db"):
        return jsonify({"status": "ready"})
    return jsonify({"status": "missing", "message": "embeddings.db not found"})
