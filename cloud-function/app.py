# /cloud-function/app.py
from flask import Flask, request, jsonify
from threading import Thread
from main_cloud_func import embed_pdfs, upload_to_bucket

app = Flask(__name__)

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
