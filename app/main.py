from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, expenses, income, categories, reports, exports, imports as imports_router

app = FastAPI(title="Family Finance Tracker")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=settings.SESSION_MAX_AGE,
    https_only=False,
    same_site="lax",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(income.router)
app.include_router(categories.router)
app.include_router(reports.router)
app.include_router(exports.router)
app.include_router(imports_router.router)
