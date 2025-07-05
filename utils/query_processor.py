# query_processor.py
import os
from pathlib import Path
from typing import List, Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain.schema import HumanMessage
from .database import EmbeddingDB
from .embeddings import get_embedding
from dotenv import load_dotenv
import json
import re
from .indexer import CodebaseIndexer

load_dotenv()

llm = ChatAnthropic(
    anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
    model_name="claude-3-5-sonnet-latest",
    temperature=0.1
)

class QueryProcessor:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.db = EmbeddingDB(project_path / ".codebase_index")
    
    def process_query(self, query: str):
        print(f"Analyzing query: {query}")
        
        relevant_chunks = self._find_relevant_chunks(query)
        
        if not relevant_chunks:
            print("No relevant code found for your query.")
            return
        
        print(f"Found {len(relevant_chunks)} relevant code chunks")
        
        changes = self._generate_changes(query, relevant_chunks)
        
        self._apply_changes(changes)
    
    def _find_relevant_chunks(self, query: str) -> List[Dict[str, Any]]:
        query_embedding = get_embedding(query)
        return self.db.similarity_search(query_embedding, top_k=5)
    
    def _generate_changes(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        context = "\n".join([
            f"File: {chunk['file_path']}\n"
            f"Type: {chunk['chunk_type']}\n"
            f"Name: {chunk['name']}\n"
            f"Lines: {chunk['start_line']}-{chunk['end_line']}\n"
            f"Content:\n{chunk['content']}\n---"
            for chunk in chunks
        ])
        
        prompt = f"""
            You are a code modification assistant. Based on the user's query and the relevant code context, 
            generate specific code changes.

            User Query: {query}

            Relevant Code Context:
            {context}

            IMPORTANT INSTRUCTIONS:
            1. Make MINIMAL changes - only modify what's necessary to address the query
            2. Preserve existing imports, class/function signatures, and overall structure
            3. If adding new code, try to add it without replacing existing working code
            4. Be extremely careful with indentation and syntax
            5. Only modify the specific lines that need to change
            6. Do not rewrite entire functions unless absolutely necessary
            7. Preserve all existing functionality

            For each change, provide:
            1. file_path: The file to modify
            2. start_line: Starting line number (be very precise)
            3. end_line: Ending line number (be very precise)
            4. new_content: The new code to replace ONLY the specified lines
            5. reasoning: Why this specific change is needed

            Respond in the following JSON format:
            {{
            "changes": [
                {{
                "file_path": "path/to/file.py",
                "start_line": 10,
                "end_line": 10,
                "new_content": "    # Only the specific line(s) that need to change",
                "reasoning": "explanation of change"
                }}
            ]
            }}

            CRITICAL: Only suggest changes that directly address the user's query. Be precise with line numbers.
            Make the smallest possible changes. Do not rewrite working code.
            """
        
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                changes_data = json.loads(json_match.group())
                return changes_data.get('changes', [])
            
            print("No valid JSON found in response")
            return []
        
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error generating changes: {e}")
            return []
    
    def _apply_changes(self, changes: List[Dict[str, Any]]):
        if not changes:
            print("No changes generated.")
            return
        
        for change in changes:
            try:
                file_path = self.project_path / change['file_path']
                
                if not file_path.exists():
                    print(f"File not found: {file_path}")
                    continue
                
                print(f"Applying change to {file_path}")
                print(f"Reasoning: {change['reasoning']}")
                
                lines = file_path.read_text().splitlines()
                
                start_idx = change['start_line'] - 1
                end_idx = change['end_line'] - 1
                
                # Show code before change
                print(f"\nCode before change (lines {change['start_line']}-{change['end_line']}):")
                print("=" * 50)
                for i in range(start_idx, end_idx + 1):
                    if i < len(lines):
                        print(f"{i + 1:3d}: {lines[i]}")
                print("=" * 50)
                
                new_lines = change['new_content'].splitlines()
                
                # Show code after change
                print(f"\nCode after change:")
                print("=" * 50)
                for i, line in enumerate(new_lines, start=change['start_line']):
                    print(f"{i:3d}: {line}")
                print("=" * 50)
                
                modified_lines = lines[:start_idx] + new_lines + lines[end_idx + 1:]
                
                file_path.write_text('\n'.join(modified_lines))
                
                print(f"Successfully modified {file_path}")
                
                self._update_file_index(file_path)
                
            except Exception as e:
                print(f"Error applying change to {change['file_path']}: {e}")
    
    def _update_file_index(self, file_path: Path):
        try:
            relative_path = file_path.relative_to(self.project_path)
            
            self.db.remove_chunks_for_file(str(relative_path))
            
            indexer = CodebaseIndexer(self.project_path)
            indexer._index_file(file_path)
            
            print(f"Updated index for {file_path}")
            
        except Exception as e:
            print(f"Error updating index for {file_path}: {e}")