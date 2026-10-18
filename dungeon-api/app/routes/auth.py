from collections.abc import Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session

from app.database import get_session
from app.models.player import Player
from app.schemas.auth import PlayerCreate, PlayerRead, TokenRead
from app.services.auth_service import (
    AuthServiceError,
    get_current_player as service_get_current_player,
    login_player as service_login,
    register_player as service_register,
)

router = APIRouter(prefix="/auth", tags=["Authentification"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
Result = TypeVar("Result")


@router.post(
    "/register",
    response_model=PlayerRead,
    status_code=status.HTTP_201_CREATED,
)
def register_player(
    player_data: PlayerCreate,
    session: Session = Depends(get_session),
) -> Player:
    return _call_service(service_register, player_data, session)


@router.post("/login", response_model=TokenRead)
def login_player(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
) -> TokenRead:
    return _call_service(service_login, form_data.username, form_data.password, session)


def get_current_player(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Session = Depends(get_session),
) -> Player:
    return _call_service(service_get_current_player, token, session)


def _http_error(error: AuthServiceError) -> HTTPException:
    headers = (
        {"WWW-Authenticate": "Bearer"}
        if error.status_code == status.HTTP_401_UNAUTHORIZED
        else None
    )
    return HTTPException(
        status_code=error.status_code,
        detail={"error": error.error, "message": error.message},
        headers=headers,
    )


def _call_service(operation: Callable[..., Result], *args: object) -> Result:
    try:
        return operation(*args)
    except AuthServiceError as error:
        raise _http_error(error) from error
