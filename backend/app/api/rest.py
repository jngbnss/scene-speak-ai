from fastapi import APIRouter, HTTPException

from app.api.deps import get_services
from app.evaluation.schema import Feedback

router = APIRouter(prefix="/api")


@router.get("/sessions/{session_id}/feedback")
def session_feedback(session_id: str) -> Feedback:
    feedback = get_services().repo.get_feedback(session_id)
    if feedback is None:
        raise HTTPException(404, "Feedback is not ready or the session does not exist.")
    return feedback


@router.get("/users/{user_id}/review")
def user_review(user_id: int) -> dict:
    try:
        return get_services().repo.review(user_id)
    except KeyError:
        raise HTTPException(404, "No such user.") from None
