# File: drive_search_api.py
import os
import io
import json
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import fitz  # PyMuPDF

# === CONFIGURATION ===
FOLDER_ID = "1XtKZcNHAjCf_FNPJMPOwT8QfqbdD9uvW"
SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

app = Flask(__name__)

# === Authenticate with Google Drive API ===
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=credentials)

# === Utility: Download and extract PDF text ===
def extract_text_from_drive_file(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    try:
        doc = fitz.open(stream=fh.read(), filetype="pdf")
        text = "\n".join([page.get_text() for page in doc])
        return text[:5000]  # Limit for performance
    except Exception as e:
        return f"[Error reading PDF: {str(e)}]"

# === Route: Search files in Google Drive ===
@app.route("/search", methods=["POST"])
def search_drive():
    query = request.json.get("query", "").lower()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    results = []
    response = (
        drive_service.files()
        .list(q=f"'{FOLDER_ID}' in parents and mimeType='application/pdf'",
              fields="files(id, name)")
        .execute()
    )
    files = response.get("files", [])

    for f in files:
        text = extract_text_from_drive_file(f["id"]).lower()
        if query in text:
            snippet_index = text.find(query)
            snippet = text[snippet_index:snippet_index + 300]
            results.append({
                "title": f["name"],
                "url": f"https://drive.google.com/file/d/{f['id']}/view",
                "snippet": snippet
            })

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
