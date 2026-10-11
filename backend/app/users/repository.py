"""Learning history: users, sessions, utterances, feedback, review items, repeated errors."""

import json
import re
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.types import WordInfo
from app.evaluation.schema import Feedback
from app.users.db import (
    ErrorRecord,
    FeedbackRecord,
    ReviewItem,
    SessionRecord,
    User,
    Utterance,
    utcnow,
)

_NICKNAME_RE = re.compile(r"^[\w\- ]{1,40}$")


class Repository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    # ----- users & sessions -------------------------------------------------------------

    def get_or_create_user(self, nickname: str) -> int:
        nickname = nickname.strip() or "guest"
        if not _NICKNAME_RE.match(nickname):
            raise ValueError("Nickname may contain letters, numbers, spaces, - and _ (max 40).")
        with self._sessions.begin() as db:
            user = db.scalar(select(User).where(User.nickname == nickname))
            if user is None:
                user = User(nickname=nickname)
                db.add(user)
                db.flush()
            return user.id

    def create_session(self, session_id: str, user_id: int, scene_id: str) -> None:
        with self._sessions.begin() as db:
            db.add(SessionRecord(id=session_id, user_id=user_id, scene_id=scene_id))

    def add_utterance(
        self,
        session_id: str,
        seq: int,
        speaker: str,
        text: str,
        words: list[WordInfo] | None = None,
    ) -> None:
        with self._sessions.begin() as db:
            db.add(
                Utterance(
                    session_id=session_id,
                    seq=seq,
                    speaker=speaker,
                    text=text,
                    asr_text=text if words else None,
                    words_json=json.dumps([w.model_dump() for w in words]) if words else None,
                )
            )

    def fix_utterance(self, session_id: str, seq: int, corrected: str) -> bool:
        """The user corrected a misrecognized line. Keeps the raw ASR text."""
        with self._sessions.begin() as db:
            row = db.scalar(
                select(Utterance).where(
                    Utterance.session_id == session_id,
                    Utterance.seq == seq,
                    Utterance.speaker == "user",
                )
            )
            if row is None:
                return False
            if row.asr_text is None:
                row.asr_text = row.text
            row.text = corrected
            row.words_json = None  # confidences no longer describe the corrected text
            return True

    def user_lines(self, session_id: str) -> list[tuple[int, str, list[WordInfo]]]:
        with self._sessions() as db:
            rows = db.scalars(
                select(Utterance)
                .where(Utterance.session_id == session_id, Utterance.speaker == "user")
                .order_by(Utterance.seq)
            ).all()
            return [
                (r.seq, r.text, [WordInfo(**w) for w in json.loads(r.words_json or "[]")])
                for r in rows
            ]

    def spoken_lines(self, session_id: str) -> list[tuple[int, str, list[WordInfo]]]:
        """User lines as recognized (before any correction), for lining up with the audio."""
        with self._sessions() as db:
            rows = db.scalars(
                select(Utterance)
                .where(
                    Utterance.session_id == session_id,
                    Utterance.speaker == "user",
                    Utterance.asr_text.is_not(None),
                )
                .order_by(Utterance.seq)
            ).all()
            return [
                (r.seq, r.asr_text or "", [WordInfo(**w) for w in json.loads(r.words_json or "[]")])
                for r in rows
            ]

    def transcript(self, session_id: str) -> list[tuple[str, str]]:
        with self._sessions() as db:
            rows = db.scalars(
                select(Utterance).where(Utterance.session_id == session_id).order_by(Utterance.id)
            ).all()
            return [(r.speaker, r.text) for r in rows]

    def finish_session(self, session_id: str, success: bool, reason: str | None) -> None:
        with self._sessions.begin() as db:
            row = db.get(SessionRecord, session_id)
            if row is not None:
                row.ended_at = utcnow()
                row.success = success
                row.end_reason = reason

    def session_user(self, session_id: str) -> int | None:
        with self._sessions() as db:
            row = db.get(SessionRecord, session_id)
            return row.user_id if row else None

    # ----- feedback ---------------------------------------------------------------------

    def save_feedback(self, session_id: str, feedback: Feedback) -> None:
        with self._sessions.begin() as db:
            record = db.get(SessionRecord, session_id)
            if record is None:
                raise KeyError(session_id)
            db.merge(
                FeedbackRecord(session_id=session_id, feedback_json=feedback.model_dump_json())
            )
            for sentence in feedback.review_items:
                db.add(ReviewItem(user_id=record.user_id, session_id=session_id, sentence=sentence))
            for e in feedback.grammar_errors:
                db.add(
                    ErrorRecord(
                        user_id=record.user_id,
                        session_id=session_id,
                        kind="grammar",
                        error_type=e.type.lower().strip()[:40],
                        original=e.original,
                        corrected=e.corrected,
                    )
                )
            for e in feedback.unnatural_expressions:
                db.add(
                    ErrorRecord(
                        user_id=record.user_id,
                        session_id=session_id,
                        kind="expression",
                        error_type="expression",
                        original=e.original,
                        corrected=e.better,
                    )
                )

    def get_feedback(self, session_id: str) -> Feedback | None:
        with self._sessions() as db:
            row = db.get(FeedbackRecord, session_id)
            return Feedback.model_validate_json(row.feedback_json) if row else None

    # ----- review -----------------------------------------------------------------------

    def repeated_error_types(self, user_id: int, min_count: int = 2) -> list[tuple[str, int]]:
        with self._sessions() as db:
            rows = db.execute(
                select(ErrorRecord.error_type, func.count())
                .where(ErrorRecord.user_id == user_id, ErrorRecord.kind == "grammar")
                .group_by(ErrorRecord.error_type)
                .having(func.count() >= min_count)
                .order_by(func.count().desc())
            ).all()
            return [(t, n) for t, n in rows]

    def review(self, user_id: int, limit: int = 30) -> dict:
        with self._sessions() as db:
            user = db.get(User, user_id)
            if user is None:
                raise KeyError(user_id)
            sentences = db.scalars(
                select(ReviewItem.sentence)
                .where(ReviewItem.user_id == user_id)
                .order_by(ReviewItem.created_at.desc(), ReviewItem.id.desc())
            ).all()
            counts = Counter(sentences)
            items = [{"sentence": s, "times": counts[s]} for s in dict.fromkeys(sentences)][:limit]
            errors = db.scalars(
                select(ErrorRecord)
                .where(ErrorRecord.user_id == user_id)
                .order_by(ErrorRecord.created_at.desc(), ErrorRecord.id.desc())
            ).all()
            sessions = db.scalars(
                select(SessionRecord)
                .where(SessionRecord.user_id == user_id, SessionRecord.ended_at.is_not(None))
                .order_by(SessionRecord.started_at.desc())
            ).all()
        repeated = []
        for error_type, n in self.repeated_error_types(user_id):
            examples = [
                {"original": e.original, "corrected": e.corrected}
                for e in errors
                if e.error_type == error_type
            ][:3]
            repeated.append({"error_type": error_type, "count": n, "examples": examples})
        return {
            "user_id": user_id,
            "nickname": user.nickname,
            "sessions": [
                {
                    "id": s.id,
                    "scene_id": s.scene_id,
                    "started_at": s.started_at.isoformat(),
                    "success": s.success,
                }
                for s in sessions[:20]
            ],
            "review_items": items,
            "repeated_errors": repeated,
        }
