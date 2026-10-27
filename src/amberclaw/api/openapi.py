"""OpenAPI Specification Exporter and Documentation Utility."""

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def generate_openapi_schema(app: FastAPI) -> dict[str, Any]:
    """Generate custom OpenAPI specification dictionary for AmberClaw API."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Ensure security schemes are documented
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JSON Web Token (JWT) Bearer Authentication",
    }
    security_schemes["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "AmberClaw API Key Authentication",
    }

    app.openapi_schema = schema
    return schema


def export_openapi_schema(app: FastAPI, output_path: Path | str = "docs/openapi.json") -> Path:
    """Generate and write OpenAPI JSON schema file."""
    schema = generate_openapi_schema(app)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return out
