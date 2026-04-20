"""
Chat Tool
Handles chat logic and message processing with RAG integration
"""

from datetime import datetime
from typing import List, Dict

from amberclaw.vemy.Tools.MongoDB import MongoDBManager
from amberclaw.vemy.AI.Vemy_Agent import VemyAgent
from amberclaw.vemy.Credentials.Settings import Config


class ChatService:
    """Chat Tool - Intelligent message processing with context"""
    
    def __init__(self, mongodb_manager: MongoDBManager, vemy_agent: VemyAgent):
        self.mongodb = mongodb_manager
        self.vemy = vemy_agent
        
    @property
    def current_session_id(self) -> str:
        """Get current session ID (defaults to today's date)"""
        return datetime.now().strftime("%d-%m-%Y")
        
    def process_message(self, user_message: str, session_id: str = None) -> str:
        """Process a user message and return response"""
        # Use provided session_id or default to current date
        active_session_id = session_id or self.current_session_id
        
        # Save user message to chat memory
        if self.mongodb.connected and self.mongodb.chat_memory:
            self.mongodb.chat_memory.add_message(active_session_id, "user", user_message)
        
        # Search for relevant feedback and knowledge
        positive_feedback = self._search_feedback(user_message, "positive")
        negative_feedback = self._search_feedback(user_message, "negative")
        knowledge = self._search_knowledge_base(user_message)
        
        # Build context
        context = self._build_context(positive_feedback, negative_feedback, knowledge)
        
        # Get chat history
        history_text = self._get_history_text(active_session_id)
        
        # Prepare full prompt
        full_prompt = f"""{self.vemy.system_instruction}

{history_text}
{context}

User: {user_message}

Assistant (Vemy):"""
        
        # Get response from Vemy Agent
        assistant_response = self.vemy.generate_response(full_prompt)
        
        # Save assistant response to chat memory
        if self.mongodb.connected and self.mongodb.chat_memory:
            self.mongodb.chat_memory.add_message(active_session_id, "assistant", assistant_response)
        
        return assistant_response
    
    def _search_feedback(self, query: str, feedback_type: str = "positive") -> List[Dict]:
        """Search for similar feedback"""
        if not self.mongodb.connected:
            return []
        
        if feedback_type == "positive" and self.mongodb.feedback_positive:
            filter_metadata = {"feedback": "positive"}
            return self.mongodb.feedback_positive.search_similar(query, filter_metadata, include_metadata=True)
        elif feedback_type == "negative" and self.mongodb.feedback_negative:
            filter_metadata = {"feedback": "negative"}
            return self.mongodb.feedback_negative.search_similar(query, filter_metadata, include_metadata=True)
        
        return []
    
    def _search_knowledge_base(self, query: str) -> List[Dict]:
        """Search knowledge base"""
        if not self.mongodb.connected or not self.mongodb.knowledge_base:
            return []
        
        return self.mongodb.knowledge_base.search_similar(query, include_metadata=True)
    
    def _build_context(self, positive_feedback: List[Dict], 
                       negative_feedback: List[Dict], knowledge: List[Dict]) -> str:
        """Build context from search results"""
        context = ""
        
        if positive_feedback:
            context += "\n\nPositive feedback examples:\n"
            for fb in positive_feedback[:2]:
                context += f"- {fb.get('text', '')}\n"
        
        if negative_feedback:
            context += "\n\nAvoid these approaches (negative feedback):\n"
            for fb in negative_feedback[:2]:
                context += f"- {fb.get('text', '')}\n"
        
        if knowledge:
            context += "\n\nRelevant knowledge:\n"
            for kb in knowledge[:2]:
                context += f"- {kb.get('text', '')}\n"
        
        return context
    
    def _get_history_text(self, session_id: str) -> str:
        """Get chat history as text"""
        if not self.mongodb.connected or not self.mongodb.chat_memory:
            return ""
        
        history = self.mongodb.chat_memory.get_history(
            session_id, 
            limit=Config.CONTEXT_WINDOW_LENGTH
        )
        
        if not history:
            return ""
        
        history_text = "\n\nRecent conversation:\n"
        for msg in history:
            msg_type = msg.get('type', 'unknown')
            # Map type back to display role
            if msg_type == 'human':
                role = 'User'
            elif msg_type == 'ai':
                role = 'Assistant'
            else:
                role = msg_type.capitalize()
                
            # Extract content from nested data structure
            content = msg.get('data', {}).get('content', '')
            history_text += f"{role}: {content}\n"
        
        return history_text
    
    def clear_history(self, session_id: str = None):
        """Clear chat history"""
        target_session_id = session_id or self.current_session_id
        if self.mongodb.connected and self.mongodb.chat_memory:
            self.mongodb.chat_memory.clear_history(target_session_id)
            return True
        return False
