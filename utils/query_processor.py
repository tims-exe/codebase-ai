# query_processor.py
import os
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain.schema import SystemMessage, HumanMessage
from .database import EmbeddingDB
from .embeddings import get_embedding
from .indexer import CodebaseIndexer
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class QueryProcessor:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.db = EmbeddingDB(project_path / ".codebase_index")
        self.llm = ChatAnthropic(
            anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
            model_name="claude-3-5-sonnet-latest",
            temperature=0.1
        )
        self.chat_history = []
        
    def process_query(self, query: str):
        """Main entry point for processing user queries"""
        print(f"Analyzing query: {query}")
        
        # Find relevant code chunks
        relevant_chunks = self._find_relevant_chunks(query)
        if not relevant_chunks:
            print("No relevant code found for your query.")
            return
        
        print(f"Found {len(relevant_chunks)} relevant code chunks")
        
        # Generate and apply changes
        response = self._generate_response(query, relevant_chunks)
        changes = self._parse_changes(response)
        
        if changes:
            self._apply_changes(changes)
        else:
            print("No changes generated or invalid response format.")
    
    def _find_relevant_chunks(self, query: str) -> List[Dict[str, Any]]:
        """Find code chunks relevant to the query"""
        query_embedding = get_embedding(query)
        return self.db.similarity_search(query_embedding, top_k=5)
    
    def _generate_response(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """Generate LLM response with code context"""
        context = self._build_context(chunks)
        user_prompt = f"""User Query: {query}

Relevant Code Context:
{context}

Please analyze the code and provide the necessary changes to address the user's query."""
        
        messages = [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            response_text = self._extract_response_text(response)
            
            # Log the full LLM response for debugging
            logger.info(f"LLM Response for query '{query[:50]}...':")
            logger.info(f"Full response: {response_text}")
            logger.info("-" * 80)
            
            # Update chat history
            self.chat_history.extend([
                {'role': 'user', 'content': query},
                {'role': 'assistant', 'content': response_text}
            ])
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error in LLM invoke: {e}")
            print(f"Error in LLM invoke: {e}")
            return ""
    
    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build code context from relevant chunks"""
        context_parts = []
        for chunk in chunks:
            context_parts.append(
                f"File: {chunk['file_path']}\n"
                f"Type: {chunk['chunk_type']}\n"
                f"Name: {chunk['name']}\n"
                f"Lines: {chunk['start_line']}-{chunk['end_line']}\n"
                f"Content:\n{chunk['content']}\n---"
            )
        return "\n".join(context_parts)
    
    def _extract_response_text(self, response) -> str:
        """Extract text content from LLM response"""
        if hasattr(response, 'content'):
            return response.content
        elif hasattr(response, 'text'):
            return response.text
        elif isinstance(response, str):
            return response
        else:
            return str(response)
    
    def _parse_changes(self, response: str) -> List[Dict[str, Any]]:
        """Parse JSON changes from LLM response"""
        if not response or not isinstance(response, str):
            return []
        
        try:
            # Find the JSON block that contains "changes" with different formatting
            patterns = [
                '{\n  "changes"',  # spaced formatting
                '{\n"changes"',    # no space formatting
                '{"changes"'       # inline formatting
            ]
            
            start_idx = -1
            for pattern in patterns:
                start_idx = response.find(pattern)
                if start_idx != -1:
                    break
            
            if start_idx != -1:
                # Count braces to find the end of the JSON object
                brace_count = 0
                end_idx = start_idx
                for i, char in enumerate(response[start_idx:]):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = start_idx + i + 1
                            break
                
                json_str = response[start_idx:end_idx]
                changes_data = json.loads(json_str)
                return changes_data.get('changes', [])
            
            return []
        
        except Exception as e:
            print(f"Error parsing changes: {e}")
            return []
    
    def _apply_changes(self, changes: List[Dict[str, Any]]):
        """Apply code changes to files"""
        if not changes:
            return
        
        # Show changes and ask for confirmation
        if not self._show_changes_and_confirm(changes):
            print("Changes cancelled by user.")
            return
        
        for change in changes:
            try:
                file_path = self.project_path / change['file_path']
                
                if not file_path.exists():
                    print(f"File not found: {file_path}")
                    continue
                
                self._apply_single_change(file_path, change)
                self._update_file_index(file_path)
                
            except Exception as e:
                print(f"Error applying change to {change['file_path']}: {e}")
    
    def _show_changes_and_confirm(self, changes: List[Dict[str, Any]]) -> bool:
        """Show proposed changes to user and ask for confirmation"""
        print("\n" + "="*60)
        print("PROPOSED CHANGES")
        print("="*60)
        
        for i, change in enumerate(changes, 1):
            print(f"\nChange {i}:")
            print(f"File: {change['file_path']}")
            print(f"Lines: {change['start_line']}-{change['end_line']}")
            print(f"Reasoning: {change['reasoning']}")
            
            # Show current code
            file_path = self.project_path / change['file_path']
            if file_path.exists():
                try:
                    lines = file_path.read_text().splitlines()
                    start_idx = change['start_line'] - 1
                    end_idx = change['end_line'] - 1
                    
                    print(f"\nCurrent code:")
                    print("-" * 40)
                    for line_num in range(start_idx, min(end_idx + 1, len(lines))):
                        print(f"{line_num + 1:3d}: {lines[line_num]}")
                    print("-" * 40)
                    
                    print(f"\nNew code:")
                    print("-" * 40)
                    new_lines = change['new_content'].splitlines()
                    for line_num, line in enumerate(new_lines, start=change['start_line']):
                        print(f"{line_num:3d}: {line}")
                    print("-" * 40)
                    
                except Exception as e:
                    print(f"Error reading file: {e}")
            else:
                print(f"Warning: File {change['file_path']} not found!")
        
        print("\n" + "="*60)
        
        # Ask for confirmation
        while True:
            response = input("\nDo you want to apply these changes? (y/n): ").strip().lower()
            
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    
    def _apply_single_change(self, file_path: Path, change: Dict[str, Any]):
        """Apply a single change to a file"""
        print(f"Applying change to {file_path}")
        print(f"Reasoning: {change['reasoning']}")
        
        lines = file_path.read_text().splitlines()
        start_idx = change['start_line'] - 1
        end_idx = change['end_line'] - 1
        
        # Show before/after
        self._show_change_preview(lines, change, start_idx, end_idx)
        
        # Apply change
        new_lines = change['new_content'].splitlines()
        modified_lines = lines[:start_idx] + new_lines + lines[end_idx + 1:]
        file_path.write_text('\n'.join(modified_lines))
        
        print(f"Successfully modified {file_path}")
    
    def _show_change_preview(self, lines: List[str], change: Dict[str, Any], start_idx: int, end_idx: int):
        """Show before/after preview of changes"""
        print(f"\nCode before change (lines {change['start_line']}-{change['end_line']}):")
        print("=" * 50)
        for i in range(start_idx, end_idx + 1):
            if i < len(lines):
                print(f"{i + 1:3d}: {lines[i]}")
        
        print(f"\nCode after change:")
        print("=" * 50)
        for i, line in enumerate(change['new_content'].splitlines(), start=change['start_line']):
            print(f"{i:3d}: {line}")
        print("=" * 50)
    
    def _update_file_index(self, file_path: Path):
        """Update the search index for a modified file"""
        try:
            relative_path = file_path.relative_to(self.project_path)
            self.db.remove_chunks_for_file(str(relative_path))
            
            indexer = CodebaseIndexer(self.project_path)
            indexer._index_file(file_path)
            
            print(f"Updated index for {file_path}")
            
        except Exception as e:
            print(f"Error updating index for {file_path}: {e}")
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the LLM"""
        return """You are a code modification assistant. Your job is to help users modify their codebase based on their queries.

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