from fastapi import APIRouter

from .models import MotdPostRequest, MotdMessage, MotdListResponse, MotdLatestResponse
from .storage import storage


router = APIRouter(prefix="/module/motd", tags=["motd"])


@router.get("/", response_model=MotdListResponse)
def list_messages():
    """List all MOTD messages, newest first."""
    messages = storage.list_all()
    latest = storage.get_latest()
    return MotdListResponse(
        messages=messages,
        count=len(messages),
        latest_id=latest.id if latest else None,
    )


@router.post("/", response_model=MotdMessage)
def post_message(req: MotdPostRequest):
    """Post a new message of the day."""
    msg = storage.add(req.message, author=req.author)
    return msg


@router.get("/latest", response_model=MotdLatestResponse)
def get_latest():
    """Get the most recent MOTD message."""
    msg = storage.get_latest()
    if msg is None:
        return MotdLatestResponse(
            message=MotdMessage(id=0, message="", author=None, created_at="")
        )
    return MotdLatestResponse(message=msg)
