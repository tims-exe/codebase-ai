# embeddings.py
from typing import List
from langchain_huggingface import HuggingFaceEmbeddings

embeddings_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

def get_embedding(text: str) -> List[float]:
    try:
        embedding = embeddings_model.embed_query(text)
        return embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return [0.0] * 384