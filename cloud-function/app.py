from flask import Flask, request, jsonify
from threading import Thread
from main_cloud_func import embed_pdfs, upload_to_bucket

app = Flask(__name__)

def run_background(force=False):
    try:
        print("START: embed_pdfs")
        if force:
            import os
            DB_PATH = "/tmp/embeddings.db"
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
                print("FORCE: Removed existing DB")
        embed_pdfs()
        print("DONE: embed_pdfs")

        print("START: upload_to_bucket")
        upload_to_bucket()
        print("DONE: upload_to_bucket")
    except Exception as e:
        print("ERROR in background thread:", str(e))

@app.route("/", methods=["POST"])
def handler():
    print("TRIGGER: HTTP POST received")
    force = request.args.get("force", "false").lower() == "true"
    Thread(target=run_background, args=(force,)).start()
    return jsonify({"status": "accepted", "message": "Embedding started in background"}), 202

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
