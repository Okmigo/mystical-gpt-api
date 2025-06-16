import os
from flask import Flask, request, jsonify
import threading
from datetime import datetime
from main_cloud_func import embed_pdfs, upload_to_bucket

app = Flask(__name__)

def run_embedding(force: bool = False):
    try:
        print("TRIGGER: HTTP POST received")

        def run_background():
            print("START: embed_pdfs")
            embed_pdfs(force=force)
            print("DONE: embed_pdfs")

            print("START: upload_to_bucket")
            upload_to_bucket()
            print("DONE: upload_to_bucket")

        threading.Thread(target=run_background).start()
        return jsonify({"status": "accepted", "message": "Embedding started in background"}), 202
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/", methods=["POST"])
def handler():
    force = request.args.get("force", "false").lower() == "true"
    return run_embedding(force)

@app.route("/status", methods=["GET"])
def status():
    try:
        path = "embeddings/embeddings.db"
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            modified_at = datetime.utcfromtimestamp(mtime).isoformat() + "Z"
            return jsonify({
                "status": "ok",
                "embeddings_db_last_modified": modified_at
            })
        else:
            return jsonify({"status": "missing", "message": "embeddings.db not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
