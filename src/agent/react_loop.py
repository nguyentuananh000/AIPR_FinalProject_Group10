import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from .parser import parse_reply

MAX_STEPS = 12
logger  = logging.getLogger(__name__)
ToolCaller = Callable[[str, dict[str, Any]], Awaitable[str]]

async def react_agent(
    llm_client,
    question: str,
    tool_call: ToolCaller,
    system_prompt: str,
    model: str,
    max_steps: int = MAX_STEPS,
    tools: list[dict[str, Any]] | None = None,
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    trace_path = Path(__file__).resolve().parents[2] / "logs" / "run_trace_1.txt"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text("", encoding="utf-8")

    def write_trace(text: str) -> None:
        with trace_path.open("a", encoding="utf-8") as file:
         file.write(text + "\n")
    for step in range(1, max_steps + 1):
        try:
            response = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model=model,
                messages=messages,
                temperature=0,
                tools=tools or None,
                tool_choice="auto" if tools else "none",
                parallel_tool_calls=False,
            )
            assistant_message = response.choices[0].message
            reply = assistant_message.content or ""
            native_tool_calls = assistant_message.tool_calls or []
            write_trace(f"\n[STEP {step}] MODEL RESPONSE:\n{reply}")
        except Exception as error:
            logger.exception("LLM call failed")
            return f"Error: could not get a response from the model: {error}"

        if native_tool_calls:
            # Groq may return native function calls instead of text Action lines.
            # Execute the first call and feed its result back as a tool message.
            call = native_tool_calls[0]
            tool_name = call.function.name
            try:
                arguments = json.loads(call.function.arguments or "{}")
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object.")
            except (json.JSONDecodeError, ValueError) as error:
                return f"Error: invalid arguments for tool '{tool_name}': {error}"

            write_trace(
                f"ACTION: {tool_name}({json.dumps(arguments, ensure_ascii=False)})"
            )
            messages.append({
                "role": "assistant",
                "content": reply or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": call.function.arguments,
                        },
                    }
                ],
            })
            try:
                observation = await tool_call(tool_name, arguments)
            except Exception as error:
                logger.exception("Tool call failed: %s", tool_name)
                observation = f"Error: tool '{tool_name}' failed: {error}"

            if (
                tool_name == "submit_audit_decision"
                and not observation.startswith("Error:")
            ):
                claim_id = arguments.get("claim_id")
                expected_status = str(arguments.get("status", "")).strip().upper()
                if expected_status == "REQUEST_INFO":
                    expected_status = "REQUEST_MORE_INFO"
                if not claim_id:
                    observation += "\nError: cannot verify because claim_id is missing."
                else:
                    try:
                        status_text = await tool_call(
                            "get_claim_status", {"claim_id": claim_id}
                        )
                        write_trace(f"VERIFY get_claim_status: {status_text}")
                        saved_status = json.loads(status_text).get("status")
                        if saved_status == expected_status:
                            observation += (
                                f"\nVerification succeeded: saved status is {saved_status}."
                            )
                        else:
                            observation += (
                                f"\nError: verification mismatch. Expected "
                                f"{expected_status}, read back {saved_status}."
                            )
                    except Exception as error:
                        logger.exception("Status verification failed")
                        observation += f"\nError: could not verify saved status: {error}"

            write_trace(f"OBSERVATION: {observation}")
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": observation,
            })
            continue

        kind, payload = parse_reply(reply)
        write_trace(f"PARSED: {kind}")
        if kind == "final":
            write_trace(f"FINAL ANSWER: {payload}")
            return payload
        
        messages.append({"role": "assistant", "content": reply})

        if kind == "invalid":
            write_trace(f"OBSERVATION: Error: {payload}")
            messages.append({
                "role": "user",
                "content": (
                    f"Observation: Error: {payload} "
                    "Return either a valid Action or Final Answer."
                ),
            })
            continue

        if kind != "action":
            return f"Error: unexpected parser result '{kind}'."

        tool_name, arguments = payload
        write_trace(f"ACTION: {tool_name}({json.dumps(arguments, ensure_ascii=False)})")
        try:
            observation = await tool_call(tool_name, arguments)
        except Exception as error:
            logger.exception("Tool call failed: %s", tool_name)
            observation = f"Error: tool '{tool_name}' failed: {error}"

        if (
            tool_name == "submit_audit_decision"
            and not observation.startswith("Error:")
        ):
            claim_id = arguments.get("claim_id")
            expected_status = str(
                arguments.get("status", "")
            ).strip().upper()

            if expected_status == "REQUEST_INFO":
                expected_status = "REQUEST_MORE_INFO"

            if not claim_id:
                observation += (
                    "\nError: cannot verify because claim_id is missing."
                )
            else:
                try:
                    status_text = await tool_call(
                        "get_claim_status",
                        {"claim_id": claim_id},
                    )
                    saved_status = json.loads(status_text).get("status")
                    write_trace(f"VERIFY get_claim_status: {status_text}")
                    if saved_status == expected_status:
                        observation += (
                            f"\nVerification succeeded: saved status is "
                            f"{saved_status}."
                        )
                    else:
                        observation += (
                            f"\nError: verification mismatch. Expected "
                            f"{expected_status}, read back {saved_status}."
                        )

                except Exception as error:
                    logger.exception("Status verification failed")
                    observation += (
                        f"\nError: could not verify saved status: {error}"
                    )
        write_trace(f"OBSERVATION: {observation}")
        messages.append({
            "role": "user",
            "content": f"Observation: {observation}",
        })

    return f"Stopped: reached the maximum of {max_steps} steps."
