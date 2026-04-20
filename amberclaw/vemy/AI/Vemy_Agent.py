"""
Vemy Agent Main
Core AI agent powered by Google Gemini with configurable system prompts

Migrated to google-genai SDK (google-generativeai is deprecated/EOL).
Uses Client-based API instead of global genai.configure().
"""

from __future__ import annotations

from google import genai
from google.genai import types
from loguru import logger

from amberclaw.vemy.Credentials.Settings import Config


class VemyAgent:
    """Vemy AI Agent - Main intelligence powered by Google Gemini"""

    def __init__(self):
        self._client: genai.Client | None = None
        self.model_name: str = Config.AUTOGEN_MODEL
        self.system_instruction: str = Config.VEMY_SYSTEM_PROMPT

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            raise RuntimeError("VemyAgent not initialized — call initialize() first")
        return self._client

    def initialize(self) -> bool:
        """Initialize Gemini AI client"""
        api_key = Config.GEMINI_API_KEY or Config.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is required")

        self._client = genai.Client(api_key=api_key)
        logger.info("Vemy Agent initialized (model: {})", self.model_name)
        return True

    def generate_response(self, prompt: str) -> str:
        """Generate response from Vemy Agent"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=Config.AUTOGEN_TEMPERATURE,
                ),
            )
            return response.text or ""
        except Exception as e:
            logger.error("Vemy Agent error: {}", e)
            return f"I encountered an error: {e}"

    def chat(self, message: str, history: list | None = None) -> str:
        """Chat with context history"""
        try:
            if history:
                chat = self.client.chats.create(
                    model=self.model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction,
                        temperature=Config.AUTOGEN_TEMPERATURE,
                    ),
                    history=[
                        types.Content(role=h.get("role", "user"), parts=[types.Part.from_text(h.get("content", ""))])
                        for h in history
                    ],
                )
                response = chat.send_message(message)
            else:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=message,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction,
                        temperature=Config.AUTOGEN_TEMPERATURE,
                    ),
                )
            return response.text or ""
        except Exception as e:
            logger.error("Vemy chat error: {}", e)
            return f"I encountered an error: {e}"
