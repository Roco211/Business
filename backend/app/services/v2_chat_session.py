"""Lightweight chat session memory for multi-turn conversations.

This module provides a simple in-memory store for chat history
that can be used by the Chat API to support multi-turn conversations.
When real LLM is connected, the history is passed as part of the messages.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class ChatTurn:
    """A single turn in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ChatSession:
    """A chat session with conversation history."""
    session_id: str
    account_id: str
    shop_id: str
    turns: list[ChatTurn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def add_turn(self, role: str, content: str) -> None:
        """Add a turn to the conversation."""
        self.turns.append(ChatTurn(role=role, content=content))
        self.last_accessed = time.time()
        # Keep only last 10 turns to stay within context window
        if len(self.turns) > 20:
            self.turns = self.turns[-20:]

    def to_messages(self) -> list[dict]:
        """Convert history to LLM message format."""
        return [{"role": turn.role, "content": turn.content} for turn in self.turns]

    def touch(self) -> None:
        """Update last accessed time."""
        self.last_accessed = time.time()


class ChatSessionStore:
    """In-memory store for chat sessions with TTL cleanup."""

    _instance: ClassVar[ChatSessionStore | None] = None
    _sessions: dict[str, ChatSession]
    _ttl_seconds: float = 3600  # 1 hour TTL

    def __new__(cls) -> ChatSessionStore:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sessions = {}
        return cls._instance

    def get_or_create(
        self,
        session_id: str | None,
        account_id: str,
        shop_id: str,
    ) -> tuple[str, ChatSession]:
        """Get existing session or create a new one.
        
        Returns:
            Tuple of (session_id, session)
        """
        self._cleanup_expired()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            # Security check: ensure session belongs to the same user/shop
            if session.account_id == account_id and session.shop_id == shop_id:
                session.touch()
                return session_id, session

        # Create new session
        import uuid
        new_id = f"chat_{uuid.uuid4().hex[:16]}"
        session = ChatSession(
            session_id=new_id,
            account_id=account_id,
            shop_id=shop_id,
        )
        self._sessions[new_id] = session
        return new_id, session

    def get(self, session_id: str) -> ChatSession | None:
        """Get a session by ID."""
        self._cleanup_expired()
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_accessed > self._ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]


def get_chat_session_store() -> ChatSessionStore:
    """Get the global chat session store."""
    return ChatSessionStore()
