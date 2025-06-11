#!/bin/bash

set -e

echo "🔍 [1] Verifying Python deps..."
python3 -c "import fitz" && echo "✅ fitz (PyMuPDF) loaded"

echo "🔍 [2] Running embed.py to confirm it builds embeddings.db..."
rm -f embeddings.db
python3 embed.py
ls -lh embeddings.db

echo "🔍 [3] Verifying Cloud Storage connection..."
gsutil ls -l gs://mystical-gpt-bucket/embeddings.db || echo "ℹ️ First-time upload expected"

echo "🔍 [4] Re-uploading embeddings.db to GCS..."
gsutil cp embeddings.db gs://mystical-gpt-bucket/

echo "🔍 [5] Forcing Cloud Build rebuild..."
gcloud builds submit --tag gcr.io/corded-nature-462101-b4/mystical-gpt-api

echo "🔁 [6] Redeploying Cloud Run..."
gcloud run deploy mystical-gpt-api \
  --image gcr.io/corded-nature-462101-b4/mystical-gpt-api \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --timeout 600 \
  --memory 2Gi

echo "✅ All systems checked and redeployed."
