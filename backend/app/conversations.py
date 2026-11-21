"""Chat history in the database (conversations + messages tables).
The last few messages are given to the AI so it remembers the context:
    "Болдод мэйл бич" ... "За, гарчиг нь юу байх вэ?" ... "Уулзалт хойшиллоо"
"""

import uuid

from sqlalchemy import insert, select

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
