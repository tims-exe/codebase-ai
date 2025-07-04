import ast
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any
from .database import EmbeddingDB
from .embeddings import get_embedding

# Setup logging
logging.basicConfig(
    filename='manage.log',
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CodebaseIndexer:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.db = EmbeddingDB(project_path / ".codebase_index")
    
    def index(self):
        for file_path in self._discover_files():
            try:
                self._index_file(file_path)
                print(f"Indexed: {file_path}")
            except Exception as e:
                print(f"Error indexing {file_path}: {e}")
                logger.error(f"Error indexing {file_path}: {e}")
    
    def _discover_files(self) -> List[Path]:
        """Discover all Python files in the project"""
        files = []
        
        for file_path in self.project_path.rglob("*.py"):
            if not any(part.startswith('.') for part in file_path.parts):
                if file_path.name not in ['__pycache__']:
                    files.append(file_path)
        
        return files
    
    def _index_file(self, file_path: Path):
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    chunk = self._extract_chunk(content, node)
                    if chunk:
                        self._store_chunk(file_path, chunk)
        except SyntaxError:
            logger.error(f"Syntax error in file: {file_path}")
    
    def _extract_chunk(self, content: str, node: ast.AST) -> Dict[str, Any]:
        lines = content.splitlines()
        start_line = node.lineno - 1
        end_line = getattr(node, 'end_lineno', start_line + 1)
        
        chunk_content = '\n'.join(lines[start_line:end_line])
        chunk_hash = hashlib.md5(chunk_content.encode()).hexdigest()
        
        return {
            'content': chunk_content,
            'hash': chunk_hash,
            'start_line': start_line + 1,
            'end_line': end_line,
            'type': type(node).__name__,
            'name': getattr(node, 'name', 'unnamed')
        }
    
    def _store_chunk(self, file_path: Path, chunk: Dict[str, Any]):
        relative_path = file_path.relative_to(self.project_path)
        
        # Check if chunk already exists (by hash)
        if self.db.chunk_exists(chunk['hash']):
            return
        
        # Generate embedding for the chunk
        embedding = get_embedding(chunk['content'])
        
        # Store in database
        self.db.store_chunk(
            file_path=str(relative_path),
            chunk_hash=chunk['hash'],
            chunk_type=chunk['type'],
            name=chunk['name'],
            start_line=chunk['start_line'],
            end_line=chunk['end_line'],
            content=chunk['content'],
            embedding=embedding
        )
        
        # Log the chunk details
        logger.info(f"Stored chunk: {chunk['hash']}")
        logger.info(f"  File: {relative_path}")
        logger.info(f"  Type: {chunk['type']}")
        logger.info(f"  Name: {chunk['name']}")
        logger.info(f"  Lines: {chunk['start_line']}-{chunk['end_line']}")
        logger.info(f"  Content: \n{chunk['content'][:100]}...")
        logger.info("-" * 50)