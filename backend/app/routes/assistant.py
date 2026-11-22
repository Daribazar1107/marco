"""The assistant API used by the web page.

POST /api/voice    recording -> text -> agent -> voice
POST /api/chat     typed text -> agent -> voice
POST /api/confirm  "Тийм" / "Үгүй" on the confirm card
GET  /api/conversations        sidebar list
GET  /api/conversations/{id}   one conversation's messages
DELETE /api/conversations/{id}
"""

import asyncio
import base64

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app import conversations
from app.agent import run_agent, run_pending
from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.voice import speech_to_text, text_to_speech

router = APIRouter(prefix="/api", tags=["assistant"])

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # ~ a few minutes; the page stops at 15 s anyway


async def speak(text: str) -> str | None:
    """Marco's answer as base64 mp3. Text still works if the voice fails."""
    try:
        audio, _ = await text_to_speech(text)
        return base64.b64encode(audio).decode()
    except Exception:
        return None


async def answer(user: CurrentUser, conversation_id: int | None, user_text: str) -> dict:
    conversation_id = conversations.get_or_create(user.id, conversation_id)

    if not user_text:
        reply = "Уучлаарай, би сонссонгүй. Дахин хэлээд үзээрэй."
        return {
            "conversation_id": conversation_id,
            "user_text": "",
            "reply_text": reply,
            "steps": [],
            "pending_action": None,
            "audio_base64": await speak(reply),
        }

    past = conversations.history(conversation_id)
    conversations.save(conversation_id, "user", user_text)
    try:
        result = await asyncio.to_thread(run_agent, user.id, user_text, past)
    except Exception as error:
        raise HTTPException(
            503,
            f"AI загвартай холбогдож чадсангүй ({settings.ollama_model}). "
            f"'ollama serve' ажиллаж байгаа эсэхийг шалгана уу. ({error})",
        )
    conversations.save(conversation_id, "assistant", result.reply)

    pending = None
    if result.pending:
        pending = {"id": result.pending.id, "summary": result.pending.summary, "args": result.pending.args}

    return {
        "conversation_id": conversation_id,
        "user_text": user_text,
        "reply_text": result.reply,
        "steps": result.steps,
        "pending_action": pending,
        "audio_base64": await speak(result.reply),
    }


@router.post("/voice")
async def voice(
    audio: UploadFile,
    conversation_id: int | None = Form(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    data = await audio.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Бичлэг хэт урт байна")
    try:
        user_text = await speech_to_text(data)
    except Exception as error:
        raise HTTPException(502, f"Яриа таних алдаа ({settings.stt_provider}): {error}")
    return await answer(user, conversation_id, user_text)


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    conversation_id: int | None = None


@router.post("/chat")
async def chat(request: ChatRequest, user: CurrentUser = Depends(get_current_user)):
    return await answer(user, request.conversation_id, request.text.strip())


class ConfirmRequest(BaseModel):
    action_id: str
    approve: bool
    conversation_id: int | None = None


@router.post("/confirm")
async def confirm(request: ConfirmRequest, user: CurrentUser = Depends(get_current_user)):
    reply = await asyncio.to_thread(run_pending, user.id, request.action_id, request.approve)
    if request.conversation_id:
        conversation_id = conversations.get_or_create(user.id, request.conversation_id)
        conversations.save(conversation_id, "assistant", reply)
    return {"reply_text": reply, "audio_base64": await speak(reply)}


# ---------------------------------------------------------------- History (sidebar)


@router.get("/conversations")
def list_conversations(user: CurrentUser = Depends(get_current_user)):
    return conversations.list_for_user(user.id)


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, user: CurrentUser = Depends(get_current_user)):
    found = conversations.messages(user.id, conversation_id)
    if found is None:
        raise HTTPException(404, "Яриа олдсонгүй")
    return {"id": conversation_id, "messages": found}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, user: CurrentUser = Depends(get_current_user)):
    if not conversations.remove(user.id, conversation_id):
        raise HTTPException(404, "Яриа олдсонгүй")
    return {"deleted": conversation_id}
