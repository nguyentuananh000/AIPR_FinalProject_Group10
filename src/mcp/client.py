import json
import sys
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters

from ..agent.react_loop import react_agent


PROJECT_ROOT = Path(__file__).resolve().parents[2]


async def run_with_mcp(
    llm_client,
    question: str,
    system_prompt: str,
    model: str,
) -> str:
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp.server"],
        cwd=PROJECT_ROOT,
    )

    async with Client(server_parameters) as client:
        tool_result = await client.list_tools()
        discovered_tools = tool_result.tools

        if not discovered_tools:
            return "Error: MCP server did not provide any tools."

        tool_descriptions = []
        tool_names = set()

        for tool in discovered_tools:
            tool_names.add(tool.name)
            description = tool.description or "No description provided."
            props = tool.input_schema.get("properties", {}) if isinstance(tool.input_schema, dict) else {}
            params_example = ", ".join(f'"{k}": "..."' for k in props.keys())

            tool_descriptions.append(
                f"- {tool.name}({{{params_example}}}): {description}"
            )

        prompt_with_tools = (
            system_prompt
            + "\n\nAvailable tools:\n"
            + "\n".join(tool_descriptions)
            + '\n\nIMPORTANT FORMAT RULE:\n'
            + 'Never output system tool call objects. Output ONLY plain text using either:\n'
            + 'Action: tool_name({"argument": "value"})\n'
            + 'or:\n'
            + 'Final Answer: <your final response>\n'
        )

        async def tool_call(
            name: str,
            arguments: dict[str, Any],
        ) -> str:
            if name not in tool_names:
                return f"Error: unknown tool '{name}'."

            result = await client.call_tool(name, arguments)

            text_blocks = [
                block.text
                for block in (result.content or [])
                if getattr(block, "text", None)
            ]
            result_text = "\n".join(text_blocks)

            if result.is_error:
                return f"Error: {result_text or 'MCP tool call failed.'}"

            if result_text:
                return result_text

            if result.structured_content is not None:
                return json.dumps(
                    result.structured_content,
                    ensure_ascii=False,
                )

            return "Tool completed but returned no text."

        return await react_agent(
            llm_client=llm_client,
            question=question,
            tool_call=tool_call,
            system_prompt=prompt_with_tools,
            model=model,
        )