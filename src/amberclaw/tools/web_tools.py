"""
AmberClaw Web & Search Tools
"""
import httpx
import re
import html
from typing import Optional, Literal
from pydantic import BaseModel, Field
from amberclaw.tools.registry import BaseTool
from amberclaw.config.schema import settings


class WebSearchArgs(BaseModel):
    query: str = Field(..., description="Search query")
    count: int = Field(default=5, ge=1, le=10, description="Number of results")


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web and return snippets and URLs."
    args_schema = WebSearchArgs

    async def run(self, query: str, count: int = 5) -> str:
        # For production, we'd use Tavily/Brave API keys from settings
        # Here we simulate or use a mock for now if no keys are found
        api_key = settings.providers.extra.get("tavily_api_key")
        if not api_key:
            return f"Error: TAVILY_API_KEY not configured. Simulated search for: {query}"

        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": api_key, "query": query, "max_results": count},
                    timeout=10.0,
                )
                r.raise_for_status()
                results = r.json().get("results", [])
                
                if not results:
                    return f"No results found for: {query}"
                
                output = [f"Search results for: {query}\n"]
                for i, res in enumerate(results, 1):
                    output.append(f"{i}. {res['title']}\n   URL: {res['url']}\n   {res['content']}\n")
                return "\n".join(output)
        except Exception as e:
            return f"Search error: {str(e)}"


class WebFetchArgs(BaseModel):
    url: str = Field(..., description="URL to fetch")


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "Fetch and extract clean text from a URL."
    args_schema = WebFetchArgs

    async def run(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                r = await client.get(url, headers={"User-Agent": "AmberClaw/2026"})
                r.raise_for_status()
                
                # Simple HTML to text extraction (can be improved with readability)
                text = r.text
                text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
                text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
                text = re.sub(r"<[^>]+>", "", text)
                text = html.unescape(text).strip()
                text = re.sub(r"\n{3,}", "\n\n", text)
                
                if len(text) > 10000:
                    text = text[:10000] + "\n\n... (content truncated)"
                
                return f"Fetched content from {url}:\n\n{text}"
        except Exception as e:
            return f"Fetch error: {str(e)}"
