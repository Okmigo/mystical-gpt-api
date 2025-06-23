from flask import Flask, request, jsonify
from main_cloud_func import embed_pdfs, download_pdfs_from_drive

app = Flask(__name__)

@app.route('/', methods=['POST'])
def trigger_embedding():
    force = request.args.get('force', 'false').lower() == 'true'
    modified = embed_pdfs(force=force)
    return jsonify({'status': 'embedding triggered', 'modified': modified})

@app.route('/download', methods=['POST'])
def trigger_download():
    download_pdfs_from_drive()
    return jsonify({'status': 'download triggered'})

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({'status': 'ok'})

