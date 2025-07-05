# indexer.py
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any
from tree_sitter_language_pack import get_parser
from tree_sitter import Node
from .database import EmbeddingDB
from .embeddings import get_embedding

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
        files = []
        for ext in ["*.py", "*.js"]:
            files.extend([f for f in self.project_path.rglob(ext) 
                         if not any(part.startswith('.') for part in f.parts)])
        return files
    
    def _index_file(self, file_path: Path):
        with open(file_path, 'rb') as f:
            source_code = f.read()
        
        if file_path.suffix == '.py':
            parser = get_parser('python')
            node_types = {
                'imports': ['import_statement', 'import_from_statement'],
                'functions': ['function_definition', 'async_function_definition'],
                'classes': ['class_definition'],
                'decorated': ['decorated_definition']
            }
        elif file_path.suffix == '.js':
            parser = get_parser('javascript')
            node_types = {
                'imports': ['import_statement', 'import_declaration'],
                'functions': ['function_declaration', 'function_expression', 'arrow_function'],
                'classes': ['class_declaration'],
                'decorated': []
            }
        else:
            return
        
        tree = parser.parse(source_code)
        processed_lines = set()
        
        imports = self._collect_nodes(tree.root_node, node_types['imports'])
        if imports:
            self._process_node_group(file_path, source_code, imports, 'Import', 'imports', processed_lines)
        
        self._walk_tree(tree.root_node, file_path, source_code, node_types, processed_lines)
        
        lines = source_code.decode('utf-8').split('\n')
        self._process_remaining_lines(file_path, lines, processed_lines)
    
    def _collect_nodes(self, node: Node, node_types: List[str]) -> List[Node]:
        nodes = []
        if node.type in node_types:
            nodes.append(node)
        for child in node.children:
            nodes.extend(self._collect_nodes(child, node_types))
        return nodes
    
    def _process_node_group(self, file_path: Path, source_code: bytes, nodes: List[Node], 
                           chunk_type: str, name: str, processed_lines: set):
        if not nodes:
            return
        
        start_line = min(n.start_point[0] for n in nodes)
        end_line = max(n.end_point[0] for n in nodes)
        start_byte = min(n.start_byte for n in nodes)
        end_byte = max(n.end_byte for n in nodes)
        
        content = source_code[start_byte:end_byte].decode('utf-8')
        
        self._store_chunk(file_path, content, chunk_type, name, start_line + 1, end_line + 1)
        
        for line_num in range(start_line, end_line + 1):
            processed_lines.add(line_num + 1)
    
    def _walk_tree(self, node: Node, file_path: Path, source_code: bytes, 
                  node_types: Dict[str, List[str]], processed_lines: set):
        if node.type in node_types['decorated']:
            self._process_decorated(node, file_path, source_code, processed_lines)
        elif node.type in node_types['functions']:
            self._process_single_node(file_path, source_code, node, 'FunctionDef', processed_lines)
        elif node.type in node_types['classes']:
            self._process_single_node(file_path, source_code, node, 'ClassDef', processed_lines)
        elif node.type == 'assignment':
            self._process_single_node(file_path, source_code, node, 'Statement', processed_lines)
        
        for child in node.children:
            self._walk_tree(child, file_path, source_code, node_types, processed_lines)
    
    def _process_decorated(self, node: Node, file_path: Path, source_code: bytes, processed_lines: set):
        if node.start_point[0] + 1 in processed_lines:
            return
        
        func_node = next((child for child in node.children 
                         if child.type in ['function_definition', 'async_function_definition', 'class_definition']), None)
        
        if func_node:
            content = source_code[node.start_byte:node.end_byte].decode('utf-8')
            name = self._get_node_name(func_node, source_code)
            chunk_type = 'FunctionDef' if func_node.type in ['function_definition', 'async_function_definition'] else 'ClassDef'
            
            self._store_chunk(file_path, content, chunk_type, name, 
                            node.start_point[0] + 1, node.end_point[0] + 1)
            
            for line_num in range(node.start_point[0], node.end_point[0] + 1):
                processed_lines.add(line_num + 1)
    
    def _process_single_node(self, file_path: Path, source_code: bytes, node: Node, 
                           chunk_type: str, processed_lines: set):
        if node.start_point[0] + 1 in processed_lines:
            return
        
        content = source_code[node.start_byte:node.end_byte].decode('utf-8')
        name = self._get_node_name(node, source_code) if chunk_type in ['FunctionDef', 'ClassDef'] else 'code_block'
        
        self._store_chunk(file_path, content, chunk_type, name, 
                        node.start_point[0] + 1, node.end_point[0] + 1)
        
        for line_num in range(node.start_point[0], node.end_point[0] + 1):
            processed_lines.add(line_num + 1)
    
    def _get_node_name(self, node: Node, source_code: bytes) -> str:
        for child in node.children:
            if child.type == 'identifier':
                return source_code[child.start_byte:child.end_byte].decode('utf-8')
        return ""
    
    def _process_remaining_lines(self, file_path: Path, lines: List[str], processed_lines: set):
        chunk_lines = []
        start_line = None
        
        for i, line in enumerate(lines, 1):
            if i not in processed_lines:
                if not chunk_lines and (not line.strip() or line.strip().startswith('#')):
                    continue
                
                if not chunk_lines:
                    start_line = i
                chunk_lines.append(line)
                
                if not line.strip() or i == len(lines):
                    if chunk_lines and any(l.strip() for l in chunk_lines):
                        content = '\n'.join(chunk_lines).strip()
                        self._store_chunk(file_path, content, 'Statement', 'code_block', 
                                        start_line, start_line + len(chunk_lines) - 1)
                    chunk_lines = []
                    start_line = None
    
    def _store_chunk(self, file_path: Path, content: str, chunk_type: str, name: str, 
                    start_line: int, end_line: int):
        chunk_hash = hashlib.md5(content.encode()).hexdigest()
        
        if self.db.chunk_exists(chunk_hash):
            return
        
        relative_path = file_path.relative_to(self.project_path)
        embedding = get_embedding(content)
        
        self.db.store_chunk(
            file_path=str(relative_path),
            chunk_hash=chunk_hash,
            chunk_type=chunk_type,
            name=name,
            start_line=start_line,
            end_line=end_line,
            content=content,
            embedding=embedding
        )
        
        logger.info(f"Stored chunk: {chunk_hash}")
        logger.info(f"  File: {relative_path}")
        logger.info(f"  Type: {chunk_type}")
        logger.info(f"  Name: {name}")
        logger.info(f"  Lines: {start_line}-{end_line}")
        logger.info(f"  Content: \n{content[:100]}...")
        logger.info("-" * 50)