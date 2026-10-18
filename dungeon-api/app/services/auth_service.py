from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.player import Player
from app.schemas.auth import PlayerCreate, TokenRead
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class AuthServiceError(Exception):
    def __init__(self, status_code: int, error: str, message: str) -> None:
        self.status_code = status_code
        self.error = error
        self.message = message
        super().__init__(message)


def register_player(player_data: PlayerCreate, session: Session) -> Player:
    player = Player(
        username=player_data.username,
        hashed_password=hash_password(player_data.password),
    )
    session.add(player)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise AuthServiceError(
            409,
            "USERNAME_TAKEN",
            "Ce nom d'utilisateur existe déjà.",
        ) from error
    session.refresh(player)
    return player


def login_player(username: str, password: str, session: Session) -> TokenRead:
    player = session.exec(
        select(Player).where(Player.username == username)
    ).first()
    if player is None or not verify_password(password, player.hashed_password):
        raise AuthServiceError(
            401,
            "INVALID_CREDENTIALS",
            "Nom d'utilisateur ou mot de passe incorrect.",
        )
    return TokenRead(access_token=create_access_token(player.username))


def get_current_player(token: str, session: Session) -> Player:
    username = decode_access_token(token)
    if username is None:
        raise AuthServiceError(401, "INVALID_TOKEN", "Jeton invalide ou expiré.")
    player = session.exec(select(Player).where(Player.username == username)).first()
    if player is None:
        raise AuthServiceError(401, "INVALID_TOKEN", "Joueur introuvable.")
    return player
