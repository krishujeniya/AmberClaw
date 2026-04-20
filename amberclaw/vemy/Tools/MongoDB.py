"""
MongoDB Tool
Handles all MongoDB operations including chat history, feedback, and knowledge base
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from amberclaw.vemy.Credentials.Settings import Config


class MongoDBChatMemory:
    """MongoDB-based chat memory for storing conversation history"""
    
    def __init__(self, client: MongoClient, database: str, collection: str):
        self.db = client[database]
        self.collection = self.db[collection]
        # Ensure fast lookups by sessionId
        self.collection.create_index("sessionId")
        
    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to chat history in the new format"""
        # Map role to type
        msg_type = "human" if role == "user" else "ai"
        
        # Prepare message data
        message_data = {
            "content": content,
            "additional_kwargs": {},
            "response_metadata": {}
        }
        
        # Add AI-specific fields
        if msg_type == "ai":
            message_data["tool_calls"] = []
            message_data["invalid_tool_calls"] = []
            
        # Construct the message object
        new_message = {
            "type": msg_type,
            "data": message_data
        }
        
        # Upsert the document: create if not exists, push to messages array
        self.collection.update_one(
            {"sessionId": session_id},
            {"$push": {"messages": new_message}},
            upsert=True
        )
        
    def get_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Retrieve chat history for a session"""
        doc = self.collection.find_one({"sessionId": session_id})
        
        if not doc or "messages" not in doc:
            return []
            
        # Return last N messages
        return doc["messages"][-limit:]
    
    def clear_history(self, session_id: str):
        """Clear chat history for a session"""
        self.collection.delete_one({"sessionId": session_id})


class MongoDBVectorStore:
    """MongoDB Vector Store for feedback and knowledge base"""
    
    def __init__(self, client: MongoClient, database: str, collection: str, 
                 index_name: str, metadata_field: str = "text", 
                 embedding_field: str = "embedding", limit: int = 4):
        self.db = client[database]
        self.collection = self.db[collection]
        self.index_name = index_name
        self.metadata_field = metadata_field
        self.embedding_field = embedding_field
        self.default_limit = limit
        
        # Initialize embeddings
        if Config.GOOGLE_API_KEY:
            try:
                self.embeddings = GoogleGenerativeAIEmbeddings(
                    model=Config.EMBEDDING_MODEL,
                    google_api_key=Config.GOOGLE_API_KEY
                )
            except Exception as e:
                print(f"⚠️  Warning: Could not initialize embeddings: {e}")
                self.embeddings = None
        else:
            self.embeddings = None
    
    def add_document(self, text: str, metadata: Dict[str, Any]):
        """Add a document to the vector store with embedding"""
        if not self.embeddings:
            print("⚠️  Embeddings not available, skipping vector store")
            return
        
        try:
            embedding_vector = self.embeddings.embed_query(text)
            
            document = {
                self.metadata_field: text,
                self.embedding_field: embedding_vector,
                "metadata": metadata,
                "timestamp": datetime.now()
            }
            self.collection.insert_one(document)
            print(f"✅ Document added to {self.collection.name}")
        except Exception as e:
            print(f"⚠️  Error adding document: {e}")
    
    def add_feedback(self, prompt: str, response: str, feedback_type: str):
        """Add feedback document with specific schema"""
        if not self.embeddings:
            print("⚠️  Embeddings not available, skipping feedback storage")
            return

        try:
            text = f"Prompt: {prompt}\nCompletion: {response}"
            embedding = self.embeddings.embed_query(text)

            doc = {
                "text": text,
                "embedding": embedding,
                "source": "blob",
                "blobType": "text/plain",
                "loc": {"lines": {"from": 1, "to": 2}},
                "prompt": prompt,
                "response": response,
                "feedback": feedback_type,
                "timestamp": datetime.now()
            }
            self.collection.insert_one(doc)
            print(f"✅ Feedback added to {self.collection.name}")
        except Exception as e:
            print(f"⚠️  Error adding feedback: {e}")

    def add_csv_document(self, text: str, line_number: int, source: str = "blob", blob_type: str = "text/csv"):
        """Add CSV document with specific n8n-like schema"""
        if not self.embeddings:
            print("⚠️  Embeddings not available, skipping CSV storage")
            return

        try:
            embedding = self.embeddings.embed_query(text)

            doc = {
                "text": text,
                "embedding": embedding,
                "source": source,
                "blobType": blob_type,
                "line": line_number,
                "loc": {"lines": {"from": 1, "to": 5}}, # Fixed structure as requested
                "doc_id": None,
                "timestamp": datetime.now()
            }
            self.collection.insert_one(doc)
            print(f"✅ CSV Document added (Line {line_number})")
        except Exception as e:
            print(f"⚠️  Error adding CSV document: {e}")

    def search_similar(self, query: str, filter_metadata: Optional[Dict] = None, 
                      k: int = None, include_metadata: bool = True) -> List[Dict]:
        """Search for similar documents using text search with metadata filtering"""
        if k is None:
            k = self.default_limit
        
        search_filter = {self.metadata_field: {"$regex": query, "$options": "i"}}
        
        if filter_metadata:
            for key, value in filter_metadata.items():
                search_filter[key] = value
        
        try:
            results = self.collection.find(search_filter).limit(k)
            documents = list(results)
            
            formatted_results = []
            for doc in documents:
                result = {"text": doc.get(self.metadata_field, "")}
                # Include all fields except embedding and _id for context
                extra_data = {k: v for k, v in doc.items() if k not in ['embedding', '_id', self.metadata_field]}
                if extra_data:
                    result["metadata"] = extra_data
                    
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            print(f"⚠️  Search error: {e}")
            return []
    
    def clear_documents(self, doc_id: str = None):
        """Clear documents from vector store"""
        try:
            if doc_id:
                result = self.collection.delete_many({"metadata.doc_id": doc_id})
                if result.deleted_count > 0:
                    print(f"🗑️  Removed {result.deleted_count} chunks for: {doc_id}")
            else:
                result = self.collection.delete_many({})
                print(f"🗑️  Removed {result.deleted_count} documents")
        except Exception as e:
            print(f"⚠️  Error clearing documents: {e}")


class MongoDBManager:
    """MongoDB Tool - Centralized database manager"""
    
    def __init__(self):
        self.client = None
        self.chat_memory = None
        self.feedback_positive = None
        self.feedback_negative = None
        self.knowledge_base = None
        self.connected = False
        
    def connect(self):
        """Connect to MongoDB and initialize all stores"""
        try:
            self.client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            # print("✅ MongoDB connected successfully")
            self.connected = True
            
            # Initialize chat memory
            self.chat_memory = MongoDBChatMemory(
                client=self.client,
                database=Config.MONGODB_DATABASE,
                collection=Config.MONGODB_COLLECTION_CHAT
            )
            
            # Initialize Positive Feedback Vector Store
            self.feedback_positive = MongoDBVectorStore(
                client=self.client,
                database=Config.MONGODB_DATABASE,
                collection=Config.MONGODB_COLLECTION_FEEDBACK,
                index_name="feedbackSearchVector",
                metadata_field="text",
                embedding_field="embedding",
                limit=4
            )
            
            # Initialize Negative Feedback Vector Store
            self.feedback_negative = MongoDBVectorStore(
                client=self.client,
                database=Config.MONGODB_DATABASE,
                collection=Config.MONGODB_COLLECTION_FEEDBACK,
                index_name="feedbackSearchVector",
                metadata_field="text",
                embedding_field="embedding",
                limit=4
            )
            
            # Initialize Knowledge Base Vector Store
            self.knowledge_base = MongoDBVectorStore(
                client=self.client,
                database=Config.MONGODB_DATABASE,
                collection=Config.MONGODB_COLLECTION_KNOWLEDGE,
                index_name="knowledgeBaseVector",
                metadata_field="text",
                embedding_field="embedding",
                limit=4
            )
            
            return True
            
        except Exception as e:
            # Sanitize error message to remove potential connection strings
            error_msg = str(e)
            if "mongodb" in error_msg.lower():
                # Simplified error message to avoid leaking details
                error_msg = "Connection failed (Network/Auth issue)"
            
            print(f"⚠️  MongoDB connection failed: {error_msg}")
            print("💡 HINT: Check IP whitelist in MongoDB Atlas.")
            print("⚠️  Running without MongoDB persistence")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            # print("✅ MongoDB disconnected")
