"""Core agent components for production-ready multi-agent systems.

This module provides the foundational classes and utilities for building
scalable, secure, and observable agent systems.
"""

from .agent import BaseAgent, AgentConfig, AgentStatus
from .tool import (
    BaseTool,
    FunctionTool,
    APITool,
    ToolConfig,
    ToolRegistry,
)
from .executor import TaskExecutor, ExecutionContext, ExecutionResult
from .config import SystemConfig, validate_config

# Backward-compatible alias for users importing `Tool` as a base interface
Tool = BaseTool

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentStatus",
    "Tool",
    "BaseTool",
    "FunctionTool",
    "APITool",
    "ToolConfig",
    "ToolRegistry",
    "TaskExecutor",
    "ExecutionContext",
    "ExecutionResult",
    "SystemConfig",
    "validate_config",
]

__version__ = "1.0.0"
