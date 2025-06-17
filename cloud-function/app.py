from flask import Flask, request, jsonify
from main_cloud_func import embed_pdfs, upload_to_bucket
import os
import sqlite3
import threading

app = Flask(__name__)

DB_PATH = "/tmp/embeddings.db"

@app.route("/", methods=["POST"])
def trigger_embedding():
    force = request.args.get("force") == "true"

    def run_background():
        try:
            print(f"BACKGROUND: Started embedding job (force = {force} )")
            if force and os.path.exists(DB_PATH):
                os.remove(DB_PATH)
                print("FORCE: Removed existing embeddings.db")

            print("START: embed_pdfs")
            embed_pdfs(force=force)
            print("DONE: embed_pdfs")

            print("START: upload_to_bucket")
            upload_to_bucket()
            print("DONE: upload_to_bucket")
        except Exception as e:
            print("ERROR in background thread:", str(e))

    threading.Thread(target=run_background).start()

    return jsonify({"status": "accepted", "message": "Embedding started in background"}), 202


@app.route("/status", methods=["GET"])
def status():
    exists = os.path.exists(DB_PATH)
    if exists:
        size = os.path.getsize(DB_PATH)
        return jsonify({"status": "ok", "message": "embeddings.db exists", "size_bytes": size})
    else:
        return jsonify({"status": "missing", "message": "embeddings.db not found"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
