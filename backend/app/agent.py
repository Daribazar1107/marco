"""Marco's brain: an agent loop around a local LLM (Ollama + Gemma 4).

    user text -> LLM -> wants a tool? -> run it -> give result back to LLM -> ... -> answer

Tools that can't be undone (send_email) are NOT run here. They are saved as a
"pending action" and only run after the user presses "Тийм" (see run_pending).
"""

import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from ollama import Client

from app.config import settings
from app.google_auth import GoogleNotConnected, current_user_id
from app.tools import NEEDS_CONFIRMATION, TOOLS, TZ, describe

client = Client(host=settings.ollama_host)

WEEKDAYS = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"]


@dataclass
class PendingAction:
    id: str
    user_id: uuid.UUID
    tool: str
    args: dict
    summary: str
    expires: float


@dataclass
class AgentResult:
    reply: str
    steps: list[dict] = field(default_factory=list)  # tool calls, shown in the UI
    pending: PendingAction | None = None


# action id -> PendingAction. In memory: a restart forgets unconfirmed actions (safe default).
_pending: dict[str, PendingAction] = {}
PENDING_SECONDS = 600


def system_prompt() -> str:
    now = datetime.now(TZ)
    return (
        "You are Marco (Марко), a personal voice assistant for a Mongolian user.\n"
        "ALWAYS answer in Mongolian (Cyrillic). Keep answers short: 1-2 sentences, "
        "they are read aloud. No markdown, no lists, no emoji.\n"
        f"Now: {now:%Y-%m-%d %H:%M}, {WEEKDAYS[now.weekday()]} гараг. Timezone {settings.timezone}.\n"
        "Turn words like 'өнөөдөр', 'маргааш', 'нөгөөдөр', 'баасан гарагт', '3 цагт' into exact "
        "ISO dates and times. 'X цаг' between 1 and 7 usually means afternoon (13:00-19:00).\n"
        "Use tools for calendar, contacts and email. If you only know a person's name, "
        "call search_contacts first to get the email address.\n"
        "To send an email call send_email: the user will confirm it with a button.\n"
        "If something important is missing (time, who, what), ask a short question instead of guessing.\n"
        "The user's words come from speech recognition and may contain small mistakes; "
        "guess the most likely meaning."
    )


def _call_llm(messages: list) -> object:
    return client.chat(
        model=settings.ollama_model,
        messages=messages,
        tools=list(TOOLS.values()),  # Ollama builds the tool schema from the docstrings
        think=False,  # Gemma 4 "thinks" out loud by default: slow for a voice assistant
        options={"temperature": 0.2, "num_ctx": 8192},  # calm answers; room for tools + history
    ).message


def _save_pending(user_id: uuid.UUID, tool: str, args: dict) -> PendingAction:
    now = time.time()
    for key in [k for k, v in _pending.items() if v.expires < now]:
        del _pending[key]  # forget old ones
    action = PendingAction(
        id=secrets.token_urlsafe(12),
        user_id=user_id,
        tool=tool,
        args=args,
        summary=describe(tool, args),
        expires=now + PENDING_SECONDS,
    )
    _pending[action.id] = action
    return action


def _run_tool(name: str, args: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"Unknown tool: {name}"
    try:
        return str(tool(**args))
    except GoogleNotConnected:
        return "Google бүртгэл холбогдоогүй. Хэрэглэгчид «Google холбох» товч дарахыг хэл."
    except TypeError as error:  # wrong or missing arguments from the LLM
        return f"Буруу параметр: {error}"
    except Exception as error:
        return f"Алдаа гарлаа: {error}"


def run_agent(user_id: uuid.UUID, user_text: str, history: list[dict] | None = None) -> AgentResult:
    """Blocking: call it with asyncio.to_thread from the API."""
    current_user_id.set(user_id)
    messages = [{"role": "system", "content": system_prompt()}]
    messages += history or []
    messages.append({"role": "user", "content": user_text})

    result = AgentResult(reply="")
    for _ in range(settings.agent_max_steps):
        message = _call_llm(messages)
        messages.append(message)

        if not message.tool_calls:
            result.reply = (message.content or "").strip()
            break

        for call in message.tool_calls:
            name = call.function.name
            args = dict(call.function.arguments or {})

            if name in NEEDS_CONFIRMATION:
                if result.pending is None:
                    result.pending = _save_pending(user_id, name, args)
                    output = (
                        "NOT DONE YET. It is waiting for the user to press the confirm button. "
                        "Tell the user in one short Mongolian sentence what will be done and ask "
                        "them to confirm."
                    )
                else:
                    output = "Only one action can wait for confirmation at a time."
                status = "pending"
            else:
                output = _run_tool(name, args)
                status = "error" if output.startswith(("Алдаа", "Буруу", "Google бүртгэл")) else "ok"

            result.steps.append({"tool": name, "args": args, "result": output, "status": status})
            messages.append({"role": "tool", "content": output, "tool_name": name})
    else:
        result.reply = "Уучлаарай, энэ хүсэлтийг гүйцээж чадсангүй. Арай энгийнээр хэлээд үзээрэй."

    if not result.reply:
        result.reply = "Уучлаарай, ойлгосонгүй. Дахин хэлнэ үү."
    return result


def run_pending(user_id: uuid.UUID, action_id: str, approve: bool) -> str:
    """The user answered the confirm card. Returns what Marco says back."""
    action = _pending.pop(action_id, None)
    if action is None or action.user_id != user_id or action.expires < time.time():
        return "Энэ үйлдлийн хугацаа дууссан байна. Дахин хэлээд үзээрэй."
    if not approve:
        return "За, цуцаллаа."
    current_user_id.set(user_id)
    return _run_tool(action.tool, action.args)
