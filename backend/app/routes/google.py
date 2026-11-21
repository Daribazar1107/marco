from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app import google_auth
from app.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api/google", tags=["google"])


@router.get("/connect")
def connect(user: CurrentUser = Depends(get_current_user)):
    """The browser opens this URL: Google's consent page."""
    try:
        return {"url": google_auth.build_auth_url(user.id)}
    except FileNotFoundError as error:
        raise HTTPException(500, str(error))


@router.get("/callback", include_in_schema=False)
def callback(state: str = "", code: str = "", error: str = ""):
    """Google sends the user back here after the consent page."""
    if error or not code:
        return RedirectResponse("/?google=cancelled")
    try:
        google_auth.handle_callback(state, code)
    except Exception:
        return RedirectResponse("/?google=error")
    return RedirectResponse("/?google=connected")


@router.get("/status")
def status(user: CurrentUser = Depends(get_current_user)):
    return {"connected": google_auth.is_connected(user.id)}


@router.delete("")
def disconnect(user: CurrentUser = Depends(get_current_user)):
    google_auth.disconnect(user.id)
    return {"connected": False}
