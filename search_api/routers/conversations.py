"""
Conversation history API — save/load RAG chat sessions.

Stores conversations as JSON arrays of messages in the DB,
allowing users to continue where they left off.
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel

from search_api.db import get_connection
from search_api.routers.auth import require_admin

router = APIRouter(prefix="/admin/conversations", tags=["conversations"], dependencies=[Depends(require_admin)])

_schema_ensured = False


def _ensure_table():
    global _schema_ensured
    if _schema_ensured:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_updated
                ON conversations (updated_at DESC)
            """)
        conn.commit()
        _schema_ensured = True
    finally:
        conn.close()


class ConversationSummary(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str


class ConversationFull(BaseModel):
    id: str
    title: str
    messages: list
    created_at: str
    updated_at: str


class SaveRequest(BaseModel):
    id: str | None = None
    title: str
    messages: list


class RenameRequest(BaseModel):
    title: str


@router.get("/", response_model=list[ConversationSummary])
def list_conversations(limit: int = 20, offset: int = 0):
    _ensure_table()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, jsonb_array_length(messages), created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        ConversationSummary(
            id=r[0], title=r[1], message_count=r[2],
            created_at=r[3].isoformat(), updated_at=r[4].isoformat(),
        )
        for r in rows
    ]


@router.get("/{conv_id}", response_model=ConversationFull)
def get_conversation(conv_id: str):
    _ensure_table()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, messages, created_at, updated_at FROM conversations WHERE id = %s", (conv_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ConversationFull(
        id=row[0], title=row[1], messages=row[2],
        created_at=row[3].isoformat(), updated_at=row[4].isoformat(),
    )


@router.post("/", response_model=ConversationFull)
def save_conversation(body: SaveRequest):
    _ensure_table()
    conv_id = body.id or str(uuid.uuid4())[:8]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO conversations (id, title, messages, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title,
                    messages = EXCLUDED.messages,
                    updated_at = now()
                RETURNING id, title, messages, created_at, updated_at
            """, (conv_id, body.title, json.dumps(body.messages)))
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    logger.info(f"EVIDENCE_CONVERSATION_SAVE: id={conv_id} messages={len(body.messages)}")
    return ConversationFull(
        id=row[0], title=row[1], messages=row[2],
        created_at=row[3].isoformat(), updated_at=row[4].isoformat(),
    )


@router.patch("/{conv_id}", response_model=ConversationFull)
def rename_conversation(conv_id: str, body: RenameRequest):
    _ensure_table()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE conversations SET title = %s, updated_at = now()
                WHERE id = %s
                RETURNING id, title, messages, created_at, updated_at
            """, (body.title, conv_id))
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ConversationFull(
        id=row[0], title=row[1], messages=row[2],
        created_at=row[3].isoformat(), updated_at=row[4].isoformat(),
    )


@router.delete("/{conv_id}")
def delete_conversation(conv_id: str):
    _ensure_table()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE id = %s RETURNING id", (conv_id,))
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"deleted": conv_id}
