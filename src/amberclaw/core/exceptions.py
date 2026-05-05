"""
AmberClaw Core Exceptions
"""

class AmberClawError(Exception):
    """Base exception for all AmberClaw errors."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ConfigurationError(AmberClawError):
    """Raised when there is a configuration issue."""
    def __init__(self, message: str):
        super().__init__(message, code="CONFIG_ERROR")


class ProviderError(AmberClawError):
    """Raised when an LLM provider fails."""
    def __init__(self, message: str, provider: str):
        self.provider = provider
        super().__init__(f"Provider {provider} error: {message}", code="PROVIDER_ERROR")


class SecurityError(AmberClawError):
    """Raised when a security policy is violated."""
    def __init__(self, message: str):
        super().__init__(message, code="SECURITY_VIOLATION")


class MemoryError(AmberClawError):
    """Raised when memory operations fail."""
    def __init__(self, message: str):
        super().__init__(message, code="MEMORY_ERROR")


class SandboxError(AmberClawError):
    """Raised when sandbox operations fail."""
    def __init__(self, message: str):
        super().__init__(message, code="SANDBOX_ERROR")
