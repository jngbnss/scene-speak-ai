from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import ForeignKey, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(String(40), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class SessionRecord(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scene_id: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[datetime | None]
    success: Mapped[bool | None]
    end_reason: Mapped[str | None] = mapped_column(String(40))


class Utterance(Base):
    __tablename__ = "utterances"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    seq: Mapped[int]
    speaker: Mapped[str] = mapped_column(String(8))  # "user" | "npc"
    text: Mapped[str] = mapped_column(Text)
    asr_text: Mapped[str | None] = mapped_column(Text)  # raw recognition before user fixes
    words_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class FeedbackRecord(Base):
    __tablename__ = "feedback"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    feedback_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ReviewItem(Base):
    __tablename__ = "review_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    sentence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ErrorRecord(Base):
    __tablename__ = "error_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    kind: Mapped[str] = mapped_column(String(16))  # "grammar" | "expression"
    error_type: Mapped[str] = mapped_column(String(40))
    original: Mapped[str] = mapped_column(Text)
    corrected: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///") and not url.endswith(":memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


def make_sessionmaker(url: str) -> sessionmaker:
    return sessionmaker(make_engine(url), expire_on_commit=False)
