"""
Vemy - Modular AI Assistant
"""

__version__ = "1.0.0"

from amberclaw.vemy.AI.Vemy_Agent import VemyAgent
from amberclaw.vemy.AI.Chat_Handler import ChatService
from amberclaw.vemy.Tools.RAG import RAGService
from amberclaw.vemy.Tools.MongoDB import MongoDBManager

__all__ = [
    "VemyAgent",
    "ChatService",
    "RAGService",
    "MongoDBManager",
]
