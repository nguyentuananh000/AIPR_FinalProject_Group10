import json
import re
from typing import Any

def parse_reply(
        reply: str,
)-> tuple[str, str| tuple[str, dict[str, Any]]| None]:
    """parse an LLM reply into a final answer, tool action, or invalid result."""
    if not reply or not reply.strip():
        return "invalid", "the model returned an empty response."

    text = reply.strip()

    text =  re.sub(r"^```(?:[a-zA-Z0-9_-]+)?\s*", "", text)
    text = re.sub(r"\s*```$","" , text).strip()

    final_match = re.search(
        r"(?im)^Final Answer:\s*(.+)$",
        text,
    )
    if final_match:
        return "final", final_match.group(1).strip()
 
    action_match = re.search(
        r"(?im)^Action:\s*`?([A-Za-z_]\w*)`?\s*"
        r"\(\s*(\{[^\r\n]*\})\s*\)\s*`?\s*$",
        text,
    )

    if not action_match:
        return "invalid", "expected final answer or action in the required format."

    tool_name =  action_match.group(1)
    raw_arguments = action_match.group(2)

    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as error:
        return "invalid", f"action argument are not valid JSON: {error}"
    if not isinstance (arguments, dict):
        return "invalid", "Action arguments must be a JSON object."
    return "action", (tool_name, arguments)