# Codebase AI

An intelligent code analysis and modification tool that uses Large Language Models to understand your codebase and automatically implement changes based on natural language queries.

## Features

- **Interactive Project Selection**: Choose any project directory to analyze and modify
- **Intelligent Code Analysis**: Automatically indexes and understands your codebase structure using AST parsing
- **Natural Language Queries**: Ask questions about your code or request modifications in plain English
- **Smart Re-indexing**: Detects if you've made recent changes and offers to re-index accordingly
- **Change Preview & Confirmation**: Shows exactly what changes will be made before applying them
- **Safe Modifications**: Creates backups before making changes and validates line numbers
- **Semantic Search**: Find relevant code sections using vector embeddings
- **Multi-language Support**: Currently supports Python and JavaScript files
- **Minimal Changes**: Makes only necessary modifications while preserving existing functionality

## How It Works

1. **Project Selection**: Choose your project directory interactively
2. **Smart Indexing**: The tool analyzes your codebase and creates semantic embeddings of code chunks (functions, classes, imports, etc.)
3. **Query Processing**: When you ask a question, it finds the most relevant code sections using similarity search
4. **Change Generation**: Uses Claude AI to generate precise, minimal code modifications
5. **User Confirmation**: Shows you exactly what changes will be made before applying them
6. **Safe Application**: Creates backups, applies changes, and updates the search index

## Dependencies

- `anthropic` - For Claude AI integration
- `langchain-anthropic` - LangChain integration with Anthropic
- `langchain-huggingface` - For local embeddings generation
- `chromadb` - Vector database for code embeddings
- `tree-sitter` - For parsing code syntax trees
- `tree-sitter-language-pack` - Language parsers for Python and JavaScript
- `python-dotenv` - For environment variable management

## Usage

1. **Run the tool**:
```bash
python main.py
```

2. **Select your project**: The tool will prompt you to enter the path to your project directory
   - Enter a relative path from the current directory (e.g., `calculator_project` or `../other-project`)
   - The tool validates that the path exists and contains Python or JavaScript files

3. **Handle indexing**: 
   - If it's your first time: The tool will automatically index your codebase
   - If an index exists: You'll be asked if you've made recent changes
     - Say "yes" to re-index with your latest changes
     - Say "no" to use the existing index

4. **Query interface**: Ask questions in natural language:
   - "Add error handling to the user authentication function"
   - "Fix the SQL injection vulnerability in the database query"
   - "Add logging to all API endpoints"
   - "Optimize the slow database query in the user service"
   - "Add input validation to the login endpoint"

5. **Review and confirm**: The tool will show you:
   - Which files will be modified
   - The exact lines that will change
   - A before/after comparison
   - The reasoning behind each change

6. **Apply changes**: Choose whether to proceed with the modifications

## Example Session

```
=== Codebase AI ===
This tool helps you modify your codebase using AI.

Enter the project folder path (relative to current directory): my-web-app
Selected project path: /home/user/my-web-app

Found existing codebase index at: /home/user/my-web-app/.codebase_index
Have you made any changes to the code recently? (y/n): n
Using existing index.

==================================================
Codebase AI is ready!
Type your queries to modify the codebase.
Type 'quit', 'exit', or 'q' to stop
==================================================

Query: Add input validation to the login function
Analyzing query: Add input validation to the login function
Found 3 relevant code chunks

============================================================
PROPOSED CHANGES
============================================================

Change 1:
File: auth/login.py
Lines: 15-20
Reasoning: Added input validation to prevent empty username/password

Current code:
----------------------------------------
15: def login(username, password):
16:     user = authenticate_user(username, password)
17:     if user:
18:         return create_session(user)
19:     return None
----------------------------------------

New code:
----------------------------------------
15: def login(username, password):
16:     if not username or not password:
17:         raise ValueError("Username and password are required")
18:     user = authenticate_user(username, password)
19:     if user:
20:         return create_session(user)
21:     return None
----------------------------------------

============================================================

Do you want to apply these changes? (y/n): y

Applying changes...

Applying change 1/1 to /home/user/my-web-app/auth/login.py
✓ Successfully modified /home/user/my-web-app/auth/login.py

✓ All changes applied successfully!
Done!
```

## Configuration

### LLM Configuration
The tool uses Claude 3.5 Sonnet by default. You can modify the model in `query_processor.py`:
```python
llm = ChatAnthropic(
    anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
    model_name="claude-3-5-sonnet-latest",  # Change this line
    temperature=0.1
)
```

### Supported File Types
Currently supports:
- Python files (`.py`)
- JavaScript files (`.js`)

To add more file types, modify the `_discover_files` method in `indexer.py`.

### Index Management
- Index files are stored in a `.codebase_index` directory within your project
- The tool automatically detects when you've made changes and offers to re-index
- You can manually delete the `.codebase_index` directory to force a complete re-index

## Architecture

### Core Components

- **`main.py`**: Entry point and command-line interface
- **`indexer.py`**: Analyzes and indexes code files using Tree-sitter
- **`query_processor.py`**: Handles user queries and generates code changes
- **`database.py`**: Manages vector embeddings using ChromaDB
- **`embeddings.py`**: Generates semantic embeddings for code chunks

### Data Flow

1. **Indexing Phase**: Code files → Tree-sitter parser → Code chunks → Embeddings → ChromaDB
2. **Query Phase**: User query → Embedding → Similarity search → Relevant chunks → LLM → Code changes → File updates

## Best Practices

1. **Use version control** - Always commit your changes before running the tool
2. **Start with small changes** - Test the tool with simple modifications first
3. **Review changes carefully** - Always examine the proposed changes before accepting
4. **Be specific in queries** - Clear, detailed requests yield better results
5. **Test after changes** - Run your tests after modifications to ensure everything works
6. **Keep backups** - The tool creates automatic backups, but version control is still recommended