"""
RAG Tool
Handles document synchronization from Google Drive to MongoDB knowledge base
"""

import os
import json as json_lib
from datetime import datetime
from typing import List, Dict

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
    CSVLoader,
)

from amberclaw.vemy.Credentials.Settings import Config
from amberclaw.vemy.Tools.MongoDB import MongoDBManager
from amberclaw.vemy.Tools.Google_Drive import GoogleDriveManager

# Supported MIME types
SUPPORTED_TYPES = {
    'application/pdf': 'PDF',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
    'text/plain': 'TXT',
    'text/csv': 'CSV',
    'application/json': 'JSON',
    'application/vnd.google-apps.document': 'Google Doc',
    'application/vnd.google-apps.spreadsheet': 'Google Sheet',
    'image/png': 'PNG Image',
    'image/jpeg': 'JPEG Image',
    'image/jpg': 'JPG Image',
}


class RAGService:
    """RAG Tool - Retrieval-Augmented Generation for knowledge base management"""
    
    def __init__(self, mongodb_manager: MongoDBManager, drive_manager: GoogleDriveManager):
        self.mongodb = mongodb_manager
        self.drive = drive_manager
        self.embeddings = None
        
    def initialize(self):
        """Initialize RAG service"""
        self._init_embeddings()
        return True
    
    def _init_embeddings(self):
        """Initialize Google Gemini embeddings"""
        if not Config.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required")
        
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=Config.EMBEDDING_MODEL,
            google_api_key=Config.GOOGLE_API_KEY
        )
        print("✅ Google Gemini Embeddings initialized")
    
    def select_files(self, files: List[Dict]) -> List[Dict]:
        """Display and select files to process"""
        print("\n" + "="*60)
        print("📁 Files in Google Drive Folder")
        print("="*60)
        
        supported_files = []
        for idx, file in enumerate(files, 1):
            mime_type = file.get('mimeType', '')
            if mime_type in SUPPORTED_TYPES:
                file_type = SUPPORTED_TYPES[mime_type]
                supported_files.append(file)
                print(f"{idx}. {file['name']}")
                print(f"   Type: {file_type}")
                print()
        
        if not supported_files:
            print("❌ No supported files found")
            return []
        
        print("="*60)
        print(f"\nFound {len(supported_files)} supported files")
        print("\nOptions: Enter file numbers (e.g., 1,3,5), 'all', or 'q' to quit")
        
        while True:
            choice = input("\nYour choice: ").strip().lower()
            
            if choice == 'q':
                return []
            
            if choice == 'all':
                print(f"✅ Selected all {len(supported_files)} files")
                return supported_files
            
            try:
                indices = [int(x.strip()) for x in choice.split(',')]
                selected = []
                for idx in indices:
                    if 1 <= idx <= len(supported_files):
                        selected.append(supported_files[idx - 1])
                
                if selected:
                    print(f"✅ Selected {len(selected)} files")
                    return selected
            except ValueError:
                print("❌ Invalid input. Try again.")
    
    def process_document(self, file_content: bytes, file_name: str, 
                        file_id: str, mime_type: str) -> List[Document]:
        """Process document and split into chunks"""
        try:
            temp_path = f"/tmp/{file_name}"
            
            if mime_type == 'application/pdf' or file_name.endswith('.pdf'):
                with open(temp_path, 'wb') as f:
                    f.write(file_content)
                loader = PyPDFLoader(temp_path)
                documents = loader.load()
            
            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                with open(temp_path, 'wb') as f:
                    f.write(file_content)
                loader = UnstructuredWordDocumentLoader(temp_path)
                documents = loader.load()
            
            elif mime_type in ['text/plain', 'application/vnd.google-apps.document']:
                text_content = file_content.decode('utf-8')
                documents = [Document(page_content=text_content, metadata={"source": file_name})]
            
            elif mime_type in ['text/csv', 'application/vnd.google-apps.spreadsheet']:
                with open(temp_path, 'wb') as f:
                    f.write(file_content)
                loader = CSVLoader(temp_path)
                documents = loader.load()
            
            elif mime_type == 'application/json':
                json_content = json_lib.loads(file_content.decode('utf-8'))
                text_content = json_lib.dumps(json_content, indent=2)
                documents = [Document(page_content=text_content, 
                                    metadata={"source": file_name, "type": "json"})]
            
            elif mime_type in ['image/png', 'image/jpeg', 'image/jpg']:
                text_content = f"Image file: {file_name}\nType: {mime_type}"
                documents = [Document(page_content=text_content, 
                                    metadata={"source": file_name, "type": "image"})]
            else:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return []
            
            # Split into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=Config.CHUNK_SIZE,
                chunk_overlap=Config.CHUNK_OVERLAP
            )
            chunks = text_splitter.split_documents(documents)
            
            # Add metadata
            for chunk in chunks:
                chunk.metadata['doc_id'] = file_id
                chunk.metadata['file_name'] = file_name
                chunk.metadata['mime_type'] = mime_type
                chunk.metadata['source'] = 'google_drive'
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            print(f"✅ Processed {file_name}: {len(chunks)} chunks")
            return chunks
        except Exception as e:
            print(f"❌ Error processing {file_name}: {e}")
            return []
    
    def sync_to_mongodb(self, documents: List[Document]):
        """Sync documents to MongoDB"""
        if not documents or not self.mongodb.connected:
            return
        
        try:
            inserted_count = 0
            for doc in documents:
                # Check if it's a CSV document
                if doc.metadata.get('mime_type') in ['text/csv', 'application/vnd.google-apps.spreadsheet']:
                    # Use the new CSV specific method
                    # CSVLoader puts row number in 'row' metadata
                    line_number = doc.metadata.get('row', 0)
                    self.mongodb.knowledge_base.add_csv_document(
                        text=doc.page_content,
                        line_number=line_number
                    )
                else:
                    # Standard insertion for other types
                    embedding = self.embeddings.embed_query(doc.page_content)
                    
                    mongo_doc = {
                        "text": doc.page_content,
                        "embedding": embedding,
                        "metadata": doc.metadata,
                        "timestamp": datetime.now()
                    }
                    
                    self.mongodb.knowledge_base.collection.insert_one(mongo_doc)
                
                inserted_count += 1
            
            print(f"✅ Inserted {inserted_count} documents to MongoDB")
        except Exception as e:
            print(f"❌ Error inserting to MongoDB: {e}")
    
    def run_sync(self):
        """Run full synchronization workflow"""
        print("=" * 60)
        print("📚 RAG Knowledge Base Sync")
        print("=" * 60)
        print()
        
        # List files from Google Drive
        print("📂 Fetching files from Google Drive...")
        files = self.drive.list_files()
        
        if not files:
            print("❌ No files found")
            return
        
        # Select files
        selected_files = self.select_files(files)
        
        if not selected_files:
            return
        
        print("\n" + "="*60)
        print("🚀 Starting Processing...")
        print("="*60)
        print()
        
        # Process each file
        total_chunks = 0
        successful = 0
        
        for idx, file_info in enumerate(selected_files, 1):
            file_id = file_info['id']
            file_name = file_info['name']
            mime_type = file_info.get('mimeType', '')
            
            print(f"\n[{idx}/{len(selected_files)}] Processing: {file_name}")
            
            # Clear existing chunks
            if self.mongodb.connected and self.mongodb.knowledge_base:
                self.mongodb.knowledge_base.clear_documents(doc_id=file_id)
            
            # Download from Google Drive
            file_content = self.drive.download_file(file_id, file_name, mime_type)
            if not file_content:
                continue
            
            # Process document
            chunks = self.process_document(file_content, file_name, file_id, mime_type)
            if not chunks:
                continue
            
            # Sync to MongoDB
            self.sync_to_mongodb(chunks)
            total_chunks += len(chunks)
            successful += 1
        
        print()
        print("=" * 60)
        print(f"✅ Sync Complete!")
        print(f"   Files processed: {successful}/{len(selected_files)}")
        print(f"   Total chunks: {total_chunks}")
        print("=" * 60)
