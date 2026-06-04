from abc import ABC, abstractmethod
from typing import Any


class BaseTerminalBackend(ABC):
    """Abstract base class for all terminal execution backends."""

    @abstractmethod
    async def execute_bash(
        self, command: str, timeout: int = 30
    ) -> dict[str, Any]:
        """
        Execute a bash command in the target environment.
        
        Returns a dict containing:
        - stdout (str)
        - stderr (str)
        - exit_code (int)
        - execution_time_ms (float)
        """
        pass

    @abstractmethod
    async def execute_python(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Execute Python code in the target environment.
        
        Returns a dict containing:
        - stdout (str)
        - stderr (str)
        - exit_code (int)
        - execution_time_ms (float)
        """
        pass
