"""Tool system for agent function calling and external integrations.

This module provides a comprehensive tool system that allows agents to interact
with external services, APIs, and functions in a secure and observable manner.
"""

import asyncio
import inspect
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Union, Type
from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field, validator
import httpx


class ToolType(str, Enum):
    """Tool type enumeration."""
    
    FUNCTION = "function"
    API = "api"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    WEB_SCRAPER = "web_scraper"
    CALCULATOR = "calculator"
    SEARCH = "search"
    CUSTOM = "custom"


class ToolStatus(str, Enum):
    """Tool operational status."""
    
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    DEPRECATED = "deprecated"
    MAINTENANCE = "maintenance"


class ToolConfig(BaseModel):
    """Configuration for tool initialization and behavior."""
    
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Tool description and usage")
    tool_type: ToolType = Field(..., description="Type of tool")
    version: str = Field(default="1.0.0", description="Tool version")
    
    # Execution settings
    timeout_seconds: int = Field(default=30, gt=0, description="Tool execution timeout")
    retry_attempts: int = Field(default=2, ge=0, description="Number of retry attempts")
    
    # Security settings
    requires_auth: bool = Field(default=False, description="Whether tool requires authentication")
    allowed_roles: List[str] = Field(default_factory=list, description="Allowed user roles")
    rate_limit_per_minute: int = Field(default=60, gt=0, description="Rate limit per minute")
    
    # API-specific settings (if applicable)
    base_url: Optional[str] = Field(default=None, description="Base URL for API tools")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    headers: Dict[str, str] = Field(default_factory=dict, description="Default headers")
    
    # Validation settings
    validate_inputs: bool = Field(default=True, description="Enable input validation")
    validate_outputs: bool = Field(default=True, description="Enable output validation")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
        extra = "forbid"


class ToolParameter(BaseModel):
    """Tool parameter definition."""
    
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (str, int, float, bool, list, dict)")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Whether parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value")
    enum_values: Optional[List[Any]] = Field(default=None, description="Allowed enum values")
    
    @validator("type")
    def validate_type(cls, v):
        """Validate parameter type."""
        valid_types = ["str", "int", "float", "bool", "list", "dict", "any"]
        if v not in valid_types:
            raise ValueError(f"Invalid type: {v}. Valid types: {valid_types}")
        return v


class ToolSchema(BaseModel):
    """Tool schema definition for function calling."""
    
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: List[ToolParameter] = Field(..., description="Tool parameters")
    
    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description
            }
            
            if param.enum_values:
                properties[param.name]["enum"] = param.enum_values
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class ToolResult(BaseModel):
    """Tool execution result."""
    
    success: bool = Field(..., description="Whether execution was successful")
    result: Any = Field(default=None, description="Tool execution result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time: float = Field(..., description="Execution time in seconds")
    tool_name: str = Field(..., description="Name of executed tool")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BaseTool(ABC):
    """Abstract base class for all tool implementations."""
    
    def __init__(self, config: ToolConfig) -> None:
        """Initialize tool with configuration.
        
        Args:
            config: Tool configuration
        """
        self.config = config
        self.status = ToolStatus.AVAILABLE
        self.usage_count = 0
        self.last_used: Optional[datetime] = None
        self.last_error: Optional[str] = None
        
        # Initialize HTTP client for API tools
        if config.tool_type == ToolType.API:
            self._http_client = httpx.AsyncClient(
                base_url=config.base_url,
                headers=config.headers,
                timeout=config.timeout_seconds
            )
        else:
            self._http_client = None
    
    @property
    @abstractmethod
    def schema(self) -> ToolSchema:
        """Get tool schema for function calling."""
        pass
    
    @abstractmethod
    async def _execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            Tool execution result
        """
        pass
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute tool with comprehensive error handling and observability.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult containing execution outcome
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Validate inputs if enabled
            if self.config.validate_inputs:
                self._validate_inputs(kwargs)
            
            # Check tool availability
            if self.status != ToolStatus.AVAILABLE:
                raise ToolExecutionError(f"Tool {self.config.name} is not available")
            
            # Execute tool
            result = await asyncio.wait_for(
                self._execute(**kwargs),
                timeout=self.config.timeout_seconds
            )
            
            # Validate outputs if enabled
            if self.config.validate_outputs:
                result = self._validate_outputs(result)
            
            # Update usage statistics
            self.usage_count += 1
            self.last_used = datetime.now(timezone.utc)
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            return ToolResult(
                success=True,
                result=result,
                execution_time=execution_time,
                tool_name=self.config.name,
                metadata={
                    "usage_count": self.usage_count,
                    "tool_type": self.config.tool_type,
                    "version": self.config.version
                }
            )
            
        except Exception as e:
            self.last_error = str(e)
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
                tool_name=self.config.name,
                metadata={
                    "error_type": type(e).__name__,
                    "tool_type": self.config.tool_type
                }
            )
    
    def _validate_inputs(self, kwargs: Dict[str, Any]) -> None:
        """Validate input parameters against schema."""
        schema = self.schema
        
        # Check required parameters
        for param in schema.parameters:
            if param.required and param.name not in kwargs:
                raise ToolValidationError(f"Required parameter '{param.name}' missing")
            
            if param.name in kwargs:
                value = kwargs[param.name]
                
                # Type validation (basic)
                if param.type == "int" and not isinstance(value, int):
                    try:
                        kwargs[param.name] = int(value)
                    except (ValueError, TypeError):
                        raise ToolValidationError(f"Parameter '{param.name}' must be integer")
                
                elif param.type == "float" and not isinstance(value, (int, float)):
                    try:
                        kwargs[param.name] = float(value)
                    except (ValueError, TypeError):
                        raise ToolValidationError(f"Parameter '{param.name}' must be float")
                
                elif param.type == "bool" and not isinstance(value, bool):
                    if isinstance(value, str):
                        kwargs[param.name] = value.lower() in ("true", "1", "yes", "on")
                    else:
                        raise ToolValidationError(f"Parameter '{param.name}' must be boolean")
                
                # Enum validation
                if param.enum_values and value not in param.enum_values:
                    raise ToolValidationError(
                        f"Parameter '{param.name}' must be one of {param.enum_values}"
                    )
    
    def _validate_outputs(self, result: Any) -> Any:
        """Validate output results."""
        # Basic validation - can be extended by subclasses
        return result
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform tool health check."""
        return {
            "tool_name": self.config.name,
            "status": self.status.value,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "last_error": self.last_error,
            "configuration": {
                "tool_type": self.config.tool_type,
                "version": self.config.version,
                "timeout": self.config.timeout_seconds
            }
        }
    
    async def cleanup(self) -> None:
        """Cleanup tool resources."""
        if self._http_client:
            await self._http_client.aclose()


class FunctionTool(BaseTool):
    """Tool wrapper for Python functions."""
    
    def __init__(self, config: ToolConfig, func: Callable) -> None:
        """Initialize function tool.
        
        Args:
            config: Tool configuration
            func: Python function to wrap
        """
        super().__init__(config)
        self.func = func
        self._schema = self._generate_schema()
    
    def _generate_schema(self) -> ToolSchema:
        """Generate schema from function signature."""
        sig = inspect.signature(self.func)
        parameters = []
        
        for name, param in sig.parameters.items():
            param_type = "any"
            required = param.default == inspect.Parameter.empty
            default = None if required else param.default
            
            # Simple type inference
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == str:
                    param_type = "str"
                elif param.annotation == int:
                    param_type = "int"
                elif param.annotation == float:
                    param_type = "float"
                elif param.annotation == bool:
                    param_type = "bool"
                elif param.annotation == list:
                    param_type = "list"
                elif param.annotation == dict:
                    param_type = "dict"
            
            parameters.append(ToolParameter(
                name=name,
                type=param_type,
                description=f"Parameter {name}",
                required=required,
                default=default
            ))
        
        return ToolSchema(
            name=self.config.name,
            description=self.config.description,
            parameters=parameters
        )
    
    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._schema
    
    async def _execute(self, **kwargs) -> Any:
        """Execute the wrapped function."""
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        else:
            # Run synchronous function in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: self.func(**kwargs))


class APITool(BaseTool):
    """Tool for making HTTP API calls."""
    
    def __init__(self, config: ToolConfig, method: str = "GET") -> None:
        """Initialize API tool.
        
        Args:
            config: Tool configuration
            method: HTTP method (GET, POST, PUT, DELETE)
        """
        super().__init__(config)
        self.method = method.upper()
        
        if not config.base_url:
            raise ToolConfigurationError("API tool requires base_url in configuration")
    
    @property
    def schema(self) -> ToolSchema:
        """Get API tool schema."""
        parameters = [
            ToolParameter(
                name="endpoint",
                type="str",
                description="API endpoint path",
                required=True
            ),
            ToolParameter(
                name="params",
                type="dict",
                description="Query parameters",
                required=False,
                default={}
            ),
            ToolParameter(
                name="data",
                type="dict",
                description="Request body data",
                required=False,
                default={}
            ),
            ToolParameter(
                name="headers",
                type="dict",
                description="Additional headers",
                required=False,
                default={}
            )
        ]
        
        return ToolSchema(
            name=self.config.name,
            description=self.config.description,
            parameters=parameters
        )
    
    async def _execute(self, **kwargs) -> Any:
        """Execute API call."""
        endpoint = kwargs.get("endpoint", "")
        params = kwargs.get("params", {})
        data = kwargs.get("data", {})
        headers = kwargs.get("headers", {})
        
        # Merge with default headers
        all_headers = {**self.config.headers, **headers}
        
        # Add authentication if configured
        if self.config.api_key:
            all_headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        response = await self._http_client.request(
            method=self.method,
            url=endpoint,
            params=params,
            json=data if data else None,
            headers=all_headers
        )
        
        response.raise_for_status()
        
        # Try to parse JSON, fallback to text
        try:
            return response.json()
        except json.JSONDecodeError:
            return response.text


class ToolRegistry:
    """Registry for managing and discovering tools."""
    
    def __init__(self) -> None:
        """Initialize tool registry."""
        self._tools: Dict[str, BaseTool] = {}
        self._tool_groups: Dict[str, List[str]] = {}
    
    def register(self, tool: BaseTool, group: Optional[str] = None) -> None:
        """Register a tool in the registry.
        
        Args:
            tool: Tool instance to register
            group: Optional group name for categorization
        """
        self._tools[tool.config.name] = tool
        
        if group:
            if group not in self._tool_groups:
                self._tool_groups[group] = []
            self._tool_groups[group].append(tool.config.name)
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def list_tools(self, group: Optional[str] = None) -> List[str]:
        """List available tools.
        
        Args:
            group: Optional group to filter by
            
        Returns:
            List of tool names
        """
        if group and group in self._tool_groups:
            return self._tool_groups[group]
        return list(self._tools.keys())
    
    def get_schemas(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tool schemas for function calling.
        
        Args:
            group: Optional group to filter by
            
        Returns:
            List of tool schemas in OpenAI format
        """
        tool_names = self.list_tools(group)
        schemas = []
        
        for name in tool_names:
            tool = self._tools[name]
            if tool.status == ToolStatus.AVAILABLE:
                schemas.append(tool.schema.to_openai_schema())
        
        return schemas
    
    async def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name.
        
        Args:
            name: Tool name
            **kwargs: Tool parameters
            
        Returns:
            Tool execution result
        """
        tool = self.get_tool(name)
        if not tool:
            raise ToolNotFoundError(f"Tool '{name}' not found in registry")
        
        return await tool.execute(**kwargs)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all tools."""
        results = {}
        for name, tool in self._tools.items():
            results[name] = await tool.health_check()
        return results
    
    async def cleanup(self) -> None:
        """Cleanup all tools."""
        for tool in self._tools.values():
            await tool.cleanup()


# Convenience functions for tool creation
def create_function_tool(
    name: str,
    description: str,
    func: Callable,
    **config_kwargs
) -> FunctionTool:
    """Create a function tool from a Python function.
    
    Args:
        name: Tool name
        description: Tool description
        func: Python function to wrap
        **config_kwargs: Additional configuration parameters
        
    Returns:
        FunctionTool instance
    """
    config = ToolConfig(
        name=name,
        description=description,
        tool_type=ToolType.FUNCTION,
        **config_kwargs
    )
    return FunctionTool(config, func)


def create_api_tool(
    name: str,
    description: str,
    base_url: str,
    method: str = "GET",
    **config_kwargs
) -> APITool:
    """Create an API tool for HTTP requests.
    
    Args:
        name: Tool name
        description: Tool description
        base_url: API base URL
        method: HTTP method
        **config_kwargs: Additional configuration parameters
        
    Returns:
        APITool instance
    """
    config = ToolConfig(
        name=name,
        description=description,
        tool_type=ToolType.API,
        base_url=base_url,
        **config_kwargs
    )
    return APITool(config, method)


# Custom Exceptions
class ToolError(Exception):
    """Base exception for tool-related errors."""
    pass


class ToolExecutionError(ToolError):
    """Exception raised when tool execution fails."""
    pass


class ToolValidationError(ToolError):
    """Exception raised when tool input/output validation fails."""
    pass


class ToolConfigurationError(ToolError):
    """Exception raised when tool configuration is invalid."""
    pass


class ToolNotFoundError(ToolError):
    """Exception raised when requested tool is not found."""
    pass