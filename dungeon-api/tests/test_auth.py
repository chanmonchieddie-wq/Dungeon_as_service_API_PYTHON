import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.models.player import Player
from app.routes.auth import router as auth_router
from app.routes.heroes import router as heroes_router
from app.security import verify_password


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "auth.db")),
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    test_app = FastAPI()
    test_app.include_router(auth_router)
    test_app.include_router(heroes_router)
    test_app.dependency_overrides[get_session] = get_test_session

    with TestClient(test_app) as test_client:
        yield test_client, engine

    engine.dispose()


def register(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"username": username, "password": password},
    )
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_register_stores_only_password_hash(client) -> None:
    test_client, engine = client
    player_data = register(test_client, "alice", "password123")

    assert player_data == {"id": 1, "username": "alice"}
    with Session(engine) as session:
        player = session.get(Player, 1)
        assert player is not None
        assert player.hashed_password != "password123"
        assert verify_password("password123", player.hashed_password)


def test_register_rejects_duplicate_username(client) -> None:
    test_client, _engine = client
    register(test_client, "alice", "password123")

    response = test_client.post(
        "/auth/register",
        json={"username": "alice", "password": "different123"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "USERNAME_TAKEN"


def test_register_validates_credentials(client) -> None:
    test_client, _engine = client
    response = test_client.post(
        "/auth/register",
        json={"username": "ab", "password": "short"},
    )

    assert response.status_code == 422


def test_login_returns_oauth_compatible_jwt(client) -> None:
    test_client, _engine = client
    register(test_client, "alice", "password123")

    response = test_client.post(
        "/auth/login",
        data={"username": "alice", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert test_client.get("/heroes").status_code == 401
    test_client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    assert test_client.get("/heroes").status_code == 200


def test_login_rejects_wrong_password(client) -> None:
    test_client, _engine = client
    register(test_client, "alice", "password123")

    response = test_client.post(
        "/auth/login",
        data={"username": "alice", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_heroes_are_private_to_their_owner(client) -> None:
    test_client, _engine = client
    register(test_client, "alice", "password123")
    alice_token = login(test_client, "alice", "password123")
    test_client.headers["Authorization"] = f"Bearer {alice_token}"
    created = test_client.post(
        "/heroes",
        json={
            "nom": "Aragorn",
            "classe": "guerrier",
            "force": 6,
            "agilite": 2,
            "intelligence": 2,
        },
    )
    assert created.status_code == 201
    hero_id = created.json()["id"]

    register(test_client, "bob", "password456")
    bob_token = login(test_client, "bob", "password456")
    test_client.headers["Authorization"] = f"Bearer {bob_token}"

    assert test_client.get("/heroes").json() == []
    hero_response = test_client.get(f"/heroes/{hero_id}")
    room_response = test_client.get(f"/heroes/{hero_id}/room")
    move_response = test_client.post(
        f"/heroes/{hero_id}/move",
        json={"direction": "nord"},
    )
    assert hero_response.status_code == 403
    assert hero_response.json()["detail"]["error"] == "NOT_YOUR_HERO"
    assert room_response.status_code == 403
    assert room_response.json()["detail"]["error"] == "NOT_YOUR_HERO"
    assert move_response.status_code == 403
    assert move_response.json()["detail"]["error"] == "NOT_YOUR_HERO"
    attack_response = test_client.post(f"/heroes/{hero_id}/attack")
    rest_response = test_client.post(f"/heroes/{hero_id}/rest")
    assert attack_response.status_code == 403
    assert attack_response.json()["detail"]["error"] == "NOT_YOUR_HERO"
    assert rest_response.status_code == 403
    assert rest_response.json()["detail"]["error"] == "NOT_YOUR_HERO"


def test_heroes_require_authentication(client) -> None:
    test_client, _engine = client

    requests = [
        test_client.get("/heroes"),
        test_client.get("/heroes/1"),
        test_client.get("/heroes/1/room"),
        test_client.post("/heroes/1/move", json={"direction": "nord"}),
        test_client.post("/heroes/1/attack"),
        test_client.post("/heroes/1/rest"),
    ]
    assert [response.status_code for response in requests] == [401] * len(requests)


def test_public_api_routes_have_response_models_and_tags() -> None:
    from fastapi.routing import APIRoute

    from app.main import app

    api_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and (route.path.startswith("/heroes") or route.path.startswith("/auth") or route.path == "/health")
    ]

    assert api_routes
    assert all(route.response_model is not None for route in api_routes)
    assert all(route.tags for route in api_routes)
