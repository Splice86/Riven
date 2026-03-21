"""Core agentic loop - pydantic_ai implementation."""

import asyncio
import logging
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.tools import Tool as PydanticTool
from openai import AsyncOpenAI

from context import SystemContext
from context import ActivityLog
from modules import ModuleRegistry, get_all_modules

logger = logging.getLogger(__name__)


class Core:
    """Simple agent using pydantic_ai with llama.cpp backend."""

    def __init__(
        self,
        model: str = "llama3",
        system_prompt: str = None,
        llm_url: str = "http://192.168.1.11:8010",
        llm_api_key: str = "sk-dummy",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.model = model
        self.llm_url = llm_url
        self.llm_api_key = llm_api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._modules = ModuleRegistry()
        self._system_context = SystemContext(system_prompt)
        self._activity_log = ActivityLog()
        
        # Auto-register all discovered modules
        for module in get_all_modules():
            self._modules.register(module)

    def _create_agent(self, system_prompt: str) -> Agent:
        """Create a pydantic_ai Agent."""
        client = AsyncOpenAI(base_url=f"{self.llm_url}/v1", api_key=self.llm_api_key)
        provider = OpenAIProvider(openai_client=client)
        model = OpenAIChatModel(model_name=self.model, provider=provider)
        
        # Get functions from registered modules
        module_funcs = self._modules.get_functions()
        tools = [PydanticTool(func) for _, func, _ in module_funcs] if module_funcs else []
        
        return Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools
        )

    async def _run_with_retry(self, system_prompt: str, prompt: str) -> Any:
        """Run a single iteration with retry logic using agent.iter()."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                agent = self._create_agent(system_prompt)
                
                # Use agent.iter() for structured node access
                async with agent.iter(prompt) as agent_run:
                    async for node in agent_run:
                        self._process_node(node)
                    
                    # Get final result
                    result = agent_run.result
                    return result
                    
            except Exception as e:
                last_error = e
                
                logger.warning(f"Retry {attempt + 1}: {e}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        raise last_error

    def _process_node(self, node) -> None:
        """Process a single node from agent.iter()."""
        node_name = type(node).__name__
        
        match node_name:
            case 'UserPromptNode':
                logger.info(f"User: {node.user_prompt}")
            
            case 'ModelRequestNode':
                if node.request and node.request.parts:
                    content = node.request.parts[0].content
                    logger.info(f"LLM: {content}")
            
            case 'CallToolsNode':
                response = node.model_response
                if response and response.parts:
                    for part in response.parts:
                        if hasattr(part, 'content'):
                            logger.info(f"Think: {part.content}")
                        if hasattr(part, 'tool_name'):
                            tool_result = node.tool_call_results.get(part.tool_name)
                            result_str = str(tool_result) if tool_result else "Done"
                            logger.info(f"Tool {part.tool_name}({part.args}): {result_str}")
            
            case 'End':
                logger.info(f"Done: {node.data.output}")

    async def run(self, prompt: str) -> Any:
        """Run the agent with the given prompt."""
        self._activity_log.add_user(prompt)
        
        # Get tag replacements from modules
        replacements = []
        for module in self._modules.all().values():
            if module.get_context and module.tag:
                value = module.get_context()
                replacements.append((module.tag, value))
        
        # Get updated system prompt
        system_prompt = self._system_context.apply_tags(replacements)
        history = self._activity_log.get_history()
        full_prompt = f"Previous conversation:\n{history}\n\nCurrent: {prompt}" if history else prompt
        
        result = await self._run_with_retry(system_prompt, full_prompt)
        self._activity_log.add_assistant(str(result.output))
        
        return result


async def main():
    """Interactive REPL for the agent."""
    system_prompt = """You are riven, a helpful AI assistant.

Current time: {{time}}

Open documents:
{{documents}}
"""

    core = Core(
        system_prompt=system_prompt,
        model="llama3",
        llm_url="http://192.168.1.11:8010",
    )
    
    print("Riven agent ready. Type 'quit' or 'exit' to stop.\n")
    
    while True:
        try:
            prompt = input("> ").strip()
            
            if prompt.lower() in ('quit', 'exit'):
                print("Goodbye!")
                break
            
            if not prompt:
                continue
            
            result = await core.run(prompt)
            print(f"\n{result.output}\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    # Suppress HTTP request logging from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
