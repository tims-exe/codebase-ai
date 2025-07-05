import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any
from tree_sitter_language_pack import get_language, get_parser
from tree_sitter import Node
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
            import_types = ['import_statement', 'import_from_statement']
            function_types = ['function_definition', 'async_function_definition']
            class_types = ['class_definition']
            decorated_types = ['decorated_definition'] 
        elif file_path.suffix == '.js':
            parser = get_parser('javascript')
            import_types = ['import_statement', 'import_declaration']
            function_types = ['function_declaration', 'function_expression', 'arrow_function']
            class_types = ['class_declaration']
            decorated_types = []
        else:
            return
        
        tree = parser.parse(source_code)
        
        processed_lines = set()
        
        imports = []
        
        def collect_imports(node: Node):
            if node.type in import_types:
                imports.append(node)
            for child in node.children:
                collect_imports(child)
        
        collect_imports(tree.root_node)
        
        if imports:
            start_line = min(n.start_point[0] for n in imports)
            end_line = max(n.end_point[0] for n in imports)
            start_byte = min(n.start_byte for n in imports)
            end_byte = max(n.end_byte for n in imports)
            
            content = source_code[start_byte:end_byte].decode('utf-8')
            chunk = {
                'content': content,
                'hash': hashlib.md5(content.encode()).hexdigest(),
                'start_line': start_line + 1,
                'end_line': end_line + 1,
                'type': 'Import',
                'name': 'imports'
            }
            
            self._store_chunk(file_path, chunk)
            
            for line_num in range(start_line, end_line + 1):
                processed_lines.add(line_num + 1)
        
        def walk_tree(node: Node):
            if node.type in decorated_types:
                self._process_decorated(node, file_path, source_code, processed_lines)
            elif node.type in function_types:
                self._process_node(file_path, source_code, node, 'FunctionDef', processed_lines)
            elif node.type in class_types:
                self._process_node(file_path, source_code, node, 'ClassDef', processed_lines)
            elif node.type == 'assignment':
                self._process_node(file_path, source_code, node, 'Statement', processed_lines)
            
            for child in node.children:
                walk_tree(child)
        
        walk_tree(tree.root_node)
        
        lines = source_code.decode('utf-8').split('\n')
        self._process_remaining_lines(file_path, lines, processed_lines)
    
    def _process_decorated(self, node: Node, file_path: Path, source_code: bytes, processed_lines: set):
        if node.start_point[0] in processed_lines:
            return
        
        func_node = None
        for child in node.children:
            if child.type in ['function_definition', 'async_function_definition', 'class_definition']:
                func_node = child
                break
        
        if not func_node:
            return
        
        # Extract the entire decorated definition (decorators + function/class)
        content = source_code[node.start_byte:node.end_byte].decode('utf-8')
        name = self._get_node_name(func_node, source_code)
        
        # Determine chunk type based on what's being decorated
        chunk_type = 'FunctionDef' if func_node.type in ['function_definition', 'async_function_definition'] else 'ClassDef'
        
        chunk = {
            'content': content,
            'hash': hashlib.md5(content.encode()).hexdigest(),
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
            'type': chunk_type,
            'name': name
        }
        
        self._store_chunk(file_path, chunk)
        
        # Mark lines as processed
        for line_num in range(node.start_point[0], node.end_point[0] + 1):
            processed_lines.add(line_num + 1)
    
    def _process_node(self, file_path: Path, source_code: bytes, node: Node, chunk_type: str, processed_lines: set):
        if node.start_point[0] in processed_lines:
            return
        
        content = source_code[node.start_byte:node.end_byte].decode('utf-8')
        name = self._get_node_name(node, source_code) if chunk_type in ['FunctionDef', 'ClassDef'] else 'imports'
        
        chunk = {
            'content': content,
            'hash': hashlib.md5(content.encode()).hexdigest(),
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
            'type': chunk_type,
            'name': name
        }
        
        self._store_chunk(file_path, chunk)
        
        # Mark lines as processed
        for line_num in range(node.start_point[0], node.end_point[0] + 1):
            processed_lines.add(line_num + 1)
    
    def _get_node_name(self, node: Node, source_code: bytes) -> str:
        # Get name from function/class definition
        for child in node.children:
            if child.type == 'identifier':
                return source_code[child.start_byte:child.end_byte].decode('utf-8')
        return ""
    
    def _process_remaining_lines(self, file_path: Path, lines: List[str], processed_lines: set):
        """Process remaining lines as simple statement chunks"""
        chunk_lines = []
        start_line = None
        
        for i, line in enumerate(lines, 1):
            if i not in processed_lines:
                if not chunk_lines and (not line.strip() or line.strip().startswith('#')):
                    continue
                
                if not chunk_lines:
                    start_line = i
                chunk_lines.append(line)
                
                # End chunk on empty line or end of file
                if not line.strip() or i == len(lines):
                    if chunk_lines and any(l.strip() for l in chunk_lines):
                        content = '\n'.join(chunk_lines).strip()
                        chunk = {
                            'content': content,
                            'hash': hashlib.md5(content.encode()).hexdigest(),
                            'start_line': start_line,
                            'end_line': start_line + len(chunk_lines) - 1,
                            'type': 'Statement',
                            'name': 'code_block'
                        }
                        self._store_chunk(file_path, chunk)
                    chunk_lines = []
                    start_line = None
    
    def _store_chunk(self, file_path: Path, chunk: Dict[str, Any]):
        """Store chunk if it doesn't already exist"""
        if self.db.chunk_exists(chunk['hash']):
            return
        
        relative_path = file_path.relative_to(self.project_path)
        embedding = get_embedding(chunk['content'])
        
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
        
        logger.info(f"Stored chunk: {chunk['hash']}")
        logger.info(f"  File: {relative_path}")
        logger.info(f"  Type: {chunk['type']}")
        logger.info(f"  Name: {chunk['name']}")
        logger.info(f"  Lines: {chunk['start_line']}-{chunk['end_line']}")
        logger.info(f"  Content: \n{chunk['content'][:100]}...")
        logger.info("-" * 50)