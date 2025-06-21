









Welcome to Cloud Shell! Type "help" to get started.
Your Cloud Platform project in this session is set to corded-nature-462101-b4.
Use `gcloud config set project [PROJECT_ID]` to change to a different project.
t_miguel1217@cloudshell:~ (corded-nature-462101-b4)$ cd ~/mystical-gpt-api/cloud-function
t_miguel1217@cloudshell:~/mystical-gpt-api/cloud-function (corded-nature-462101-b4)$ import os
import io
import fitz  # PyMuPDF
import sqlite3
import tempfile
import time
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from google.cloud import storage
from google.cloud import secretmanager
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

