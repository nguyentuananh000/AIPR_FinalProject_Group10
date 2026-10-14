import asyncio
import json
import logging
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
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    for step in range(1, max_steps + 1):
        try:
            response = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model=model,
                messages=messages,
                temperature=0,
            )
            reply = response.choices[0].message.content or ""

        except Exception as error:
            logger.exception("LLM call failed")
            return f"Error: could not get a response from the model: {error}"

        kind, payload = parse_reply(reply)

        if kind == "final":
            return payload

        # Ghi lại câu trả lời của model trước khi gửi Observation.
        messages.append({"role": "assistant", "content": reply})

        if kind == "invalid":
            messages.append({
                "role": "user",
                "content": (
                    f"Observation: Error: {payload} "
                    "Return either a valid Action or Final Answer."
                ),
            })
            continue

        # Từ đây trở xuống chỉ xử lý Action hợp lệ.
        if kind != "action":
            return f"Error: unexpected parser result '{kind}'."

        tool_name, arguments = payload

        try:
            observation = await tool_call(tool_name, arguments)
        except Exception as error:
            logger.exception("Tool call failed: %s", tool_name)
            observation = f"Error: tool '{tool_name}' failed: {error}"

        # Sau khi ghi quyết định, tự động đọc lại để xác minh.
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

        messages.append({
            "role": "user",
            "content": f"Observation: {observation}",
        })

    # Dòng này nằm ngoài vòng for.
    return f"Stopped: reached the maximum of {max_steps} steps."