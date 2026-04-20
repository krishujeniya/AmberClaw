"""
Google Drive Tool
Comprehensive Google Drive API operations including search, upload, share, move, and folder management
"""

import os
import io
import pickle
from typing import List, Dict, Optional, Union
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

from amberclaw.vemy.Credentials.Settings import Config

# Google Drive API scopes - Full access for all operations
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.metadata'
]


class GoogleDriveManager:
    """Google Drive Tool - Comprehensive Drive API manager"""
    
    def __init__(self):
        self.drive_service = None
        self.connected = False
        
    def connect(self):
        """Initialize Google Drive API using OAuth2 from environment variables"""
        try:
            creds = None
            token_file = str(Config.TOKEN_PICKLE_PATH)
            
            if os.path.exists(token_file):
                with open(token_file, 'rb') as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    print("🔄 Refreshing access token...")
                    creds.refresh(Request())
                else:
                    print("\n" + "="*60)
                    print("🔐 Google Drive OAuth2 Authentication Required")
                    print("="*60)
                    
                    if not all([Config.GOOGLE_OAUTH_CLIENT_ID, Config.GOOGLE_OAUTH_CLIENT_SECRET]):
                        print("\n❌ Error: OAuth credentials not found in .env file!")
                        print("   Please add: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET")
                        print("   Get them from: https://console.cloud.google.com/apis/credentials")
                        print("="*60 + "\n")
                        self.connected = False
                        return False
                    
                    client_config = {
                        "installed": {
                            "client_id": Config.GOOGLE_OAUTH_CLIENT_ID,
                            "client_secret": Config.GOOGLE_OAUTH_CLIENT_SECRET,
                            "project_id": Config.GOOGLE_OAUTH_PROJECT_ID,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            "redirect_uris": ["http://localhost"]
                        }
                    }
                    
                    print("\n✅ OAuth credentials loaded from environment variables")
                    print("   Opening browser for authentication...")
                    print("="*60 + "\n")
                    
                    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                    creds = flow.run_local_server(port=8080)
                
                with open(token_file, 'wb') as token:
                    pickle.dump(creds, token)
                # print("✅ Credentials saved for future use")
            
            self.drive_service = build('drive', 'v3', credentials=creds)
            self.connected = True
            # print("✅ Google Drive API initialized")
            return True
            
        except Exception as e:
            print(f"❌ Error initializing Google Drive: {e}")
            self.connected = False
            return False
    
    # ========== SEARCH OPERATIONS ==========
    
    def search_files(self, query_string: str, folder_id: Optional[str] = None) -> List[Dict]:
        """Search files and folders in Google Drive by name"""
        if not self.connected or not self.drive_service:
            print("❌ Google Drive service not available")
            return []
        
        try:
            # Build search query
            search_query = f"name contains '{query_string}' and trashed=false"
            if folder_id:
                search_query = f"'{folder_id}' in parents and {search_query}"
            
            results = self.drive_service.files().list(
                q=search_query,
                fields="files(id, name, mimeType, modifiedTime, size, webViewLink)",
                pageSize=100
            ).execute()
            
            files = results.get('files', [])
            print(f"✅ Found {len(files)} files matching '{query_string}'")
            return files
        except Exception as e:
            print(f"❌ Error searching files: {e}")
            return []
    
    # ========== LIST OPERATIONS ==========
    
    def list_files(self, folder_id: Optional[str] = None) -> List[Dict]:
        """List all files in Google Drive folder"""
        if not self.connected or not self.drive_service:
            print("❌ Google Drive service not available")
            return []
        
        folder_id = folder_id or Config.GOOGLE_DRIVE_FOLDER_ID
        
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime)",
                pageSize=100
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            print(f"❌ Error listing files: {e}")
            return []
    
    # ========== DOWNLOAD OPERATIONS ==========
    
    def download_file(self, file_id: str, file_name: str, mime_type: str) -> Optional[bytes]:
        """Download file from Google Drive"""
        if not self.connected or not self.drive_service:
            print("❌ Google Drive service not available")
            return None
        
        try:
            if mime_type == 'application/vnd.google-apps.document':
                request = self.drive_service.files().export_media(
                    fileId=file_id, mimeType='text/plain')
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                request = self.drive_service.files().export_media(
                    fileId=file_id, mimeType='text/csv')
            else:
                request = self.drive_service.files().get_media(fileId=file_id)
            
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_content.seek(0)
            print(f"✅ Downloaded: {file_name}")
            return file_content.read()
        except Exception as e:
            print(f"❌ Error downloading {file_name}: {e}")
            return None
    
    # ========== UPLOAD OPERATIONS ==========
    
    def upload_file(self, file_path: str, file_name: Optional[str] = None, 
                   parent_folder_id: Optional[str] = 'root', mime_type: Optional[str] = None) -> Optional[Dict]:
        """Upload file to Google Drive"""
        if not self.connected or not self.drive_service:
            print("❌ Google Drive service not available")
            return None
        
        try:
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                return None
            
            # Use provided name or extract from path
            name = file_name or Path(file_path).name
            
            # File metadata
            file_metadata = {
                'name': name,
                'parents': [parent_folder_id]
            }
            
            # Create media upload
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            
            # Upload file
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()
            
            print(f"✅ Uploaded: {name} (ID: {file.get('id')})")
            return file
        except Exception as e:
            print(f"❌ Error uploading file: {e}")
            return None
    
    # ========== SHARE OPERATIONS ==========
    
    def share_file(self, file_id: str, email_address: str, role: str = 'reader') -> bool:
        """Share file with a user (reader, writer, or commenter)"""
        if not self.connected or not self.drive_service:
            print("❌ Google Drive service not available")
            return False
        
        try:
            permission = {
                'type': 'user',
                'role': role,  # reader, writer, commenter
                'emailAddress': email_address
            }
            
            self.drive_service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id'
            ).execute()
            
            print(f"✅ Shared file with {email_address} as {role}")
            return True
        except Exception as e:
            print(f"❌ Error sharing file: {e}")
            return False
    
    def share_folder(self, folder_id: str, email_address: str, role: str = 'reader') -> bool:
        """Share folder with a user"""
        return self.share_file(folder_id, email_address, role)
    
    # ========== MOVE OPERATIONS ==========
    
    def move_file(self, file_id: str, new_parent_folder_id: str) -> bool:
        """Move file to a different folder"""
        if not self.connected or not self.drive_service:
            print("❌ Google Drive service not available")
            return False
        
        try:
            # Get current parents
            file = self.drive_service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()
            
            previous_parents = ",".join(file.get('parents', []))
            
            # Move file
            self.drive_service.files().update(
                fileId=file_id,
                addParents=new_parent_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            
            print(f"✅ Moved file to new folder")
            return True
        except Exception as e:
            print(f"❌ Error moving file: {e}")
            return False
    
    # ========== FOLDER OPERATIONS ==========
    
    def create_folder(self, folder_name: str, parent_folder_id: str = 'root') -> Optional[Dict]:
        """Create a new folder in Google Drive"""
        if not self.connected or not self.drive_service:
            print("❌ Google Drive service not available")
            return None
        
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }
            
            folder = self.drive_service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink'
            ).execute()
            
            print(f"✅ Created folder: {folder_name} (ID: {folder.get('id')})")
            return folder
        except Exception as e:
            print(f"❌ Error creating folder: {e}")
            return None
    
    # ========== SHARED DRIVE OPERATIONS ==========
    
    def list_shared_drives(self, limit: int = 10) -> List[Dict]:
        """Get a list of shared drives"""
        if not self.connected or not self.drive_service:
            print("❌ Google Drive service not available")
            return []
        
        try:
            results = self.drive_service.drives().list(
                pageSize=limit,
                fields="drives(id, name)"
            ).execute()
            
            drives = results.get('drives', [])
            print(f"✅ Found {len(drives)} shared drives")
            return drives
        except Exception as e:
            print(f"❌ Error listing shared drives: {e}")
            return []
    
    def get_shared_drive(self, drive_id: str) -> Optional[Dict]:
        """Get information about a specific shared drive"""
        if not self.connected or not self.drive_service:
            print("❌ Google Drive service not available")
            return None
        
        try:
            drive = self.drive_service.drives().get(
                driveId=drive_id,
                fields="id, name, createdTime"
            ).execute()
            
            print(f"✅ Retrieved shared drive: {drive.get('name')}")
            return drive
        except Exception as e:
            print(f"❌ Error getting shared drive: {e}")
            return None
    
    # ========== UTILITY OPERATIONS ==========
    
    def disconnect(self):
        """Cleanup Google Drive connection"""
        self.drive_service = None
        self.connected = False
        # print("✅ Google Drive disconnected")
