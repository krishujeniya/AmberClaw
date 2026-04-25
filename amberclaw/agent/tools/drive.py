import os
import pickle
from typing import Type
from pathlib import Path
from pydantic import BaseModel, Field

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from amberclaw.agent.tools.base import PydanticTool
from amberclaw.config.loader import load_config

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata",
]


class DriveManager:
    """Helper to manage Google Drive service connection."""

    def __init__(self, config):
        self.config = config
        self.service = None

    def _get_service(self):
        if self.service:
            return self.service

        creds = None
        token_path = Path(self.config.token_json or "~/.amberclaw/drive_token.pickle").expanduser()

        if token_path.exists():
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # In a terminal tool, we might need to prompt for OAuth
                # but for now we assume credentials are pre-configured or handled by env
                # If credentials_json is provided as raw JSON string or path
                creds_json = self.config.credentials_json
                if os.path.exists(creds_json):
                    flow = InstalledAppFlow.from_client_secrets_file(creds_json, SCOPES)
                else:
                    # Fallback to local server if we're in an interactive session
                    # This is risky in some environments but standard for CLI tools
                    raise ConnectionError(
                        "Google Drive credentials not found. Please configure tools.drive.credentials_json"
                    )

                creds = flow.run_local_server(port=0)

            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        self.service = build("drive", "v3", credentials=creds)
        return self.service


class DriveSearchInput(BaseModel):
    query: str = Field(..., description="The search string to find files in Google Drive.")


class DriveSearchTool(PydanticTool):
    name: str = "drive_search"
    description: str = "Search for files and folders in Google Drive by name."
    args_schema: Type[BaseModel] = DriveSearchInput

    def _execute(self, query: str) -> str:
        config = load_config()
        if not config.tools.drive.enabled:
            return "Google Drive tool is disabled in config."

        manager = DriveManager(config.tools.drive)
        service = manager._get_service()

        q = f"name contains '{query}'"
        results = (
            service.files()
            .list(q=q, fields="files(id, name, mimeType, modifiedTime)", pageSize=10)
            .execute()
        )

        files = results.get("files", [])
        if not files:
            return "No files matching the query were found."

        output = ["Files found in Google Drive:"]
        for f in files:
            output.append(f"- {f['name']} (ID: {f['id']}, Type: {f['mimeType']})")
        return "\n".join(output)


class DriveUploadInput(BaseModel):
    file_path: str = Field(..., description="Local path to the file to upload.")
    folder_id: str = Field(
        "root", description="ID of the destination folder in Google Drive (defaults to 'root')."
    )


class DriveUploadTool(PydanticTool):
    name: str = "drive_upload"
    description: str = "Upload a local file to Google Drive."
    args_schema: Type[BaseModel] = DriveUploadInput

    def _execute(self, file_path: str, folder_id: str = "root") -> str:
        config = load_config()
        if not config.tools.drive.enabled:
            return "Google Drive tool is disabled in config."

        path = Path(file_path).expanduser()
        if not path.exists():
            return f"Error: Local file {file_path} does not exist."

        manager = DriveManager(config.tools.drive)
        service = manager._get_service()

        file_metadata = {"name": path.name, "parents": [folder_id]}
        media = MediaFileUpload(str(path), resumable=True)
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
            .execute()
        )

        return f"File uploaded successfully: {file['name']} (ID: {file['id']})\nLink: {file.get('webViewLink')}"
