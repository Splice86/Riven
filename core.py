"""The core loop - simple, direct LLM calls with function execution.

No pydantic_ai, no dynamic decorators, no framework abstractions.
Just a clean loop: call → parse → execute → repeat.

The Manager owns the database. Core is stateless and session-agnostic.
"""

import asyncio
import inspect
import json
from dataclasses import dataclass
from typing import Callable, AsyncIterator

from openai import AsyncOpenAI

from riven_config import config


# =============================================================================
# Function - plain function descriptor
# =============================================================================

@dataclass
class Function:
    """A callable function exposed to the LLM.

    No decorators, no Pydantic models. Just: name, description,
    a JSON schema for the parameters, and the actual callable.
    """
    name: str
    description: str
    parameters: dict  # JSON schema
    fn: Callable
    timeout: float = 20.0

    @classmethod
    def from_callable(cls, fn: Callable, timeout: float = 20.0) -> "Function":
        """Create a Function from a plain callable."""
        name = fn.__name__
        desc = (fn.__doc__ or "").strip()
        if desc:
            desc = desc.split("\n")[0]

        sig = inspect.signature(fn)
        props = {}
        required = []

        for pname, param in sig.parameters.items():
            if pname.startswith("_"):
                continue

            param_type = "string"
            if param.annotation is not inspect.Parameter.empty:
                if param.annotation in (int,):
                    param_type = "integer"
                elif param.annotation in (float,):
                    param_type = "number"
                elif param.annotation in (bool,):
                    param_type = "boolean"

            props[pname] = {"type": param_type}
            if param.default is inspect.Parameter.empty:
                required.append(pname)

        schema = {"type": "object", "properties": props, "required": required}
        return cls(name=name, description=desc, parameters=schema, fn=fn, timeout=timeout)


# =============================================================================
# Result types
# =============================================================================

@dataclass
class FunctionCall:
    """A parsed function call from the LLM response."""
    id: str
    name: str
    arguments: dict


@dataclass
class FunctionResult:
    """Result of executing a function."""
    call_id: str
    name: str
    content: str
    error: str | None = None


# =============================================================================
# The Core Loop
# =============================================================================

class Core:
    """Pure agentic loop. Stateless, session-agnostic.

    The Manager owns the database and calls Core with a context_callback
    that builds the full API payload on every LLM call. Core executes
    tools, yields events, and repeats — nothing else.

    Flow per turn:
        context_callback() -> {system, messages}
            LLM called
                yields tokens
                if tool_call -> execute -> yield result
                -> next LLM call (callback called again with updated context)
            if no tool_calls -> yield done
    """

    def __init__(
        self,
        llm_url: str,
        llm_model: str,
        llm_api_key: str,
        functions: list[Function],
        max_function_calls: int = 20,
        tool_timeout: float = 20.0,
    ):
        self._client = AsyncOpenAI(base_url=llm_url, api_key=llm_api_key)
        self._llm_model = llm_model
        self._functions = functions
        self._max_function_calls = max_function_calls
        self._tool_timeout = tool_timeout
        self._cancelled = False
        self._func_index: dict[str, Function] = {f.name: f for f in functions}
        self._tools = self._build_tools()

    def cancel(self) -> None:
        """Cancel the current run."""
        self._cancelled = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": f.name,
                    "description": f.description,
                    "parameters": f.parameters,
                },
            }
            for f in self._functions
        ]

    def _parse_calls(self, msg: dict) -> list[FunctionCall]:
        """Extract function calls from an assistant message."""
        calls = []
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", "{}")
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            calls.append(FunctionCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                arguments=arguments or {},
            ))
        return calls

    async def _execute(self, call: FunctionCall) -> FunctionResult:
        """Execute a single function call with timeout."""
        func = self._func_index.get(call.name)
        if not func:
            return FunctionResult(call_id=call.id, name=call.name, content="",
                                  error=f"Unknown function: {call.name}")

        timeout = call.arguments.pop("_timeout", None) or self._tool_timeout

        content, error = "", None
        try:
            result = await asyncio.wait_for(func.fn(**call.arguments), timeout=timeout)
            content = str(result) if result is not None else ""
        except asyncio.TimeoutError:
            error = f"Function timed out after {timeout}s"
        except Exception as e:
            error = str(e)

        return FunctionResult(call_id=call.id, name=call.name, content=content, error=error)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _get_thinking(self, delta) -> str | None:
        """Extract thinking/reasoning content from a streaming delta.

        MiniMax uses 'reasoning_content', OpenRouter uses 'reasoning'.
        """
        if not delta.model_extra:
            return None
        return delta.model_extra.get('reasoning_content') or delta.model_extra.get('reasoning')

    async def run_stream(
        self,
        context_callback: Callable[[str], dict],
    ) -> AsyncIterator[dict]:
        """Run the agent loop, yielding events to the caller.

        Args:
            context_callback: Called before each LLM call. Receives the
                              text streamed so far and returns the full
                              API payload:
                                  {"system": "...", "messages": [...]}
                              The Manager owns this dict and mutates it
                              mid-loop (e.g. appending tool results).

        Yields dicts:
            {"token": str}            - text chunk from the model stream
            {"thinking": str}         - reasoning/thinking chunk (kept separate
                                        from accumulated_text — callers decide
                                        whether to display/store it)
            {"tool_call": {id, name, arguments}} - function call detected
            {"tool_result": {id, name, content, error}} - function result
            {"assistant": dict}       - full assistant message (with tool_calls
                                        if applicable). Append BEFORE tool
                                        results so history is [user, assistant, tool].
            {"done": True}             - loop complete
            {"error": str}            - something went wrong
        """
        self._cancelled = False
        function_call_count = 0
        accumulated_text = ""

        while True:
            if self._cancelled:
                yield {"error": "cancelled"}
                return

            # --- Build API payload ---
            ctx = context_callback(accumulated_text)
            api_messages = []
            if ctx.get("system"):
                api_messages.append({"role": "system", "content": ctx["system"]})
            api_messages.extend(ctx.get("messages", []))

            # --- Call LLM ---
            stream = await self._client.chat.completions.create(
                model=self._llm_model,
                messages=api_messages,
                tools=self._tools or None,
                stream=True,
            )

            # --- Collect the complete assistant message ---
            assistant_msg = {"content": "", "tool_calls": []}
            thinking_buffer = ""

            async for chunk in stream:
                if self._cancelled:
                    yield {"error": "cancelled"}
                    return

                delta = chunk.choices[0].delta

                # Extract thinking, buffer it
                thinking = self._get_thinking(delta)
                if thinking:
                    thinking_buffer += thinking
                    continue

                # Non-thinking delta — flush any buffered thinking first
                if thinking_buffer:
                    yield {"thinking": thinking_buffer}
                    thinking_buffer = ""

                if delta.content:
                    accumulated_text += delta.content
                    yield {"token": delta.content}
                    assistant_msg["content"] += delta.content

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index or 0
                        while len(assistant_msg["tool_calls"]) <= idx:
                            assistant_msg["tool_calls"].append({"id": "", "function": {"name": "", "arguments": ""}})
                        tc = assistant_msg["tool_calls"][idx]
                        if tc_delta.id:
                            tc["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tc["function"]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tc["function"]["arguments"] += tc_delta.function.arguments

            # --- Flush any remaining thinking at end of stream ---
            if thinking_buffer:
                yield {"thinking": thinking_buffer}

            # --- Parse ---
            calls = self._parse_calls(assistant_msg)

            # --- No tool calls — yield assistant, then done ---
            if not calls:
                assistant_msg["role"] = "assistant"
                yield {"assistant": assistant_msg}
                yield {"done": True}
                return

            # --- Execute all calls, collect results ---
            results: list[FunctionResult] = []
            for call in calls:
                if self._cancelled:
                    yield {"error": "cancelled"}
                    return

                function_call_count += 1
                if function_call_count > self._max_function_calls:
                    yield {"error": f"Max function calls reached ({self._max_function_calls})"}
                    return

                yield {"tool_call": {"id": call.id, "name": call.name, "arguments": call.arguments}}
                results.append(await self._execute(call))

            # --- Yield assistant message FIRST so harness gets ordering right ---
            assistant_msg["role"] = "assistant"
            yield {"assistant": assistant_msg}

            # --- Then yield tool results ---
            for result in results:
                yield {"tool_result": {
                    "id": result.call_id, "name": result.name,
                    "content": result.content, "error": result.error,
                }}


# =============================================================================
# TEST HARNESS
# =============================================================================

if __name__ == "__main__":
    import time

    async def get_time() -> str:
        """Return the current time."""
        return time.strftime("%Y-%m-%d %H:%M:%S")

    core = Core(
        llm_url=config.get("llm.primary.url", "http://127.0.0.1:8000/v1"),
        llm_model=config.get("llm.primary.model", "lukealonso/MiniMax-M2.7-NVFP4"),
        llm_api_key=config.get("llm.primary.api_key", "sk-dummy"),
        functions=[Function.from_callable(get_time)],
    )

    SYSTEM = """You are a helpful assistant. Use the get_time tool if asked.

Available tools:
- get_time() -> str (returns current time as YYYY-MM-DD HH:MM:SS)
"""

    context = {"system": SYSTEM, "messages": []}

    def context_callback(accumulated_text: str) -> dict:
        return context

    async def main():
        print("=== Core === (quit to exit)\n")
        while True:
            prompt = input("> ").strip()
            if prompt.lower() in ("q", "quit"):
                break

            context["messages"].append({"role": "user", "content": prompt})

            pending_tool = None

            async for event in core.run_stream(context_callback=context_callback):
                if "token" in event:
                    print(event["token"], end="", flush=True)
                elif "thinking" in event:
                    print(f"\n<think>\n{event['thinking']}\n</think>", end="", flush=True)
                elif "tool_call" in event:
                    tc = event["tool_call"]
                    args_str = json.dumps(tc["arguments"]) if tc["arguments"] else "{}"
                    pending_tool = {"name": tc["name"], "args": args_str}
                elif "tool_result" in event:
                    r = event["tool_result"]
                    context["messages"].append({
                        "role": "tool",
                        "tool_call_id": r["id"],
                        "content": r["content"],
                    })
                    if pending_tool:
                        print(f"\n<tool>{pending_tool['name']}{pending_tool['args']}</tool>\n<result>{r['content']}</result>", flush=True)
                        pending_tool = None
                    else:
                        print(f"\n<result>{r['content']}</result>", flush=True)
                elif "assistant" in event:
                    context["messages"].append(event["assistant"])
                elif "done" in event:
                    print()
                elif "error" in event:
                    print(f"\n[Error: {event['error']}]")

    asyncio.run(main())
