# rag.py
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class RAG:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.index = faiss.IndexFlatL2(384)  # embedding size

    def add_doc(self, text: str):
        vec = self.model.encode([text])
        self.index.add(np.array(vec, dtype="float32"))

    def query(self, text: str, top_k=3):
        vec = self.model.encode([text])
        D, I = self.index.search(np.array(vec, dtype="float32"), top_k)
        return I, D