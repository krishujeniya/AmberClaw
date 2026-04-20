"""
Vemy Agent Main
Core AI agent powered by Google Gemini with configurable system prompts
"""

import google.generativeai as genai
from amberclaw.vemy.Credentials.Settings import Config


class VemyAgent:
    """Vemy AI Agent - Main intelligence powered by Google Gemini"""
    
    def __init__(self):
        self.model = None
        self.system_instruction = Config.VEMY_SYSTEM_PROMPT
        
    def initialize(self):
        """Initialize Gemini AI agent"""
        if not Config.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required")
        
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        
        # Initialize model with system instruction
        self.model = genai.GenerativeModel(
            model_name=Config.AUTOGEN_MODEL,
            system_instruction=self.system_instruction
        )
        
        # print(f"✅ Vemy Agent initialized (model: {Config.AUTOGEN_MODEL})")
        # print(f"   System prompt: {len(self.system_instruction)} characters")
        return True
    
    def generate_response(self, prompt: str) -> str:
        """Generate response from Vemy Agent"""
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            error_msg = f"I encountered an error: {str(e)}"
            print(f"❌ Error in Vemy Agent: {e}")
            return error_msg
    
    def chat(self, message: str, history: list = None) -> str:
        """Chat with context history"""
        try:
            if history:
                # Build conversation context
                conversation = self.model.start_chat(history=history)
                response = conversation.send_message(message)
            else:
                response = self.model.generate_content(message)
            
            return response.text
        except Exception as e:
            error_msg = f"I encountered an error: {str(e)}"
            print(f"❌ Error in chat: {e}")
            return error_msg
