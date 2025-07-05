# main.py

import os
import shutil
from pathlib import Path
from utils.query_processor import QueryProcessor
from dotenv import load_dotenv
from utils.indexer import CodebaseIndexer

load_dotenv()

def get_project_path():
    """Get project path from user input"""
    while True:
        project_input = input("Enter the project folder path (relative to current directory): ").strip()
        
        if not project_input:
            print("Please enter a valid path.")
            continue
        
        project_path = Path.cwd() / project_input
        
        if not project_path.exists():
            print(f"Path '{project_path}' does not exist. Please try again.")
            continue
        
        if not project_path.is_dir():
            print(f"Path '{project_path}' is not a directory. Please try again.")
            continue
        
        # Check if there are any Python or JavaScript files
        has_files = any(project_path.rglob("*.py")) or any(project_path.rglob("*.js"))
        if not has_files:
            print(f"No Python or JavaScript files found in '{project_path}'. Please check the path.")
            continue
        
        return project_path

def check_for_recent_changes(project_path):
    """Ask user if they've made recent changes and handle re-indexing"""
    index_path = project_path / ".codebase_index"
    
    if index_path.exists():
        print(f"\nFound existing codebase index at: {index_path}")
        
        while True:
            response = input("Have you made any changes to the code recently? (y/n): ").strip().lower()
            
            if response in ['y', 'yes']:
                print("Removing old index and re-indexing codebase...")
                try:
                    shutil.rmtree(index_path)
                    print("Old index removed successfully.")
                except Exception as e:
                    print(f"Error removing old index: {e}")
                return True  # Need to re-index
            
            elif response in ['n', 'no']:
                print("Using existing index.")
                return False  # Don't need to re-index
            
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    
    return True  # No existing index, need to create one

def main():
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("No API key provided. Please set ANTHROPIC_API_KEY in your .env file.")
        return
    
    print("=== Codebase AI ===")
    print("This tool helps you modify your codebase using AI.\n")
    
    # Get project path from user
    project_path = get_project_path()
    print(f"Selected project path: {project_path}")
    
    # Check for recent changes and handle indexing
    need_indexing = check_for_recent_changes(project_path)
    
    if need_indexing:
        print("\nIndexing codebase...")
        indexer = CodebaseIndexer(project_path)
        indexer.index()
        print("Indexing complete!")
    
    print("\n" + "="*50)
    print("Codebase AI is ready!")
    print("Type your queries to modify the codebase.")
    print("Type 'quit', 'exit', or 'q' to stop")
    print("="*50 + "\n")
    
    processor = QueryProcessor(project_path)
    
    while True:
        try:
            query = input("Query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("Exiting...")
                break
            
            if not query:
                continue
            
            print(f"\nProcessing: {query}")
            processor.process_query(query)
            print("Done!\n")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()