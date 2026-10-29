"""Explicit account enrollment and session endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .auth import COOKIE, SESSION_SECONDS, AuthenticationError, AuthStore

router = APIRouter(prefix="/api/auth")


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=128, repr=False)


class Enrollment(Login):
    code: str = Field(min_length=20, max_length=128, repr=False)


class NewUser(Login):
    role: str = Field(default="member", pattern="^(admin|member)$")


class NewPassword(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128, repr=False)
    new_password: str = Field(min_length=14, max_length=128, repr=False)


def store(request):
    return AuthStore(request.app.state.runs.store.directory)


def cookie(response, request, token):
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


@router.get("/status")
def status(request: Request):
    return {"configured": store(request).configured()}


@router.post("/enroll", status_code=201)
def enroll(payload: Enrollment, request: Request, response: Response):
    auth = store(request)
    auth.enroll(payload.code, payload.username, payload.password)
    token, user = auth.login(payload.username, payload.password)
    cookie(response, request, token)
    return {"user": user.public()}


@router.post("/login")
def login(payload: Login, request: Request, response: Response):
    token, user = store(request).login(payload.username, payload.password, "loopback-browser")
    cookie(response, request, token)
    return {"user": user.public()}


@router.post("/logout")
def logout(request: Request, response: Response):
    store(request).logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
    return {"signed_out": True}


@router.get("/me")
def me(request: Request):
    return {"user": request.state.principal.public()}


@router.post("/password")
def password(payload: NewPassword, request: Request, response: Response):
    store(request).change_password(
        request.state.principal, payload.current_password, payload.new_password
    )
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
    return {"signed_out": True}


@router.get("/users")
def users(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    if request.state.principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required")
    rows = store(request).users(offset=offset, limit=limit + 1)
    return {"users": rows[:limit], "next_offset": offset + limit if len(rows) > limit else None}


class UserChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str | None = Field(default=None, pattern="^(admin|member)$")
    active: bool | None = Field(default=None, strict=True)


@router.post("/users/{user_id}/update")
def update_user(user_id: str, payload: UserChange, request: Request):
    if request.state.principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required")
    try:
        return {
            "user": store(request).manage_user(
                request.state.principal, user_id, role=payload.role, active=payload.active
            )
        }
    except AuthenticationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/users/{user_id}/revoke-sessions")
def revoke_sessions(user_id: str, request: Request):
    if request.state.principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required")
    return {"user": store(request).manage_user(request.state.principal, user_id, revoke=True)}


@router.post("/users", status_code=201)
def create_user(payload: NewUser, request: Request):
    if request.state.principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required")
    user = store(request).add_user(
        request.state.principal, payload.username, payload.password, payload.role
    )
    return {"user": user.public()}
