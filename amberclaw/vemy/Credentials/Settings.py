"""
Configuration Settings
Centralized configuration management for the entire application
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Centralized configuration class"""
    
    # Project paths
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    SRC_DIR = BASE_DIR / "src"
    
    # Google Gemini
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    AUTOGEN_MODEL = os.getenv("AUTOGEN_MODEL", "gemini-2.0-flash-exp")
    AUTOGEN_TEMPERATURE = float(os.getenv("AUTOGEN_TEMPERATURE", "0.7"))
    
    # MongoDB
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "vemy_db")
    MONGODB_COLLECTION_CHAT = os.getenv("MONGODB_COLLECTION_CHAT", "chatHistory")
    MONGODB_COLLECTION_FEEDBACK = os.getenv("MONGODB_COLLECTION_FEEDBACK", "Feedback")
    MONGODB_COLLECTION_KNOWLEDGE = os.getenv("MONGODB_COLLECTION_KNOWLEDGE", "knowledgeBase")
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID")
    
    # Google Drive & OAuth
    GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    GOOGLE_OAUTH_PROJECT_ID = os.getenv("GOOGLE_OAUTH_PROJECT_ID", "default-project")
    
    # OAuth token file
    TOKEN_PICKLE_PATH = SRC_DIR / "Credentials" / "token.pickle"
    
    # Embedding settings
    EMBEDDING_MODEL = "models/text-embedding-004"
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    
    # Chat settings
    CONTEXT_WINDOW_LENGTH = 5
    
    # Vemy Agent System Prompt
    VEMY_SYSTEM_PROMPT = os.getenv("VEMY_SYSTEM_PROMPT", """You are Vemy - a warm, intelligent, and helpful AI assistant.

Your personality:
- Friendly and approachable, like talking to a knowledgeable friend
- Professional yet conversational
- Patient and understanding
- Enthusiastic about helping users

Your capabilities:
- Answer questions with accurate, well-researched information
- Remember and reference previous conversations
- Search through knowledge base and feedback to provide better responses
- Provide context-aware and personalized assistance
- Help with a wide variety of tasks

Your communication style:
- Be concise but thorough
- Use clear, simple language
- Add relevant emojis occasionally to make conversations engaging
- Break down complex topics into digestible parts
- Always be respectful and supportive

Remember: You have access to conversation history, positive/negative feedback examples, and a knowledge base. Use these to provide the most helpful and contextual responses possible.""")

    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        
        if not cls.GOOGLE_API_KEY:
            errors.append("GOOGLE_API_KEY is required")
        
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required for bot functionality")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True
    
    @classmethod
    def display(cls):
        """Display current configuration (safe values only)"""
        # print("=" * 60)
        # print("Configuration Settings")
        # print("=" * 60)
        # print(f"Model: {cls.AUTOGEN_MODEL}")
        # print(f"MongoDB: {'SET' if cls.MONGODB_URI else 'MISSING'}")
        # print(f"Database: {cls.MONGODB_DATABASE}")
        # print(f"Google API Key: {'SET' if cls.GOOGLE_API_KEY else 'MISSING'}")
        # print(f"Telegram Token: {'SET' if cls.TELEGRAM_BOT_TOKEN else 'MISSING'}")
        # print(f"OAuth Client ID: {'SET' if cls.GOOGLE_OAUTH_CLIENT_ID else 'MISSING'}")
        # print("=" * 60)
        pass
