"""Shared exceptions for adapter and sync layers (step 3 scaffold)."""


class LangGraphIntegrationError(Exception):
    """Base class for langgraph-integration failures."""

    pass


class McpAdapterError(LangGraphIntegrationError):
    """MCP payload shape or mapping failed in adapter."""

    pass


class LangGraphSyncError(LangGraphIntegrationError):
    """Push to LangGraph (stream, retry, rate limit) failed in sync."""

    pass
