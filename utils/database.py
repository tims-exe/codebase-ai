# database.py
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings

class EmbeddingDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.mkdir(exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(allow_reset=True)
        )
        
        self.collection = self.client.get_or_create_collection(
            name="codebase_chunks",
            metadata={"hnsw:space": "cosine"}
        )
    
    def chunk_exists(self, chunk_hash: str) -> bool:
        try:
            results = self.collection.get(ids=[chunk_hash])
            return len(results['ids']) > 0
        except:
            return False
    
    def store_chunk(self, file_path: str, chunk_hash: str, chunk_type: str, 
                   name: str, start_line: int, end_line: int, content: str, 
                   embedding: List[float]):
        metadata = {
            'file_path': file_path,
            'chunk_type': chunk_type,
            'name': name,
            'start_line': start_line,
            'end_line': end_line
        }
        
        self.collection.add(
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata],
            ids=[chunk_hash]
        )
    
    def similarity_search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        return [
            {
                'file_path': results['metadatas'][0][i]['file_path'],
                'chunk_type': results['metadatas'][0][i]['chunk_type'],
                'name': results['metadatas'][0][i]['name'],
                'start_line': results['metadatas'][0][i]['start_line'],
                'end_line': results['metadatas'][0][i]['end_line'],
                'content': results['documents'][0][i],
                'similarity': 1 - results['distances'][0][i]
            }
            for i in range(len(results['ids'][0]))
        ]
    
    def remove_chunks_for_file(self, file_path: str):
        try:
            results = self.collection.get(where={"file_path": file_path})
            if results['ids']:
                self.collection.delete(ids=results['ids'])
        except Exception as e:
            print(f"Error removing chunks for {file_path}: {e}")