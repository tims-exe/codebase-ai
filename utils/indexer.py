import hashlib
import logging
from pathlib import Path
from typing import Dict, Any
from .database import EmbeddingDB
from .embeddings import get_embedding
import cocoindex

# Logging setup
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
        self.flow = self._make_flow()
        self.flow.setup()  # initialize once

    def _make_flow(self):
        @cocoindex.flow_def(name="CodeChunking")
        def chunk_flow(flow_builder: cocoindex.FlowBuilder, scope: cocoindex.DataScope):
            scope["files"] = flow_builder.add_source(
                cocoindex.sources.LocalFile(
                    path=str(self.project_path),
                    included_patterns=["*.py", "*.js", "*.jsx", "*.ts", "*.tsx"]
                )
            )
            collector = scope.add_collector()
            with scope["files"].row() as file:
                file["chunks"] = file["content"].transform(
                    cocoindex.functions.SplitRecursively(),
                    language=file["filename"].split('.')[-1],
                    chunk_size=1000,
                    chunk_overlap=100
                )
                with file["chunks"].row() as chunk:
                    collector.collect(
                        filename=file["filename"],
                        content=chunk["text"],
                        start_line=chunk["location"]["start_line"],
                        end_line=chunk["location"]["end_line"],
                        node_type=chunk["node_type"]
                    )
            # export optional if needed using collector.export(...)
            return collector

        return chunk_flow

    def index(self):
        stats = self.flow.update()  # run the pipeline
        for chunk in stats.raw_data:
            self._process_and_store_chunk(chunk)
        flow = self.flow
        # Prepare backend tables/collections
        flow.setup(report_to_stdout=True)
        # Run the flow incrementally
        stats = flow.update()
        print(f"Flow stats: {stats}")
        # Process retrieved chunks
        chunks = stats.raw_data
        for chunk in chunks:
            self._process_and_store_chunk(chunk)

    def _process_and_store_chunk(self, chunk_data: Dict[str, Any]):
        file_path = Path(chunk_data["filename"])
        content = chunk_data["content"]
        chunk_hash = hashlib.md5(content.encode()).hexdigest()

        if self.db.chunk_exists(chunk_hash):
            return

        name = self._extract_name(content, chunk_data.get("node_type", ""))
        embedding = get_embedding(content)
        relative = file_path.relative_to(self.project_path)

        self.db.store_chunk(
            file_path=str(relative),
            chunk_hash=chunk_hash,
            chunk_type=chunk_data.get("node_type", "code_block"),
            name=name,
            start_line=chunk_data["start_line"],
            end_line=chunk_data["end_line"],
            content=content,
            embedding=embedding
        )
        logger.info(f"Indexed chunk {chunk_hash} in {relative} lines {chunk_data['start_line']}-{chunk_data['end_line']}")

    def _extract_name(self, content: str, node_type: str) -> str:
        first = content.strip().split("\n", 1)[0].strip()
        if first.startswith("def "):
            return first.split("def ", 1)[1].split("(", 1)[0].strip()
        if first.startswith("class "):
            return first.split("class ", 1)[1].split("(", 1)[0].rstrip(":").strip()
        if first.startswith("function "):
            return first.split("function ", 1)[1].split("(", 1)[0].strip()
        return "unnamed"
