"""Task execution and workflow management for agent systems.

This module provides robust task execution capabilities with workflow management,
execution context tracking, and comprehensive error handling for production deployments.
"""

import uuid
import asyncio
import inspect
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union, AsyncGenerator
from datetime import datetime, timezone
from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Task execution status enumeration."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


class TaskPriority(int, Enum):
    """Task priority levels."""
    
    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 15
    CRITICAL = 20


@dataclass
class ExecutionContext:
    """Context information for task execution."""
    
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Execution metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Task information
    task_type: str = "generic"
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: int = 300
    retry_attempts: int = 3
    
    # Context data
    context_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Execution state
    status: ExecutionStatus = ExecutionStatus.PENDING
    current_step: Optional[str] = None
    progress_percentage: float = 0.0
    
    # Error handling
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    
    @property
    def execution_time(self) -> Optional[float]:
        """Calculate execution time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return None
    
    @property
    def is_active(self) -> bool:
        """Check if task is currently active."""
        return self.status in [ExecutionStatus.RUNNING, ExecutionStatus.RETRYING]
    
    @property
    def is_complete(self) -> bool:
        """Check if task has completed (success or failure)."""
        return self.status in [
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMEOUT
        ]
    
    def update_progress(self, step: str, percentage: float) -> None:
        """Update execution progress."""
        self.current_step = step
        self.progress_percentage = max(0.0, min(100.0, percentage))


class ExecutionResult(BaseModel):
    """Result of task execution."""
    
    task_id: str = Field(..., description="Unique task identifier")
    status: ExecutionStatus = Field(..., description="Execution status")
    success: bool = Field(..., description="Whether execution was successful")
    
    # Result data
    result: Any = Field(default=None, description="Task execution result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed error information")
    
    # Timing information
    execution_time: Optional[float] = Field(default=None, description="Execution time in seconds")
    created_at: datetime = Field(..., description="Task creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Task start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Task completion timestamp")
    
    # Progress tracking
    progress_percentage: float = Field(default=100.0, description="Task completion percentage")
    current_step: Optional[str] = Field(default=None, description="Current execution step")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class WorkflowStep(BaseModel):
    """Definition of a workflow step."""
    
    name: str = Field(..., description="Step name")
    description: str = Field(..., description="Step description")
    function: str = Field(..., description="Function name to execute")
    depends_on: List[str] = Field(default_factory=list, description="Step dependencies")
    timeout_seconds: int = Field(default=60, description="Step timeout")
    retry_attempts: int = Field(default=2, description="Step retry attempts")
    required: bool = Field(default=True, description="Whether step is required")
    condition: Optional[str] = Field(default=None, description="Conditional execution expression")


class Workflow(BaseModel):
    """Workflow definition with steps and dependencies."""
    
    name: str = Field(..., description="Workflow name")
    description: str = Field(..., description="Workflow description")
    version: str = Field(default="1.0.0", description="Workflow version")
    steps: List[WorkflowStep] = Field(..., description="Workflow steps")
    parallel_execution: bool = Field(default=False, description="Enable parallel step execution")
    
    def get_executable_steps(self, completed_steps: List[str]) -> List[WorkflowStep]:
        """Get steps that can be executed given completed steps."""
        executable = []
        for step in self.steps:
            if step.name not in completed_steps:
                # Check if all dependencies are satisfied
                if all(dep in completed_steps for dep in step.depends_on):
                    executable.append(step)
        return executable
    
    def validate_dependencies(self) -> bool:
        """Validate workflow step dependencies for cycles."""
        # Simple cycle detection using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(step_name: str) -> bool:
            visited.add(step_name)
            rec_stack.add(step_name)
            
            step = next((s for s in self.steps if s.name == step_name), None)
            if step:
                for dep in step.depends_on:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True
            
            rec_stack.remove(step_name)
            return False
        
        for step in self.steps:
            if step.name not in visited:
                if has_cycle(step.name):
                    return False
        
        return True


class TaskExecutor:
    """Production-ready task executor with workflow management."""
    
    def __init__(self, max_concurrent_tasks: int = 10) -> None:
        """Initialize task executor.
        
        Args:
            max_concurrent_tasks: Maximum number of concurrent tasks
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self._active_tasks: Dict[str, ExecutionContext] = {}
        self._task_futures: Dict[str, asyncio.Task] = {}
        self._workflow_registry: Dict[str, Workflow] = {}
        self._function_registry: Dict[str, Callable] = {}
        self._execution_history: List[ExecutionResult] = []
        
        # Task queue for managing capacity
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._worker_tasks: List[asyncio.Task] = []
        
        # Start worker tasks
        self._start_workers()
    
    def _start_workers(self) -> None:
        """Start worker tasks for processing the task queue."""
        for i in range(self.max_concurrent_tasks):
            worker = asyncio.create_task(self._worker())
            self._worker_tasks.append(worker)
    
    async def _worker(self) -> None:
        """Worker coroutine for processing tasks from the queue."""
        while True:
            try:
                # Get task from queue
                context, func, args, kwargs = await self._task_queue.get()
                
                # Execute task
                await self._execute_task_internal(context, func, args, kwargs)
                
                # Mark task as done
                self._task_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue processing
                print(f"Worker error: {e}")
    
    def register_function(self, name: str, func: Callable) -> None:
        """Register a function for workflow execution.
        
        Args:
            name: Function name
            func: Function to register
        """
        self._function_registry[name] = func
    
    def register_workflow(self, workflow: Workflow) -> None:
        """Register a workflow definition.
        
        Args:
            workflow: Workflow to register
        """
        if not workflow.validate_dependencies():
            raise ValueError(f"Workflow {workflow.name} has circular dependencies")
        
        self._workflow_registry[workflow.name] = workflow
    
    async def execute_task(
        self,
        func: Callable,
        *args,
        context: Optional[ExecutionContext] = None,
        **kwargs
    ) -> ExecutionResult:
        """Execute a single task with comprehensive error handling.
        
        Args:
            func: Function to execute
            *args: Function arguments
            context: Optional execution context
            **kwargs: Function keyword arguments
            
        Returns:
            ExecutionResult containing outcome
        """
        if context is None:
            context = ExecutionContext()
        
        # Set initial status
        context.status = ExecutionStatus.PENDING
        self._active_tasks[context.task_id] = context
        
        try:
            # Add task to queue
            await self._task_queue.put((context, func, args, kwargs))
            
            # Wait for completion
            while not context.is_complete:
                await asyncio.sleep(0.1)
            
            # Create result
            result = ExecutionResult(
                task_id=context.task_id,
                status=context.status,
                success=context.status == ExecutionStatus.COMPLETED,
                result=context.context_data.get("result"),
                error=context.error_message,
                error_details=context.error_details,
                execution_time=context.execution_time,
                created_at=context.created_at,
                started_at=context.started_at,
                completed_at=context.completed_at,
                progress_percentage=context.progress_percentage,
                current_step=context.current_step,
                metadata=context.metadata
            )
            
            # Store in history
            self._execution_history.append(result)
            
            return result
            
        finally:
            # Cleanup
            if context.task_id in self._active_tasks:
                del self._active_tasks[context.task_id]
    
    async def _execute_task_internal(
        self,
        context: ExecutionContext,
        func: Callable,
        args: tuple,
        kwargs: dict
    ) -> None:
        """Internal task execution with retry logic."""
        context.started_at = datetime.now(timezone.utc)
        context.status = ExecutionStatus.RUNNING
        
        for attempt in range(context.retry_attempts + 1):
            try:
                context.retry_count = attempt
                
                if attempt > 0:
                    context.status = ExecutionStatus.RETRYING
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
                # Execute with timeout
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=context.timeout_seconds
                    )
                else:
                    # Run synchronous function in thread pool
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                        timeout=context.timeout_seconds
                    )
                
                # Success
                context.context_data["result"] = result
                context.status = ExecutionStatus.COMPLETED
                context.completed_at = datetime.now(timezone.utc)
                context.progress_percentage = 100.0
                return
                
            except asyncio.TimeoutError:
                context.error_message = f"Task timed out after {context.timeout_seconds} seconds"
                context.status = ExecutionStatus.TIMEOUT
            except Exception as e:
                context.error_message = str(e)
                context.error_details = {
                    "exception_type": type(e).__name__,
                    "attempt": attempt + 1,
                    "max_attempts": context.retry_attempts + 1
                }
                
                if attempt == context.retry_attempts:
                    context.status = ExecutionStatus.FAILED
        
        context.completed_at = datetime.now(timezone.utc)
    
    async def execute_workflow(
        self,
        workflow_name: str,
        inputs: Dict[str, Any],
        context: Optional[ExecutionContext] = None
    ) -> ExecutionResult:
        """Execute a workflow with dependency management.
        
        Args:
            workflow_name: Name of registered workflow
            inputs: Input data for workflow
            context: Optional execution context
            
        Returns:
            ExecutionResult containing workflow outcome
        """
        if context is None:
            context = ExecutionContext(task_type="workflow")
        
        workflow = self._workflow_registry.get(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow {workflow_name} not found")
        
        context.status = ExecutionStatus.RUNNING
        context.started_at = datetime.now(timezone.utc)
        context.context_data["workflow_inputs"] = inputs
        context.context_data["workflow_results"] = {}
        
        completed_steps = []
        step_results = {}
        
        try:
            while len(completed_steps) < len(workflow.steps):
                executable_steps = workflow.get_executable_steps(completed_steps)
                
                if not executable_steps:
                    # Check for required steps that can't be executed
                    remaining_steps = [s for s in workflow.steps if s.name not in completed_steps]
                    required_remaining = [s for s in remaining_steps if s.required]
                    
                    if required_remaining:
                        raise RuntimeError(
                            f"Required steps cannot be executed: {[s.name for s in required_remaining]}"
                        )
                    break
                
                # Execute steps
                if workflow.parallel_execution:
                    # Parallel execution
                    step_tasks = []
                    for step in executable_steps:
                        if self._should_execute_step(step, step_results):
                            task = asyncio.create_task(
                                self._execute_workflow_step(step, inputs, step_results)
                            )
                            step_tasks.append((step, task))
                    
                    # Wait for all steps to complete
                    for step, task in step_tasks:
                        try:
                            result = await task
                            step_results[step.name] = result
                            completed_steps.append(step.name)
                        except Exception as e:
                            if step.required:
                                raise
                            step_results[step.name] = {"error": str(e)}
                            completed_steps.append(step.name)
                
                else:
                    # Sequential execution
                    for step in executable_steps:
                        if self._should_execute_step(step, step_results):
                            try:
                                result = await self._execute_workflow_step(step, inputs, step_results)
                                step_results[step.name] = result
                                completed_steps.append(step.name)
                                
                                # Update progress
                                progress = len(completed_steps) / len(workflow.steps) * 100
                                context.update_progress(step.name, progress)
                                
                            except Exception as e:
                                if step.required:
                                    raise
                                step_results[step.name] = {"error": str(e)}
                                completed_steps.append(step.name)
            
            # Workflow completed successfully
            context.status = ExecutionStatus.COMPLETED
            context.context_data["workflow_results"] = step_results
            context.progress_percentage = 100.0
            
        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error_message = str(e)
            context.error_details = {
                "workflow_name": workflow_name,
                "completed_steps": completed_steps,
                "step_results": step_results
            }
        
        finally:
            context.completed_at = datetime.now(timezone.utc)
        
        return ExecutionResult(
            task_id=context.task_id,
            status=context.status,
            success=context.status == ExecutionStatus.COMPLETED,
            result=context.context_data.get("workflow_results"),
            error=context.error_message,
            error_details=context.error_details,
            execution_time=context.execution_time,
            created_at=context.created_at,
            started_at=context.started_at,
            completed_at=context.completed_at,
            progress_percentage=context.progress_percentage,
            current_step=context.current_step,
            metadata=context.metadata
        )
    
    def _should_execute_step(self, step: WorkflowStep, step_results: Dict[str, Any]) -> bool:
        """Check if a workflow step should be executed based on conditions."""
        if step.condition:
            # Simple condition evaluation (can be extended)
            # For now, just check if condition is "true" or "false"
            if step.condition.lower() == "false":
                return False
            
            # Could implement more complex condition evaluation here
            # using step_results and other context
        
        return True
    
    async def _execute_workflow_step(
        self,
        step: WorkflowStep,
        inputs: Dict[str, Any],
        step_results: Dict[str, Any]
    ) -> Any:
        """Execute a single workflow step."""
        func = self._function_registry.get(step.function)
        if not func:
            raise ValueError(f"Function {step.function} not found in registry")
        
        # Prepare step context
        step_context = {
            "inputs": inputs,
            "step_results": step_results,
            "step_name": step.name
        }
        
        # Execute with step-specific timeout and retry
        for attempt in range(step.retry_attempts + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(step_context),
                        timeout=step.timeout_seconds
                    )
                else:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: func(step_context)),
                        timeout=step.timeout_seconds
                    )
                
                return result
                
            except Exception as e:
                if attempt == step.retry_attempts:
                    raise
                await asyncio.sleep(2 ** attempt)
    
    def get_task_status(self, task_id: str) -> Optional[ExecutionContext]:
        """Get status of an active task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            ExecutionContext if task is active, None otherwise
        """
        return self._active_tasks.get(task_id)
    
    def list_active_tasks(self) -> List[ExecutionContext]:
        """List all active tasks."""
        return list(self._active_tasks.values())
    
    def get_execution_history(self, limit: int = 100) -> List[ExecutionResult]:
        """Get execution history.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of execution results
        """
        return self._execution_history[-limit:]
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel an active task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was cancelled, False if not found
        """
        if task_id in self._task_futures:
            self._task_futures[task_id].cancel()
            
            if task_id in self._active_tasks:
                context = self._active_tasks[task_id]
                context.status = ExecutionStatus.CANCELLED
                context.completed_at = datetime.now(timezone.utc)
            
            return True
        
        return False
    
    async def shutdown(self) -> None:
        """Shutdown the task executor gracefully."""
        # Cancel all worker tasks
        for worker in self._worker_tasks:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        # Cancel any remaining active tasks
        for task_id in list(self._active_tasks.keys()):
            await self.cancel_task(task_id)