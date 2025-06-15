from flask import Flask, request, jsonify
from main_cloud_func import embed_pdfs, upload_to_bucket

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handler():
    try:
        print("TRIGGER: HTTP POST received")
        embed_pdfs()
        upload_to_bucket()
        return jsonify({"status": "success", "message": "embeddings.db updated in GCS"})
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
