# /cloud-function/app.py
from flask import Flask, request, jsonify
from threading import Thread
from main_cloud_func import embed_pdfs, upload_to_bucket
import os
import datetime

app = Flask(__name__)

EMBEDDINGS_DB = "/tmp/embeddings.db"


def run_background(force: bool = False):
    try:
        print("BACKGROUND: Started embedding job (force =", force, ")")
        embed_pdfs(force=force)
        upload_to_bucket()
        print("BACKGROUND: Embedding complete and uploaded")
    except Exception as e:
        print("ERROR in background thread:", str(e))


@app.route("/", methods=["POST"])
def handler():
    force = request.args.get("force", "false").lower() == "true"
    Thread(target=run_background, args=(force,)).start()
    return jsonify({"status": "accepted", "message": "Embedding started in background"}), 202


@app.route("/status", methods=["GET"])
def status():
    if os.path.exists(EMBEDDINGS_DB):
        timestamp = datetime.datetime.utcfromtimestamp(os.path.getmtime(EMBEDDINGS_DB)).isoformat() + "Z"
        size = os.path.getsize(EMBEDDINGS_DB)
        return jsonify({
            "status": "ok",
            "last_modified": timestamp,
            "size_bytes": size
        }), 200
    else:
        return jsonify({"status": "missing", "message": "embeddings.db not found"}), 404


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
