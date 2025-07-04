# database.py
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

class EmbeddingDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.mkdir(exist_ok=True)
        
        # Initialize Chroma client
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
        
        chunks = []
        for i in range(len(results['ids'][0])):
            metadata = results['metadatas'][0][i]
            chunks.append({
                'file_path': metadata['file_path'],
                'chunk_type': metadata['chunk_type'],
                'name': metadata['name'],
                'start_line': metadata['start_line'],
                'end_line': metadata['end_line'],
                'content': results['documents'][0][i],
                'similarity': 1 - results['distances'][0][i] 
            })
        
        return chunks
    
    def get_chunk_by_location(self, file_path: str, line_number: int) -> Optional[Dict[str, Any]]:
        results = self.collection.get(
            where={"file_path": file_path}
        )
        
        for i, metadata in enumerate(results['metadatas']):
            if metadata['start_line'] <= line_number <= metadata['end_line']:
                return {
                    'file_path': metadata['file_path'],
                    'chunk_type': metadata['chunk_type'],
                    'name': metadata['name'],
                    'start_line': metadata['start_line'],
                    'end_line': metadata['end_line'],
                    'content': results['documents'][i]
                }
        
        return None