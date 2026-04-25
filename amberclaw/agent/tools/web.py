"""Web tools: web_search and web_fetch."""

import html
import json
import os
import re
from typing import Optional, Literal
from urllib.parse import urlparse

import httpx
from loguru import logger
from pydantic import BaseModel, Field, AliasChoices

from amberclaw.agent.tools.base import PydanticTool

# Shared constants
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
MAX_REDIRECTS = 5  # Limit redirects to prevent DoS attacks


def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _validate_url(url: str) -> tuple[bool, str]:
    """Validate URL: must be http(s) with valid domain and no local IPs (SSRF protection)."""
    import ipaddress

    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        if not p.netloc:
            return False, "Missing domain"

        # SSRF protection: block local/private networks
        hostname = p.hostname or ""
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_unspecified:
                return False, f"Access to private/local IP {hostname} is blocked"
        except ValueError:
            # Not an IP address, could be a domain.
            # In a real production system, you'd resolve it and check the IP.
            # But for this fix, we block known local strings.
            if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0"):
                return False, f"Access to {hostname} is blocked"

        return True, ""
    except Exception as e:
        return False, str(e)


class WebSearchArgs(BaseModel):
    """Arguments for the web_search tool."""

    query: str = Field(..., description="Search query")
    count: Optional[int] = Field(None, description="Results (1-10)", ge=1, le=10)


class WebSearchTool(PydanticTool):
    """Search the web using Brave Search API."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web. Returns titles, URLs, and snippets."

    @property
    def args_schema(self) -> type[WebSearchArgs]:
        return WebSearchArgs

    def __init__(self, api_key: str | None = None, max_results: int = 5, proxy: str | None = None):
        super().__init__()
        self._init_api_key = api_key
        self.max_results = max_results
        self.proxy = proxy

    @property
    def api_key(self) -> str:
        """Resolve API key at call time so env/config changes are picked up."""
        return self._init_api_key or os.environ.get("BRAVE_API_KEY", "")

    async def run(self, args: WebSearchArgs) -> str:
        if not self.api_key:
            return (
                "Error: Brave Search API key not configured. Set it in "
                "~/.amberclaw/config.json under tools.web.search.apiKey "
                "(or export BRAVE_API_KEY), then restart the gateway."
            )

        try:
            n = args.count or self.max_results
            logger.debug("WebSearch: {}", "proxy enabled" if self.proxy else "direct connection")
            from typing import cast

            async with httpx.AsyncClient(proxy=cast(str, self.proxy)) as client:
                r = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": args.query, "count": n},
                    headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
                    timeout=10.0,
                )
                r.raise_for_status()

            results = r.json().get("web", {}).get("results", [])[:n]
            if not results:
                return f"No results for: {args.query}"

            lines = [f"Results for: {args.query}\n"]
            for i, item in enumerate(results, 1):
                lines.append(f"{i}. {item.get('title', '')}\n   {item.get('url', '')}")
                if desc := item.get("description"):
                    lines.append(f"   {desc}")
            return "\n".join(lines)
        except httpx.ProxyError as e:
            logger.error("WebSearch proxy error: {}", e)
            return f"Proxy error: {e}"
        except Exception as e:
            logger.error("WebSearch error: {}", e)
            return f"Error: {e}"


class WebFetchArgs(BaseModel):
    """Arguments for the web_fetch tool."""

    url: str = Field(..., description="URL to fetch")
    extract_mode: Literal["markdown", "text"] = Field(
        "markdown",
        description="Extraction mode",
        validation_alias=AliasChoices("extract_mode", "extractMode"),
    )
    max_chars: Optional[int] = Field(
        None,
        ge=100,
        description="Max characters to return",
        validation_alias=AliasChoices("max_chars", "maxChars"),
    )


class WebFetchTool(PydanticTool):
    """Fetch and extract content from a URL using Readability."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch URL and extract readable content (HTML → markdown/text)."

    @property
    def args_schema(self) -> type[WebFetchArgs]:
        return WebFetchArgs

    def __init__(self, max_chars: int = 50000, proxy: str | None = None):
        super().__init__()
        self.max_chars = max_chars
        self.proxy = proxy

    async def run(self, args: WebFetchArgs) -> str:
        from readability import Document

        max_chars = args.max_chars or self.max_chars
        is_valid, error_msg = _validate_url(args.url)
        if not is_valid:
            return json.dumps(
                {"error": f"URL validation failed: {error_msg}", "url": args.url},
                ensure_ascii=False,
            )

        try:
            logger.debug("WebFetch: {}", "proxy enabled" if self.proxy else "direct connection")
            from typing import cast

            async with httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=MAX_REDIRECTS,
                timeout=30.0,
                proxy=cast(str, self.proxy),
            ) as client:
                r = await client.get(args.url, headers={"User-Agent": USER_AGENT})
                r.raise_for_status()

            ctype = r.headers.get("content-type", "")

            if "application/json" in ctype:
                text, extractor = json.dumps(r.json(), indent=2, ensure_ascii=False), "json"
            elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
                doc = Document(r.text)
                content = (
                    self._to_markdown(doc.summary())
                    if args.extract_mode == "markdown"
                    else _strip_tags(doc.summary())
                )
                text = f"# {doc.title()}\n\n{content}" if doc.title() else content
                extractor = "readability"
            else:
                text, extractor = r.text, "raw"

            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            return json.dumps(
                {
                    "url": args.url,
                    "finalUrl": str(r.url),
                    "status": r.status_code,
                    "extractor": extractor,
                    "truncated": truncated,
                    "length": len(text),
                    "text": text,
                },
                ensure_ascii=False,
            )
        except httpx.ProxyError as e:
            logger.error("WebFetch proxy error for {}: {}", args.url, e)
            return json.dumps({"error": f"Proxy error: {e}", "url": args.url}, ensure_ascii=False)
        except Exception as e:
            logger.error("WebFetch error for {}: {}", args.url, e)
            return json.dumps({"error": str(e), "url": args.url}, ensure_ascii=False)

    def _to_markdown(self, html: str) -> str:
        """Convert HTML to markdown."""
        # Convert links, headings, lists before stripping tags
        text = re.sub(
            r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            lambda m: f"[{_strip_tags(m[2])}]({m[1]})",
            html,
            flags=re.I,
        )
        text = re.sub(
            r"<h([1-6])[^>]*>([\s\S]*?)</h\1>",
            lambda m: f"\n{'#' * int(m[1])} {_strip_tags(m[2])}\n",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"<li[^>]*>([\s\S]*?)</li>", lambda m: f"\n- {_strip_tags(m[1])}", text, flags=re.I
        )
        text = re.sub(r"</(p|div|section|article)>", "\n\n", text, flags=re.I)
        text = re.sub(r"<(br|hr)\s*/?>", "\n", text, flags=re.I)
        return _normalize(_strip_tags(text))
