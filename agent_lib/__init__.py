"""Agent Library top-level package.

Exports stable interfaces for core agent components and memory utilities.
"""

from .core import (
    BaseAgent,
    AgentConfig,
    AgentStatus,
    Tool,
    BaseTool,
    FunctionTool,
    APITool,
    ToolConfig,
    ToolRegistry,
    TaskExecutor,
    ExecutionContext,
    ExecutionResult,
    SystemConfig,
    validate_config,
)

from .memory import ShortTermMemory, WorkingMemory

__all__ = [
    # core
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
    # memory
    "ShortTermMemory",
    "WorkingMemory",
]

__version__ = "1.0.0"
