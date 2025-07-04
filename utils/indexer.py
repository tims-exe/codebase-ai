# indexer.py
import ast
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from .database import EmbeddingDB
from .embeddings import get_embedding

class CodebaseIndexer:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.db = EmbeddingDB(project_path / ".codebase_index")
        self.supported_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h'}
    
    def index(self):
      
        for file_path in self._discover_files():
            try:
                self._index_file(file_path)
                print(f"Indexed: {file_path}")
            except Exception as e:
                print(f"Error indexing {file_path}: {e}")
    
    def _discover_files(self) -> List[Path]:
        """Discover all code files in the project"""
        files = []
        gitignore_patterns = self._load_gitignore()
        
        for root, dirs, filenames in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'node_modules', '__pycache__', 'venv', 'env'}]
            
            for filename in filenames:
                file_path = Path(root) / filename
                if (file_path.suffix in self.supported_extensions and
                    not self._should_ignore(file_path, gitignore_patterns)):
                    files.append(file_path)
        
        return files
    
    def _load_gitignore(self) -> List[str]:
        gitignore_path = self.project_path / '.gitignore'
        if gitignore_path.exists():
            return gitignore_path.read_text().splitlines()
        return []
    
    def _should_ignore(self, file_path: Path, patterns: List[str]) -> bool:
        relative_path = file_path.relative_to(self.project_path)
        return any(pattern in str(relative_path) for pattern in patterns if pattern.strip())
    
    def _index_file(self, file_path: Path):
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return
        
        if file_path.suffix == '.py':
            self._index_python_file(file_path, content)
        else:
            self._index_generic_file(file_path, content)
    
    def _index_python_file(self, file_path: Path, content: str):
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    chunk = self._extract_chunk(content, node)
                    if chunk:
                        self._store_chunk(file_path, chunk, node)
        except SyntaxError:
            self._index_generic_file(file_path, content)
    
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
    
    def _index_generic_file(self, file_path: Path, content: str):
        lines = content.splitlines()
        chunk_size = 50  # Lines per chunk
        
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            chunk_content = '\n'.join(chunk_lines)
            chunk_hash = hashlib.md5(chunk_content.encode()).hexdigest()
            
            chunk = {
                'content': chunk_content,
                'hash': chunk_hash,
                'start_line': i + 1,
                'end_line': min(i + chunk_size, len(lines)),
                'type': 'generic_chunk',
                'name': f'chunk_{i // chunk_size}'
            }
            
            self._store_chunk(file_path, chunk, None)
    
    def _store_chunk(self, file_path: Path, chunk: Dict[str, Any], node: ast.AST = None):
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