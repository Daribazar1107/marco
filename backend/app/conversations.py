"""Chat history in the database (conversations + messages tables).
The last few messages are given to the AI so it remembers the context:
    "Болдод мэйл бич" ... "За, гарчиг нь юу байх вэ?" ... "Уулзалт хойшиллоо"
"""

import uuid

from sqlalchemy import delete, func, insert, select

from app.db import engine
from app.models import Conversation, Message

HISTORY_LIMIT = 10  # messages the AI sees (more = slower)


def get_or_create(user_id: uuid.UUID, conversation_id: int | None) -> int:
    with engine.begin() as connection:
        if conversation_id:
            owner = connection.execute(
                select(Conversation.user_id).where(Conversation.id == conversation_id)
            ).scalar_one_or_none()
            if owner == user_id:  # only your own conversation
                return conversation_id
        return connection.execute(
            insert(Conversation).values(user_id=user_id).returning(Conversation.id)
        ).scalar_one()


def history(conversation_id: int) -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(Message.sender, Message.text)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(HISTORY_LIMIT)
        ).all()
    return [{"role": sender, "content": text} for sender, text in reversed(rows)]


def save(conversation_id: int, sender: str, text: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            insert(Message).values(conversation_id=conversation_id, sender=sender, text=text)
        )


# ---------------------------------------------------------------- Sidebar


def list_for_user(user_id: uuid.UUID, limit: int = 50) -> list[dict]:
    """Conversations with at least one message, newest first. Title = first user message."""
    first_text = (
        select(Message.text)
        .where(Message.conversation_id == Conversation.id, Message.sender == "user")
        .order_by(Message.id)
        .limit(1)
        .scalar_subquery()
    )
    last_at = (
        select(func.max(Message.created_at))
        .where(Message.conversation_id == Conversation.id)
        .scalar_subquery()
    )
    with engine.connect() as connection:
        rows = connection.execute(
            select(Conversation.id, first_text.label("title"), last_at.label("updated_at"))
            .where(Conversation.user_id == user_id, last_at.is_not(None))
            .order_by(last_at.desc())
            .limit(limit)
        ).all()
    return [
        {"id": row.id, "title": (row.title or "Шинэ яриа")[:80], "updated_at": row.updated_at}
        for row in rows
    ]


def _owned(connection, user_id: uuid.UUID, conversation_id: int) -> bool:
    owner = connection.execute(
        select(Conversation.user_id).where(Conversation.id == conversation_id)
    ).scalar_one_or_none()
    return owner == user_id


def messages(user_id: uuid.UUID, conversation_id: int) -> list[dict] | None:
    """All messages of one conversation, or None if it isn't yours."""
    with engine.connect() as connection:
        if not _owned(connection, user_id, conversation_id):
            return None
        rows = connection.execute(
            select(Message.sender, Message.text, Message.created_at)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        ).all()
    return [{"sender": r.sender, "text": r.text, "created_at": r.created_at} for r in rows]


def remove(user_id: uuid.UUID, conversation_id: int) -> bool:
    """Delete a conversation and its messages (ON DELETE CASCADE)."""
    with engine.begin() as connection:
        if not _owned(connection, user_id, conversation_id):
            return False
        connection.execute(delete(Conversation).where(Conversation.id == conversation_id))
    return True
