from collections.abc import Awaitable, Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.models.hero import Hero
from app.models.player import Player
from app.routes.auth import get_current_player
from app.schemas.dungeon import CombatRead, HeroMove, RoomRead
from app.schemas.hero import HeroCreate, HeroRead
from app.services.hero_service import (
    HeroServiceError,
    attack_with_hero as service_attack,
    create_hero as service_create,
    get_hero as service_get,
    get_hero_room as service_get_room,
    list_heroes as service_list,
    move_hero as service_move,
    rest_hero as service_rest,
)

router = APIRouter(prefix="/heroes", tags=["Héros"])
CurrentPlayer = Annotated[Player, Depends(get_current_player)]
Result = TypeVar("Result")


@router.post("", response_model=HeroRead, status_code=status.HTTP_201_CREATED)
def create_hero(
    hero_data: HeroCreate,
    player: CurrentPlayer,
    session: Session = Depends(get_session),
) -> Hero:
    return _call_service(service_create, hero_data, player, session)


@router.get("", response_model=list[HeroRead])
def list_heroes(
    player: CurrentPlayer,
    session: Session = Depends(get_session),
) -> list[Hero]:
    return list(_call_service(service_list, player, session))


@router.get("/{hero_id}", response_model=HeroRead)
def get_hero(
    hero_id: int,
    player: CurrentPlayer,
    session: Session = Depends(get_session),
) -> Hero:
    return _call_service(service_get, hero_id, player, session)


@router.get("/{hero_id}/room", response_model=RoomRead)
def get_hero_room(
    hero_id: int,
    player: CurrentPlayer,
    session: Session = Depends(get_session),
) -> RoomRead:
    return _call_service(service_get_room, hero_id, player, session)


@router.post("/{hero_id}/move", response_model=RoomRead)
def move_hero(
    hero_id: int,
    move: HeroMove,
    player: CurrentPlayer,
    session: Session = Depends(get_session),
) -> RoomRead:
    return _call_service(service_move, hero_id, move, player, session)


@router.post("/{hero_id}/attack", response_model=CombatRead)
def attack_with_hero(
    hero_id: int,
    player: CurrentPlayer,
    session: Session = Depends(get_session),
) -> CombatRead:
    return _call_service(service_attack, hero_id, player, session)


@router.post("/{hero_id}/rest", response_model=HeroRead)
async def rest_hero(
    hero_id: int,
    player: CurrentPlayer,
    session: Session = Depends(get_session),
) -> Hero:
    return await _call_async_service(service_rest, hero_id, player, session)


def _http_error(error: HeroServiceError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"error": error.error, "message": error.message},
    )


def _call_service(operation: Callable[..., Result], *args: object) -> Result:
    try:
        return operation(*args)
    except HeroServiceError as error:
        raise _http_error(error) from error


async def _call_async_service(
    operation: Callable[..., Awaitable[Result]],
    *args: object,
) -> Result:
    try:
        return await operation(*args)
    except HeroServiceError as error:
        raise _http_error(error) from error
