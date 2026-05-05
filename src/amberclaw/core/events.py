"""
AmberClaw Async Event Bus
"""
import asyncio
from typing import Any, Callable, Dict, List, Type
from pydantic import BaseModel, Field
from datetime import datetime


class Event(BaseModel):
    """Base event model."""
    name: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EventBus:
    """Simple async event bus for decoupled communication."""
    
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        """Subscribe to an event."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    async def emit(self, event: Event):
        """Emit an event to all subscribers."""
        if event.name not in self._listeners:
            return

        tasks = []
        for callback in self._listeners[event.name]:
            if asyncio.iscoroutinefunction(callback):
                tasks.append(callback(event))
            else:
                callback(event)
        
        if tasks:
            await asyncio.gather(*tasks)

# Global event bus instance
bus = EventBus()
