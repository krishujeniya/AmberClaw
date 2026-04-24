from typing import Type, List, Optional
from pydantic import BaseModel, Field
from amberclaw.agent.tools.base import PydanticTool
from amberclaw.agent.memory.knowledge import KnowledgeStore
from amberclaw.config.loader import load_config

class KnowledgeSearchInput(BaseModel):
    query: str = Field(..., description="The search query to find relevant knowledge.")
    limit: int = Field(5, description="Maximum number of results to return.")

class KnowledgeSearchTool(PydanticTool):
    name: str = "knowledge_search"
    description: str = "Search the local knowledge base for relevant information, snippets, or past decisions."
    args_schema: Type[BaseModel] = KnowledgeSearchInput

    def _execute(self, query: str, limit: int = 5) -> str:
        config = load_config()
        store = KnowledgeStore(config.tools.knowledge.db_path)
        results = store.search(query, limit)
        
        if not results:
            return "No matching knowledge found."
            
        output = []
        for res in results:
            output.append(f"[{res.category}] {res.content}")
        
        return "\n---\n".join(output)

class KnowledgeAddInput(BaseModel):
    category: str = Field(..., description="Category for the knowledge (e.g., 'code_pattern', 'decision').")
    content: str = Field(..., description="The knowledge content to store.")
    tags: List[str] = Field(default_factory=list, description="Optional tags for better retrieval.")

class KnowledgeAddTool(PydanticTool):
    name: str = "knowledge_add"
    description: str = "Add a new piece of knowledge to the long-term knowledge base."
    args_schema: Type[BaseModel] = KnowledgeAddInput

    def _execute(self, category: str, content: str, tags: List[str] = []) -> str:
        config = load_config()
        store = KnowledgeStore(config.tools.knowledge.db_path)
        metadata = {"tags": tags}
        entry_id = store.add(category, content, metadata)
        return f"Knowledge stored successfully with ID: {entry_id}"
