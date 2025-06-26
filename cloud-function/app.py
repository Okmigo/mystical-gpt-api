import os, traceback
from flask import Flask, request, jsonify

print(f"STARTING: PORT={os.getenv('PORT', 'unset')}")

try:
    from main_cloud_func import embed_pdfs, download_pdfs_from_drive
    print("Imported main_cloud_func OK")
except Exception:
    traceback.print_exc()
    raise

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def trigger_embedding():
    force = request.args.get('force', 'false').lower() == 'true'
    return jsonify({'status': 'embedding triggered', 'modified': embed_pdfs(force=force)})

@app.route('/download', methods=['POST'])
def trigger_download():
    download_pdfs_from_drive()
    return jsonify({'status': 'download triggered'})

@app.route('/status', methods=['GET'])
def get_status():
    print("STATUS endpoint hit")
    return jsonify({'status': 'ok'})

if __name__ == "__main__":
    print("END of script reached")
