"""Short-term memory implementation for agents.

This module provides working memory capabilities for agents to maintain
context during task execution and conversation flows.
"""

import time
import asyncio
from collections import OrderedDict, defaultdict
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field


class MemoryItemType(str, Enum):
    """Types of memory items."""
    
    CONVERSATION = "conversation"
    TASK = "task"
    OBSERVATION = "observation"
    ACTION = "action"
    RESULT = "result"
    CONTEXT = "context"
    METADATA = "metadata"


class MemoryPriority(int, Enum):
    """Memory item priority levels."""
    
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15


@dataclass
class MemoryItem:
    """Individual memory item with metadata."""
    
    id: str
    content: Any
    item_type: MemoryItemType
    priority: "MemoryPriority" = MemoryPriority.NORMAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: Optional[int] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if memory item has expired."""
        if self.ttl_seconds is None:
            return False
        
        elapsed = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return elapsed > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        """Get age of memory item in seconds."""
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()
    
    def access(self) -> None:
        """Mark item as accessed."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)


class ShortTermMemory:
    """Short-term memory implementation with LRU eviction and TTL support.
    
    This class provides working memory for agents with automatic cleanup,
    priority-based retention, and efficient retrieval mechanisms.
    """
    
    def __init__(
        self,
        capacity: int = 1000,
        default_ttl_seconds: int = 3600,  # 1 hour
        cleanup_interval_seconds: int = 300,  # 5 minutes
        enable_compression: bool = True
    ) -> None:
        """Initialize short-term memory.
        
        Args:
            capacity: Maximum number of items to store
            default_ttl_seconds: Default TTL for items
            cleanup_interval_seconds: Interval for automatic cleanup
            enable_compression: Enable memory compression
        """
        self.capacity = capacity
        self.default_ttl_seconds = default_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.enable_compression = enable_compression
        
        # Storage
        self._items: OrderedDict[str, MemoryItem] = OrderedDict()
        self._type_index: Dict[MemoryItemType, List[str]] = defaultdict(list)
        self._tag_index: Dict[str, List[str]] = defaultdict(list)
        self._priority_queues: Dict[MemoryPriority, List[str]] = defaultdict(list)
        
        # Statistics
        self._access_count = 0
        self._hit_count = 0
        self._eviction_count = 0
        self._last_cleanup = datetime.now(timezone.utc)
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue
                print(f"Memory cleanup error: {e}")
    
    async def store(
        self,
        item_id: str,
        content: Any,
        item_type: MemoryItemType = MemoryItemType.CONTEXT,
        priority: MemoryPriority = MemoryPriority.NORMAL,
        ttl_seconds: Optional[int] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store an item in short-term memory.
        
        Args:
            item_id: Unique identifier for the item
            content: Content to store
            item_type: Type of memory item
            priority: Priority level
            ttl_seconds: Time-to-live in seconds
            tags: Optional tags for categorization
            metadata: Optional metadata
            
        Returns:
            True if stored successfully
        """
        # Remove existing item if present
        if item_id in self._items:
            await self._remove_item(item_id)
        
        # Check capacity and evict if necessary
        if len(self._items) >= self.capacity:
            await self._evict_items()
        
        # Create memory item
        item = MemoryItem(
            id=item_id,
            content=content,
            item_type=item_type,
            priority=priority,
            ttl_seconds=ttl_seconds or self.default_ttl_seconds,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        # Store item
        self._items[item_id] = item
        self._items.move_to_end(item_id)
        
        # Update indexes
        self._type_index[item_type].append(item_id)
        for tag in item.tags:
            self._tag_index[tag].append(item_id)
        self._priority_queues[priority].append(item_id)
        
        return True
    
    async def retrieve(
        self,
        item_id: str,
        mark_accessed: bool = True
    ) -> Optional[MemoryItem]:
        """Retrieve an item from memory.
        
        Args:
            item_id: Item identifier
            mark_accessed: Whether to mark as accessed
            
        Returns:
            MemoryItem if found, None otherwise
        """
        self._access_count += 1
        
        item = self._items.get(item_id)
        if item is None:
            return None
        
        # Check if expired
        if item.is_expired:
            await self._remove_item(item_id)
            return None
        
        self._hit_count += 1
        
        if mark_accessed:
            item.access()
            # Move to end (most recently used)
            self._items.move_to_end(item_id)
        
        return item
    
    async def retrieve_by_type(
        self,
        item_type: MemoryItemType,
        limit: Optional[int] = None
    ) -> List[MemoryItem]:
        """Retrieve items by type.
        
        Args:
            item_type: Type of items to retrieve
            limit: Maximum number of items to return
            
        Returns:
            List of memory items
        """
        item_ids = self._type_index.get(item_type, [])
        items = []
        
        for item_id in item_ids:
            item = await self.retrieve(item_id, mark_accessed=False)
            if item is not None:
                items.append(item)
        
        # Sort by priority and timestamp
        items.sort(key=lambda x: (x.priority.value, x.timestamp), reverse=True)
        
        if limit:
            items = items[:limit]
        
        return items
    
    async def retrieve_by_tags(
        self,
        tags: List[str],
        match_all: bool = True,
        limit: Optional[int] = None
    ) -> List[MemoryItem]:
        """Retrieve items by tags.
        
        Args:
            tags: Tags to search for
            match_all: Whether all tags must match (AND) or any (OR)
            limit: Maximum number of items to return
            
        Returns:
            List of memory items
        """
        if not tags:
            return []
        
        item_sets = [set(self._tag_index.get(tag, [])) for tag in tags]
        
        if match_all:
            # Intersection of all tag sets
            matching_ids = set.intersection(*item_sets) if item_sets else set()
        else:
            # Union of all tag sets
            matching_ids = set.union(*item_sets) if item_sets else set()
        
        items = []
        for item_id in matching_ids:
            item = await self.retrieve(item_id, mark_accessed=False)
            if item is not None:
                items.append(item)
        
        # Sort by priority and timestamp
        items.sort(key=lambda x: (x.priority.value, x.timestamp), reverse=True)
        
        if limit:
            items = items[:limit]
        
        return items
    
    async def search(
        self,
        query: str,
        item_types: Optional[List[MemoryItemType]] = None,
        limit: Optional[int] = None
    ) -> List[MemoryItem]:
        """Search memory content.
        
        Args:
            query: Search query string
            item_types: Optional filter by item types
            limit: Maximum number of results
            
        Returns:
            List of matching memory items
        """
        query_lower = query.lower()
        matching_items = []
        
        for item in self._items.values():
            if item.is_expired:
                continue
            
            if item_types and item.item_type not in item_types:
                continue
            
            # Simple text search in content
            content_str = str(item.content).lower()
            if query_lower in content_str:
                matching_items.append(item)
                continue
            
            # Search in tags
            if any(query_lower in tag.lower() for tag in item.tags):
                matching_items.append(item)
                continue
            
            # Search in metadata
            metadata_str = str(item.metadata).lower()
            if query_lower in metadata_str:
                matching_items.append(item)
        
        # Sort by relevance (simple scoring)
        def relevance_score(item: MemoryItem) -> float:
            score = 0.0
            content_str = str(item.content).lower()
            
            # Exact match bonus
            if query_lower == content_str:
                score += 10.0
            
            # Count occurrences
            score += content_str.count(query_lower) * 2.0
            
            # Priority bonus
            score += item.priority.value * 0.1
            
            # Recency bonus
            age_hours = item.age_seconds / 3600
            score += max(0, 5.0 - age_hours * 0.1)
            
            return score
        
        matching_items.sort(key=relevance_score, reverse=True)
        
        if limit:
            matching_items = matching_items[:limit]
        
        return matching_items
    
    async def update(
        self,
        item_id: str,
        content: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: Optional[MemoryPriority] = None
    ) -> bool:
        """Update an existing memory item.
        
        Args:
            item_id: Item identifier
            content: New content (optional)
            tags: New tags (optional)
            metadata: New metadata (optional)
            priority: New priority (optional)
            
        Returns:
            True if updated successfully
        """
        item = self._items.get(item_id)
        if item is None or item.is_expired:
            return False
        
        # Update indexes if needed
        if tags is not None and tags != item.tags:
            # Remove from old tag indexes
            for tag in item.tags:
                if item_id in self._tag_index[tag]:
                    self._tag_index[tag].remove(item_id)
            
            # Add to new tag indexes
            for tag in tags:
                self._tag_index[tag].append(item_id)
            
            item.tags = tags
        
        if priority is not None and priority != item.priority:
            # Remove from old priority queue
            if item_id in self._priority_queues[item.priority]:
                self._priority_queues[item.priority].remove(item_id)
            
            # Add to new priority queue
            self._priority_queues[priority].append(item_id)
            item.priority = priority
        
        # Update content and metadata
        if content is not None:
            item.content = content
        
        if metadata is not None:
            item.metadata.update(metadata)
        
        # Mark as accessed
        item.access()
        self._items.move_to_end(item_id)
        
        return True
    
    async def remove(self, item_id: str) -> bool:
        """Remove an item from memory.
        
        Args:
            item_id: Item identifier
            
        Returns:
            True if removed successfully
        """
        return await self._remove_item(item_id)
    
    async def _remove_item(self, item_id: str) -> bool:
        """Internal method to remove an item."""
        item = self._items.get(item_id)
        if item is None:
            return False
        
        # Remove from main storage
        del self._items[item_id]
        
        # Remove from indexes
        self._type_index[item.item_type].remove(item_id)
        for tag in item.tags:
            self._tag_index[tag].remove(item_id)
        self._priority_queues[item.priority].remove(item_id)
        
        return True
    
    async def _evict_items(self, target_size: Optional[int] = None) -> int:
        """Evict items to make space.
        
        Args:
            target_size: Target size after eviction
            
        Returns:
            Number of items evicted
        """
        if target_size is None:
            target_size = int(self.capacity * 0.8)  # Evict to 80% capacity
        
        evicted_count = 0
        current_size = len(self._items)
        
        # First, remove expired items
        expired_items = [
            item_id for item_id, item in self._items.items()
            if item.is_expired
        ]
        for item_id in expired_items:
            await self._remove_item(item_id)
            evicted_count += 1
        
        # If still over capacity, use LRU eviction with priority consideration
        items_list = list(self._items.items())
        while len(self._items) > target_size and items_list:
            # Sort by priority (ascending) and last accessed (ascending)
            items_list.sort(
                key=lambda x: (x[1].priority.value, x[1].last_accessed)
            )
            
            # Remove lowest priority, least recently used item
            item_id, _ = items_list.pop(0)
            await self._remove_item(item_id)
            evicted_count += 1
        
        self._eviction_count += evicted_count
        return evicted_count
    
    async def _cleanup_expired(self) -> int:
        """Clean up expired items.
        
        Returns:
            Number of items cleaned up
        """
        expired_items = [
            item_id for item_id, item in self._items.items()
            if item.is_expired
        ]
        
        cleanup_count = 0
        for item_id in expired_items:
            await self._remove_item(item_id)
            cleanup_count += 1
        
        self._last_cleanup = datetime.now(timezone.utc)
        return cleanup_count
    
    async def clear(self) -> None:
        """Clear all memory items."""
        self._items.clear()
        self._type_index.clear()
        self._tag_index.clear()
        self._priority_queues.clear()
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics.
        
        Returns:
            Dictionary containing memory statistics
        """
        total_items = len(self._items)
        expired_items = sum(1 for item in self._items.values() if item.is_expired)
        
        hit_rate = (self._hit_count / self._access_count) if self._access_count > 0 else 0.0
        
        type_distribution = {
            item_type.value: len(item_ids)
            for item_type, item_ids in self._type_index.items()
        }
        
        priority_distribution = {
            priority.value: len(item_ids)
            for priority, item_ids in self._priority_queues.items()
        }
        
        return {
            "total_items": total_items,
            "capacity": self.capacity,
            "utilization": total_items / self.capacity,
            "expired_items": expired_items,
            "access_count": self._access_count,
            "hit_count": self._hit_count,
            "hit_rate": hit_rate,
            "eviction_count": self._eviction_count,
            "last_cleanup": self._last_cleanup.isoformat(),
            "type_distribution": type_distribution,
            "priority_distribution": priority_distribution,
            "memory_usage_mb": self._estimate_memory_usage()
        }
    
    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage in MB (rough approximation)."""
        import sys
        
        total_size = 0
        for item in self._items.values():
            total_size += sys.getsizeof(item.content)
            total_size += sys.getsizeof(item.metadata)
            total_size += sum(sys.getsizeof(tag) for tag in item.tags)
        
        return total_size / (1024 * 1024)  # Convert to MB
    
    async def shutdown(self) -> None:
        """Shutdown memory and cleanup resources."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        await self.clear()


class WorkingMemory(ShortTermMemory):
    """Enhanced short-term memory for active task execution.
    
    This class extends ShortTermMemory with task-specific features like
    conversation history, task context, and structured memory organization.
    """
    
    def __init__(self, **kwargs) -> None:
        """Initialize working memory."""
        super().__init__(**kwargs)
        
        # Task-specific storage
        self._conversation_history: List[Dict[str, Any]] = []
        self._task_context: Dict[str, Any] = {}
        self._active_tools: Dict[str, Any] = {}
        self._reasoning_steps: List[Dict[str, Any]] = []
    
    async def add_conversation_turn(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a conversation turn to working memory.
        
        Args:
            role: Role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Turn identifier
        """
        turn_id = f"turn_{len(self._conversation_history)}"
        turn = {
            "id": turn_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        
        self._conversation_history.append(turn)
        
        # Store in memory
        await self.store(
            item_id=turn_id,
            content=turn,
            item_type=MemoryItemType.CONVERSATION,
            tags=["conversation", role],
            metadata=metadata
        )
        
        return turn_id
    
    async def get_conversation_history(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history.
        
        Args:
            limit: Maximum number of turns to return
            
        Returns:
            List of conversation turns
        """
        history = self._conversation_history.copy()
        if limit:
            history = history[-limit:]
        return history
    
    async def set_task_context(self, key: str, value: Any) -> None:
        """Set task context variable.
        
        Args:
            key: Context key
            value: Context value
        """
        self._task_context[key] = value
        
        await self.store(
            item_id=f"context_{key}",
            content=value,
            item_type=MemoryItemType.CONTEXT,
            tags=["task_context", key],
            metadata={"context_key": key}
        )
    
    async def get_task_context(self, key: Optional[str] = None) -> Any:
        """Get task context variable or entire context.
        
        Args:
            key: Specific context key (optional)
            
        Returns:
            Context value or entire context dictionary
        """
        if key is None:
            return self._task_context.copy()
        return self._task_context.get(key)
    
    async def add_reasoning_step(
        self,
        step_type: str,
        content: str,
        result: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a reasoning step to working memory.
        
        Args:
            step_type: Type of reasoning step
            content: Step description
            result: Step result
            metadata: Optional metadata
            
        Returns:
            Step identifier
        """
        step_id = f"step_{len(self._reasoning_steps)}"
        step = {
            "id": step_id,
            "type": step_type,
            "content": content,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        
        self._reasoning_steps.append(step)
        
        await self.store(
            item_id=step_id,
            content=step,
            item_type=MemoryItemType.ACTION,
            tags=["reasoning", step_type],
            metadata=metadata
        )
        
        return step_id
    
    async def get_reasoning_steps(
        self,
        step_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get reasoning steps.
        
        Args:
            step_type: Filter by step type
            
        Returns:
            List of reasoning steps
        """
        steps = self._reasoning_steps.copy()
        if step_type:
            steps = [step for step in steps if step["type"] == step_type]
        return steps
    
    async def register_active_tool(
        self,
        tool_name: str,
        tool_info: Dict[str, Any]
    ) -> None:
        """Register an active tool.
        
        Args:
            tool_name: Tool name
            tool_info: Tool information
        """
        self._active_tools[tool_name] = tool_info
        
        await self.store(
            item_id=f"tool_{tool_name}",
            content=tool_info,
            item_type=MemoryItemType.METADATA,
            tags=["active_tool", tool_name],
            metadata={"tool_name": tool_name}
        )
    
    async def get_active_tools(self) -> Dict[str, Any]:
        """Get active tools.
        
        Returns:
            Dictionary of active tools
        """
        return self._active_tools.copy()
    
    async def reset_task(self) -> None:
        """Reset task-specific memory while preserving configuration."""
        self._conversation_history.clear()
        self._task_context.clear()
        self._active_tools.clear()
        self._reasoning_steps.clear()
        
        # Remove task-related items from memory
        task_items = await self.retrieve_by_tags(
            ["conversation", "task_context", "reasoning", "active_tool"],
            match_all=False
        )
        
        for item in task_items:
            await self.remove(item.id)
    
    async def get_working_summary(self) -> Dict[str, Any]:
        """Get a summary of working memory state.
        
        Returns:
            Dictionary containing working memory summary
        """
        base_stats = await self.get_statistics()
        
        return {
            **base_stats,
            "conversation_turns": len(self._conversation_history),
            "task_context_items": len(self._task_context),
            "active_tools": len(self._active_tools),
            "reasoning_steps": len(self._reasoning_steps),
            "last_conversation_turn": (
                self._conversation_history[-1]["timestamp"]
                if self._conversation_history else None
            ),
            "last_reasoning_step": (
                self._reasoning_steps[-1]["timestamp"]
                if self._reasoning_steps else None
            )
        }
