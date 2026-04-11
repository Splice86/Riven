"""Tool management for riven - wrapping, timeout handling, etc."""

import asyncio
import functools
from typing import Callable

from pydantic_ai.tools import Tool as PydanticTool, ToolDefinition


def wrap_with_timeout(func: Callable, default_timeout: float) -> Callable:
    """Wrap a tool function to support _timeout parameter.
    
    The LLM can pass _timeout=N to any tool call to override the default timeout.
    
    Args:
        func: The async function to wrap
        default_timeout: Default timeout in seconds
        
    Returns:
        Wrapped function with timeout support
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract timeout from kwargs (LLM can override per-call)
        timeout = kwargs.pop('_timeout', default_timeout)
        
        # Check if original function is async
        if asyncio.iscoroutinefunction(func):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
        else:
            # Sync function - run in executor to allow timeout
            def run_sync():
                return func(*args, **kwargs)
            
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, run_sync),
                timeout=timeout
            )
    
    return wrapper


def make_tool_prepare(default_timeout: float):
    """Create a prepare callback that adds _timeout to tool schema.
    
    Args:
        default_timeout: Default timeout in seconds
        
    Returns:
        Prepare callback function
    """
    async def prepare(ctx, tool_def: ToolDefinition) -> ToolDefinition | None:
        # Add _timeout parameter to the tool definition
        schema = tool_def.parameters_json_schema
        if schema is None:
            schema = {'type': 'object', 'properties': {}}
        
        schema['properties']['_timeout'] = {
            'type': 'integer',
            'description': 'Optional timeout override in seconds for this tool call',
            'default': None
        }
        
        tool_def.parameters_json_schema = schema
        return tool_def
    
    return prepare


def create_tools(module_funcs: list, default_timeout: float) -> list:
    """Create pydantic_ai tools with timeout support.
    
    Args:
        module_funcs: List of (name, function, description) tuples from modules
        default_timeout: Default timeout for tools in seconds
        
    Returns:
        List of PydanticTool instances with timeout handling
    """
    tools = []
    
    for name, func, desc in module_funcs:
        # Wrap to support _timeout override
        wrapped = wrap_with_timeout(func, default_timeout)
        
        # Add _timeout to tool schema via prepare callback
        tool = PydanticTool(
            wrapped,
            timeout=float(default_timeout),
            prepare=make_tool_prepare(default_timeout)
        )
        tools.append(tool)
    
    return tools