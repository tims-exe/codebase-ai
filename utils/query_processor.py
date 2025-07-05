# query_processor.py
import os
from pathlib import Path
from typing import List, Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from .database import EmbeddingDB
from .embeddings import get_embedding
from dotenv import load_dotenv
from .indexer import CodebaseIndexer

load_dotenv()

class QueryProcessor:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.db = EmbeddingDB(project_path / ".codebase_index")
        self.chat_history: List[Dict[str, str]] = []
        
        # Initialize LLM with system prompt
        self.llm = ChatAnthropic(
            anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
            model_name="claude-3-5-sonnet-latest",
            temperature=0.1
        )
        
        # System prompt - run once on initialization
        self.system_prompt = """You are a code modification assistant. Your job is to help users modify their codebase based on their queries.

IMPORTANT INSTRUCTIONS:
1. Make MINIMAL changes - only modify what's necessary to address the query
2. Preserve existing imports, class/function signatures, and overall structure
3. If adding new code, try to add it without replacing existing working code
4. Be extremely careful with indentation and syntax
5. Only modify the specific lines that need to change
6. Do not rewrite entire functions unless absolutely necessary
7. Preserve all existing functionality

For each change, provide a JSON response with:
- file_path: The file to modify
- start_line: Starting line number (be very precise)
- end_line: Ending line number (be very precise)
- new_content: The new code to replace ONLY the specified lines
- reasoning: Why this specific change is needed

Response format:
{
"changes": [
    {
    "file_path": "path/to/file.py",
    "start_line": 10,
    "end_line": 10,
    "new_content": "    # Only the specific line(s) that need to change",
    "reasoning": "explanation of change"
    }
]
}

Only suggest changes that directly address the user's query. Be precise with line numbers."""
    
    def process_query(self, query: str):
        print(f"Analyzing query: {query}")
        
        relevant_chunks = self._find_relevant_chunks(query)
        
        if not relevant_chunks:
            print("No relevant code found for your query.")
            return
        
        print(f"Found {len(relevant_chunks)} relevant code chunks")
        
        # Generate response using QA chain
        response = self._qa_chain(query, relevant_chunks)
        
        # Parse and apply changes
        changes = self._parse_changes(response)
        if changes:
            self._apply_changes(changes)
        else:
            print("No changes generated or invalid response format.")
    
    def _find_relevant_chunks(self, query: str) -> List[Dict[str, Any]]:
        query_embedding = get_embedding(query)
        return self.db.similarity_search(query_embedding, top_k=5)
    
    def _qa_chain(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        # Build context from relevant chunks
        context = "\n".join([
            f"File: {chunk['file_path']}\n"
            f"Type: {chunk['chunk_type']}\n"
            f"Name: {chunk['name']}\n"
            f"Lines: {chunk['start_line']}-{chunk['end_line']}\n"
            f"Content:\n{chunk['content']}\n---"
            for chunk in chunks
        ])
        
        # Build chat history for context
        history_context = ""
        if self.chat_history:
            history_context = "\n\nPrevious conversation:\n"
            for msg in self.chat_history[-6:]:  # Keep last 6 messages
                history_context += f"{msg['role']}: {msg['content'][:200]}...\n"
        
        # User prompt with query and code context
        user_prompt = f"""User Query: {query}

Relevant Code Context:
{context}{history_context}

Please analyze the code and provide the necessary changes to address the user's query."""
        
        # Create messages for the chain
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # Add chat history to messages
        for msg in self.chat_history[-4:]:  # Keep last 4 messages for context
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            else:
                messages.append(AIMessage(content=msg['content']))
        
        # Get response from LLM
        response = self.llm.invoke(messages)
        
        # Extract content from response
        if hasattr(response, 'content'):
            response_text = response.content
        elif isinstance(response, str):
            response_text = response
        else:
            response_text = str(response)
        
        # Update chat history
        self.chat_history.append({'role': 'user', 'content': query})
        self.chat_history.append({'role': 'assistant', 'content': response_text})
        
        return response_text
    
    def _parse_changes(self, response: str) -> List[Dict[str, Any]]:
        import json
        import re
        
        # Handle case where response might not be a string
        if not isinstance(response, str):
            print(f"Response is not a string, got type: {type(response)}")
            print(f"Response value: {response}")
            return []
        
        if not response.strip():
            print("Empty response received")
            return []
        
        try:
            # Try to find JSON block with proper brackets matching
            json_pattern = r'\{(?:[^{}]|{[^{}]*})*\}'
            json_matches = re.findall(json_pattern, response, re.DOTALL)
            
            for json_str in json_matches:
                try:
                    changes_data = json.loads(json_str)
                    if 'changes' in changes_data:
                        return changes_data['changes']
                except json.JSONDecodeError:
                    continue
            
            # Fallback: try to extract between first { and last }
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx + 1]
                changes_data = json.loads(json_str)
                return changes_data.get('changes', [])
            
            print("No valid JSON found in response")
            print(f"Raw response: {response[:500]}...")
            return []
        
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error parsing changes: {e}")
            print(f"Raw response: {response[:500]}...")
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