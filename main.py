from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import requests
import tempfile
import os

from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA

import pickle
import urllib.request

app = FastAPI()

# Allow CORS for all
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model
class Query(BaseModel):
    query: str

# Load FAISS index from public GCS bucket
EMBEDDING_DB_URL = "https://storage.googleapis.com/mystical-gpt-data/embeddings.db"

with tempfile.TemporaryDirectory() as tmpdir:
    local_path = os.path.join(tmpdir, "embeddings.db")
    urllib.request.urlretrieve(EMBEDDING_DB_URL, local_path)

    with open(local_path, "rb") as f:
        vectorstore = pickle.load(f)

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    qa_chain = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(temperature=0),
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
    )

@app.get("/ping")
async def ping():
    return {"message": "pong"}

@app.post("/search")
async def search(query: Query):
    result = qa_chain(query.query)
    return {"answer": result["result"]}
