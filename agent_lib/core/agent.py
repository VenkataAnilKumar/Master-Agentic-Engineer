"""Base agent implementation for production-ready multi-agent systems.

This module provides the foundational BaseAgent class that all agents should inherit from,
along with configuration models and status tracking for enterprise deployment.
"""

import uuid
import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone

from pydantic import BaseModel, Field, validator
from tenacity import retry, stop_after_attempt, wait_exponential


class AgentStatus(str, Enum):
	"""Agent operational status enumeration."""
    
	INITIALIZING = "initializing"
	READY = "ready"
	BUSY = "busy"
	ERROR = "error"
	STOPPED = "stopped"
	MAINTENANCE = "maintenance"


class AgentConfig(BaseModel):
	"""Configuration model for agent initialization and behavior.
    
	This model defines all configurable parameters for agent operation,
	including LLM settings, execution limits, and operational parameters.
	"""
    
	# Agent Identity
	name: str = Field(..., description="Unique agent identifier")
	description: str = Field(default="", description="Agent description and purpose")
	version: str = Field(default="1.0.0", description="Agent version")
    
	# LLM Configuration
	model_name: str = Field(default="gpt-4", description="LLM model to use")
	temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature")
	max_tokens: int = Field(default=4096, gt=0, description="Maximum tokens per response")
    
	# Execution Parameters
	max_iterations: int = Field(default=10, ge=1, le=100, description="Maximum reasoning iterations")
	timeout_seconds: int = Field(default=300, gt=0, description="Task execution timeout")
	retry_attempts: int = Field(default=3, ge=0, description="Number of retry attempts")
    
	# Resource Limits
	max_memory_mb: int = Field(default=1024, gt=0, description="Maximum memory usage in MB")
	max_concurrent_tasks: int = Field(default=5, ge=1, description="Maximum concurrent tasks")
    
	# Security Settings
	enable_security: bool = Field(default=True, description="Enable security features")
	allowed_domains: List[str] = Field(default_factory=list, description="Allowed domains for external calls")
	rate_limit_per_minute: int = Field(default=60, gt=0, description="Rate limit per minute")
    
	# Observability
	enable_metrics: bool = Field(default=True, description="Enable metrics collection")
	enable_tracing: bool = Field(default=True, description="Enable distributed tracing")
	log_level: str = Field(default="INFO", description="Logging level")
    
	@validator("model_name")
	def validate_model_name(cls, v):
		"""Validate supported model names."""
		supported_models = [
			"gpt-4", "gpt-4-turbo", "gpt-3.5-turbo",
			"claude-3-sonnet", "claude-3-haiku",
			"gemini-pro", "llama-2-70b"
		]
		if v not in supported_models:
			raise ValueError(f"Model {v} not supported. Supported models: {supported_models}")
		return v
    
	@validator("log_level")
	def validate_log_level(cls, v):
		"""Validate logging level."""
		valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
		if v.upper() not in valid_levels:
			raise ValueError(f"Invalid log level: {v}. Valid levels: {valid_levels}")
		return v.upper()
    
	class Config:
		"""Pydantic configuration."""
		frozen = True
		extra = "forbid"
		use_enum_values = True


class AgentMetrics(BaseModel):
	"""Agent performance and operational metrics."""
    
	tasks_completed: int = Field(default=0, description="Total tasks completed")
	tasks_failed: int = Field(default=0, description="Total tasks failed")
	average_execution_time: float = Field(default=0.0, description="Average execution time in seconds")
	memory_usage_mb: float = Field(default=0.0, description="Current memory usage in MB")
	cpu_usage_percent: float = Field(default=0.0, description="Current CPU usage percentage")
	last_activity: Optional[datetime] = Field(default=None, description="Last activity timestamp")
    
	@property
	def success_rate(self) -> float:
		"""Calculate task success rate."""
		total_tasks = self.tasks_completed + self.tasks_failed
		return (self.tasks_completed / total_tasks * 100) if total_tasks > 0 else 0.0


class BaseAgent(ABC):
	"""Abstract base class for all agent implementations.
    
	This class provides the foundational functionality that all agents should have,
	including configuration management, status tracking, error handling, and
	observability features for production deployment.
    
	Example:
		```python
		class ResearchAgent(BaseAgent):
			async def _execute_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
				# Implement specific agent logic
				result = await self._perform_research(task)
				return {"result": result, "metadata": {"sources": 5}}
        
		config = AgentConfig(name="research_agent", model_name="gpt-4")
		agent = ResearchAgent(config)
		result = await agent.execute("Analyze market trends for Q4 2024")
		```
	"""
    
	def __init__(self, config: AgentConfig) -> None:
		"""Initialize agent with configuration.
        
		Args:
			config: Agent configuration parameters
            
		Raises:
			ValueError: If configuration is invalid
			RuntimeError: If initialization fails
		"""
		self.config = config
		self.agent_id = str(uuid.uuid4())
		self.status = AgentStatus.INITIALIZING
		self.metrics = AgentMetrics()
		self.created_at = datetime.now(timezone.utc)
		self.last_error: Optional[str] = None
        
		# Setup logging
		self.logger = self._setup_logging()
        
		# Initialize components
		self._running_tasks: Dict[str, asyncio.Task] = {}
		self._shutdown_event = asyncio.Event()
        
		# Complete initialization
		self._post_init()
		self.status = AgentStatus.READY
        
		self.logger.info(
			f"Agent {self.config.name} ({self.agent_id}) initialized successfully",
			extra={
				"agent_id": self.agent_id,
				"agent_name": self.config.name,
				"config": self.config.dict()
			}
		)
    
	def _setup_logging(self) -> logging.Logger:
		"""Setup structured logging for the agent."""
		logger = logging.getLogger(f"agent.{self.config.name}")
		logger.setLevel(getattr(logging, self.config.log_level))
        
		if not logger.handlers:
			handler = logging.StreamHandler()
			formatter = logging.Formatter(
				'%(asctime)s - %(name)s - %(levelname)s - %(message)s'
			)
			handler.setFormatter(formatter)
			logger.addHandler(handler)
        
		return logger
    
	def _post_init(self) -> None:
		"""Post-initialization hook for subclasses to override."""
		pass
    
	@property
	def is_healthy(self) -> bool:
		"""Check if agent is in a healthy state."""
		return self.status in [AgentStatus.READY, AgentStatus.BUSY]
    
	@property
	def can_accept_tasks(self) -> bool:
		"""Check if agent can accept new tasks."""
		return (
			self.status == AgentStatus.READY and
			len(self._running_tasks) < self.config.max_concurrent_tasks
		)
    
	async def execute(
		self, 
		task: str, 
		context: Optional[Dict[str, Any]] = None,
		priority: int = 0
	) -> Dict[str, Any]:
		"""Execute a task with comprehensive error handling and observability.
        
		Args:
			task: Task description or instruction
			context: Optional context information
			priority: Task priority (higher values = higher priority)
            
		Returns:
			Dictionary containing result and execution metadata
            
		Raises:
			AgentExecutionError: If task execution fails
			AgentBusyError: If agent cannot accept new tasks
			AgentTimeoutError: If execution exceeds timeout
		"""
		if not self.can_accept_tasks:
			raise AgentBusyError(f"Agent {self.config.name} cannot accept new tasks")
        
		task_id = str(uuid.uuid4())
		start_time = datetime.now(timezone.utc)
        
		self.logger.info(
			f"Starting task execution: {task_id}",
			extra={
				"task_id": task_id,
				"task": task,
				"context": context,
				"priority": priority
			}
		)
        
		self.status = AgentStatus.BUSY
        
		try:
			# Execute task with timeout and retry logic
			result = await self._execute_with_retry(task, context or {}, task_id)
            
			# Update metrics
			execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
			self.metrics.tasks_completed += 1
			self.metrics.last_activity = datetime.now(timezone.utc)
			self._update_average_execution_time(execution_time)
            
			self.logger.info(
				f"Task completed successfully: {task_id}",
				extra={
					"task_id": task_id,
					"execution_time": execution_time,
					"success": True
				}
			)
            
			return {
				"task_id": task_id,
				"result": result,
				"success": True,
				"execution_time": execution_time,
				"agent_id": self.agent_id,
				"timestamp": start_time.isoformat()
			}
            
		except Exception as e:
			# Update error metrics
			self.metrics.tasks_failed += 1
			self.last_error = str(e)
			execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
			self.logger.error(
				f"Task execution failed: {task_id}",
				extra={
					"task_id": task_id,
					"error": str(e),
					"execution_time": execution_time,
					"success": False
				},
				exc_info=True
			)
            
			raise AgentExecutionError(f"Task execution failed: {e}") from e
            
		finally:
			self.status = AgentStatus.READY
			if task_id in self._running_tasks:
				del self._running_tasks[task_id]
    
	@retry(
		stop=stop_after_attempt(3),
		wait=wait_exponential(multiplier=1, min=4, max=10)
	)
	async def _execute_with_retry(
		self, 
		task: str, 
		context: Dict[str, Any],
		task_id: str
	) -> Dict[str, Any]:
		"""Execute task with retry logic."""
		try:
			return await asyncio.wait_for(
				self._execute_task(task, context),
				timeout=self.config.timeout_seconds
			)
		except asyncio.TimeoutError:
			raise AgentTimeoutError(
				f"Task execution timed out after {self.config.timeout_seconds} seconds"
			)
    
	@abstractmethod
	async def _execute_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
		"""Execute the actual task logic.
        
		This method must be implemented by subclasses to define the specific
		behavior of the agent.
        
		Args:
			task: Task description or instruction
			context: Context information and parameters
            
		Returns:
			Dictionary containing the task result and any metadata
            
		Raises:
			Any exception that occurs during task execution
		"""
		pass
    
	def _update_average_execution_time(self, execution_time: float) -> None:
		"""Update the rolling average execution time."""
		total_tasks = self.metrics.tasks_completed + self.metrics.tasks_failed
		if total_tasks == 1:
			self.metrics.average_execution_time = execution_time
		else:
			# Simple moving average
			self.metrics.average_execution_time = (
				(self.metrics.average_execution_time * (total_tasks - 1) + execution_time) / total_tasks
			)
    
	async def health_check(self) -> Dict[str, Any]:
		"""Perform comprehensive health check.
        
		Returns:
			Dictionary containing health status and metrics
		"""
		return {
			"agent_id": self.agent_id,
			"name": self.config.name,
			"status": self.status.value,
			"healthy": self.is_healthy,
			"can_accept_tasks": self.can_accept_tasks,
			"metrics": self.metrics.dict(),
			"uptime_seconds": (datetime.now(timezone.utc) - self.created_at).total_seconds(),
			"running_tasks": len(self._running_tasks),
			"last_error": self.last_error,
			"configuration": {
				"model": self.config.model_name,
				"max_concurrent_tasks": self.config.max_concurrent_tasks,
				"timeout_seconds": self.config.timeout_seconds
			}
		}
    
	async def shutdown(self, graceful: bool = True) -> None:
		"""Shutdown the agent gracefully or forcefully.
        
		Args:
			graceful: If True, wait for running tasks to complete
		"""
		self.logger.info(f"Shutting down agent {self.config.name}")
		self.status = AgentStatus.STOPPED
        
		if graceful and self._running_tasks:
			self.logger.info(f"Waiting for {len(self._running_tasks)} tasks to complete")
			await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
		else:
			# Cancel all running tasks
			for task in self._running_tasks.values():
				task.cancel()
        
		self._shutdown_event.set()
		self.logger.info(f"Agent {self.config.name} shutdown complete")
    
	def __repr__(self) -> str:
		"""String representation of the agent."""
		return (
			f"<{self.__class__.__name__}("
			f"id={self.agent_id[:8]}..., "
			f"name={self.config.name}, "
			f"status={self.status.value})>"
		)


# Custom Exceptions
class AgentError(Exception):
	"""Base exception for agent-related errors."""
	pass


class AgentExecutionError(AgentError):
	"""Exception raised when agent task execution fails."""
	pass


class AgentBusyError(AgentError):
	"""Exception raised when agent is too busy to accept new tasks."""
	pass


class AgentTimeoutError(AgentError):
	"""Exception raised when agent task execution times out."""
	pass


class AgentConfigurationError(AgentError):
	"""Exception raised when agent configuration is invalid."""
	pass
