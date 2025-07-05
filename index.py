# index.py

import os
from pathlib import Path
from utils.indexer import CodebaseIndexer
from dotenv import load_dotenv

load_dotenv()


def main():
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("No api key provided")
        return
    
    project_path = Path.cwd() / "express-server"
    
    print(f"Indexing codebase in: {project_path}.....")
    
    indexer = CodebaseIndexer(project_path)
    indexer.index()
    
    print("Indexing complete")

if __name__ == "__main__":
    main()


