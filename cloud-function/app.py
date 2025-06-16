from flask import Flask, request, jsonify
import threading
from main_cloud_func import embed_pdfs, upload_to_bucket

app = Flask(__name__)

def run_embedding():
    try:
        print("BACKGROUND: Started embedding job")
        embed_pdfs()
        upload_to_bucket()
        print("BACKGROUND: Embedding complete and uploaded")
    except Exception as e:
        print("ERROR in background thread:", str(e))

@app.route("/", methods=["POST"])
def handler():
    threading.Thread(target=run_embedding).start()
    return jsonify({"status": "accepted", "message": "Embedding started in background"}), 202

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)

def handler():
    try:
        print("TRIGGER: HTTP POST received")
        
        def run_background():
            print("START: embed_pdfs")
            embed_pdfs()
            print("DONE: embed_pdfs")

            print("START: upload_to_bucket")
            upload_to_bucket()
            print("DONE: upload_to_bucket")

        Thread(target=run_background).start()
        return jsonify({"status": "accepted", "message": "Embedding started in background"}), 202
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

