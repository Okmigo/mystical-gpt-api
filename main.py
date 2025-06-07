import os
import json
import requests
import shutil
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain.vectorstores import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

@app.post("/search")
async def search_docs(req: QueryRequest):
    query = req.query.strip()
    if not query:
        return {"error": "Empty query"}

    try:
        db_path = "embeddings.db"
        if not os.path.exists(db_path):
            url = "https://storage.googleapis.com/mystical-gpt-data/embeddings.db"
            response = requests.get(url, stream=True)
            with open(db_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)

        db = FAISS.load_local(db_path, OpenAIEmbeddings(), allow_dangerous_deserialization=True)
        retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 4})

        prompt = PromptTemplate(
            input_variables=["context", "question"],
            template="""
You are a helpful AI assistant. Use the following context to answer the question at the end.
Include only the most relevant direct quotations. Do not include any document titles, links, or citations.

Context:
{context}

Question:
{question}

Answer:""")

        chain = RetrievalQA.from_chain_type(
            llm=ChatOpenAI(temperature=0),
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": prompt},
            return_source_documents=False
        )

        result = chain({"query": query})
        return {"answer": result.get("result", "No result found")}

    except Exception as e:
        return {"error": str(e)}

@app.get("/ping")
async def ping():
    return {"message": "pong"}

@app.get("/")
async def root():
    return {"message": "Mystical GPT API is live."}