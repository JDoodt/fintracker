"""Phase 4: CSV import — stub for Phase 1."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/import", response_class=HTMLResponse)
async def import_page(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "import_review.html", {
        "current_user": current_user,
        "flash": request.session.pop("flash", None),
    })
