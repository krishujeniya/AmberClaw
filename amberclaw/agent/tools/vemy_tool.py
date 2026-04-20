"""Vemy Chat tool — RAG-augmented chat via Vemy's ChatService."""

from typing import Any

from loguru import logger

from amberclaw.agent.tools.base import Tool


class VemyTool(Tool):
    """Invoke the Vemy AI assistant with RAG-augmented chat."""

    name = "vemy_chat"
    description = (
        "Chat with Vemy, a RAG-augmented AI assistant powered by Google Gemini. "
        "Vemy has access to conversation history, a knowledge base, and feedback "
        "examples stored in MongoDB. Use this for general-purpose questions, "
        "knowledge retrieval, and conversational assistance."
    )
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The message to send to Vemy.",
            },
            "session_id": {
                "type": "string",
                "description": "Optional session ID for conversation context. Defaults to today's date.",
            },
        },
        "required": ["message"],
    }

    def __init__(
        self,
        api_key: str | None = None,
        mongodb_uri: str | None = None,
        model: str | None = None,
    ):
        self._api_key = api_key
        self._mongodb_uri = mongodb_uri
        self._model = model
        self._service = None

    def _get_service(self):
        """Lazy-initialize Vemy stack on first call."""
        if self._service is not None:
            return self._service

        import os
        from amberclaw.vemy.AI.Vemy_Agent import VemyAgent
        from amberclaw.vemy.Tools.MongoDB import MongoDBManager
        from amberclaw.vemy.AI.Chat_Handler import ChatService
        from amberclaw.vemy.Credentials import Settings

        # Override settings from constructor params
        if self._api_key:
            Settings.Config.GEMINI_API_KEY = self._api_key
        if self._mongodb_uri:
            Settings.Config.MONGODB_URI = self._mongodb_uri
        if self._model:
            Settings.Config.AUTOGEN_MODEL = self._model

        agent = VemyAgent()
        agent.initialize()

        mongo = MongoDBManager()
        mongo.connect()

        self._service = ChatService(mongodb_manager=mongo, vemy_agent=agent)
        logger.info("Vemy tool stack initialized")
        return self._service

    async def execute(self, message: str, session_id: str | None = None, **kwargs: Any) -> str:
        try:
            service = self._get_service()
            return service.process_message(message, session_id=session_id)
        except Exception as e:
            logger.error("VemyTool error: {}", e)
            return f"Error: Vemy chat failed — {e}"
