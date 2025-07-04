# main.py

import os
from pathlib import Path
from utils.query_processor import QueryProcessor
from dotenv import load_dotenv

load_dotenv()

def main():
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("No api key provided")
        return
    
    project_path = Path.cwd() / "calculator_project"
    
    index_path = project_path / ".codebase_index"
    if not index_path.exists():
        print("No codebase index found. Indexing...")
        from utils.indexer import CodebaseIndexer
        indexer = CodebaseIndexer(project_path)
        indexer.index()
        print("Indexing complete")
    
    print("Codebase-ai")
    print("Type 'quit' or 'exit' to stop\n")
    
    processor = QueryProcessor(project_path)
    
    while True:
        try:
            query = input("Query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("Exiting.....")
                break
            
            if not query:
                continue
            
            print(f"\nProcessing: {query}")
            processor.process_query(query)
            print("Done!\n")
            
        except KeyboardInterrupt:
            print("Exiting.....")
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()
