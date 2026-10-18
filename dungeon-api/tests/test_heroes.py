import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.engine import URL
from sqlmodel import Session, SQLModel, create_engine, select

from app.database import get_session
from app.models.hero import Hero
from app.routes.auth import router as auth_router
from app.routes.heroes import router
from app.services.dungeon_map import START_ROOM, get_room
from app.services.hero_migrations import migrate_hero_schema


@pytest.fixture
def test_engine(tmp_path):
    engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "test.db")),
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(test_engine):

    def get_test_session():
        with Session(test_engine) as session:
            yield session

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.include_router(auth_router)
    test_app.dependency_overrides[get_session] = get_test_session

    with TestClient(test_app) as test_client:
        registration = test_client.post(
            "/auth/register",
            json={"username": "test-player", "password": "test-password"},
        )
        assert registration.status_code == 201
        login = test_client.post(
            "/auth/login",
            data={"username": "test-player", "password": "test-password"},
        )
        assert login.status_code == 200
        test_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield test_client


def test_create_hero(client: TestClient) -> None:
    response = client.post(
        "/heroes",
        json={
            "nom": "Aragorn",
            "classe": "guerrier",
            "force": 6,
            "agilite": 2,
            "intelligence": 2,
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "nom": "Aragorn",
        "classe": "guerrier",
        "force": 6,
        "agilite": 2,
        "intelligence": 2,
        "pv": 32,
        "pv_max": 32,
        "salle_actuelle": START_ROOM,
        "or_": 0,
        "victoire": False,
        "en_combat": False,
        "est_vivant": True,
    }


def test_list_heroes(client: TestClient) -> None:
    client.post(
        "/heroes",
        json={
            "nom": "Aragorn",
            "classe": "guerrier",
            "force": 6,
            "agilite": 2,
            "intelligence": 2,
        },
    )

    response = client.get("/heroes")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["nom"] == "Aragorn"


def test_get_hero_by_id(client: TestClient) -> None:
    created = client.post(
        "/heroes",
        json={
            "nom": "Aragorn",
            "classe": "guerrier",
            "force": 6,
            "agilite": 2,
            "intelligence": 2,
        },
    )

    response = client.get(f"/heroes/{created.json()['id']}")

    assert response.status_code == 200
    assert response.json() == created.json()


def test_get_unknown_hero_returns_structured_404(client: TestClient) -> None:
    response = client.get("/heroes/9999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "error": "HERO_NOT_FOUND",
            "message": "Héros avec l'identifiant 9999 introuvable.",
        }
    }


def create_test_hero(client: TestClient) -> int:
    response = client.post(
        "/heroes",
        json={
            "nom": "Aragorn",
            "classe": "guerrier",
            "force": 6,
            "agilite": 2,
            "intelligence": 2,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_get_hero_room_returns_room_details(client: TestClient) -> None:
    hero_id = create_test_hero(client)
    start_room = get_room(START_ROOM)
    assert start_room is not None

    response = client.get(f"/heroes/{hero_id}/room")

    assert response.status_code == 200
    assert response.json() == {
        "id": START_ROOM,
        "name": start_room["name"],
        "description": start_room["description"],
        "exits": start_room["exits"],
        "monster": None,
    }


def test_get_hero_room_returns_404_for_unknown_hero(client: TestClient) -> None:
    response = client.get("/heroes/9999/room")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "HERO_NOT_FOUND"


def test_move_hero_to_hall(client: TestClient) -> None:
    hero_id = create_test_hero(client)
    hall = get_room("hall")
    assert hall is not None

    response = client.post(f"/heroes/{hero_id}/move", json={"direction": "nord"})

    assert response.status_code == 200
    assert response.json()["id"] == "hall"
    assert response.json()["name"] == hall["name"]
    assert response.json()["monster"] is None
    assert client.get(f"/heroes/{hero_id}").json()["salle_actuelle"] == "hall"


def test_move_into_haunted_room_starts_combat_at_full_hp(
    client: TestClient,
) -> None:
    hero_id = create_test_hero(client)
    client.post(f"/heroes/{hero_id}/move", json={"direction": "nord"})

    response = client.post(f"/heroes/{hero_id}/move", json={"direction": "ouest"})

    assert response.status_code == 200
    room_data = response.json()
    assert room_data["id"] == "bibliotheque"
    assert room_data["monster"] is not None
    assert room_data["monster"]["id"] == "gobelin"
    assert room_data["monster"]["hp"] == 12
    assert room_data["monster"]["name"] == "Gobelin"
    hero_response = client.get(f"/heroes/{hero_id}")
    assert hero_response.status_code == 200
    assert hero_response.json()["en_combat"] is True
    assert hero_response.json()["est_vivant"] is True
    room_response = client.get(f"/heroes/{hero_id}/room")
    assert room_response.status_code == 200
    assert room_response.json()["monster"]["hp"] == 12


def test_move_without_exit_returns_structured_400(client: TestClient) -> None:
    hero_id = create_test_hero(client)

    response = client.post(f"/heroes/{hero_id}/move", json={"direction": "est"})

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "error": "NO_EXIT",
            "message": "Il n'y a pas de passage vers le est.",
        }
    }
    assert client.get(f"/heroes/{hero_id}").json()["salle_actuelle"] == START_ROOM


def test_move_rejects_invalid_direction(client: TestClient) -> None:
    hero_id = create_test_hero(client)

    response = client.post(f"/heroes/{hero_id}/move", json={"direction": "haut"})

    assert response.status_code == 422


def test_move_returns_404_for_unknown_hero(client: TestClient) -> None:
    response = client.post("/heroes/9999/move", json={"direction": "nord"})

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "HERO_NOT_FOUND"


def test_hero_is_persisted_after_reopening_database(
    client: TestClient, test_engine
) -> None:
    client.post(
        "/heroes",
        json={
            "nom": "Aragorn",
            "classe": "guerrier",
            "force": 6,
            "agilite": 2,
            "intelligence": 2,
        },
    )
    database_url = test_engine.url
    test_engine.dispose()
    reopened_engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    try:
        with Session(reopened_engine) as session:
            persisted_hero = session.exec(select(Hero)).one()
    finally:
        reopened_engine.dispose()

    assert persisted_hero.nom == "Aragorn"


def test_migration_adds_combat_columns_without_losing_heroes(tmp_path) -> None:
    engine = create_engine(URL.create("sqlite", database=str(tmp_path / "legacy.db")))
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE hero (
                id INTEGER PRIMARY KEY,
                nom VARCHAR NOT NULL,
                classe VARCHAR NOT NULL,
                "force" INTEGER NOT NULL,
                agilite INTEGER NOT NULL,
                intelligence INTEGER NOT NULL,
                pv INTEGER NOT NULL,
                pv_max INTEGER NOT NULL,
                salle VARCHAR NOT NULL,
                gold INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO hero (
                id, nom, classe, "force", agilite, intelligence, pv, pv_max, salle, gold
            ) VALUES (1, 'Aragorn', 'guerrier', 6, 2, 2, 20, 20, 'entree', 7)
            """
        )

    migrate_hero_schema(engine)

    column_names = {column["name"] for column in inspect(engine).get_columns("hero")}
    with Session(engine) as session:
        hero = session.get(Hero, 1)
        assert hero is not None
        assert hero.nom == "Aragorn"
        assert hero.pv == 32
        assert hero.pv_max == 32
        assert hero.or_ == 7
        assert hero.victoire is False
        assert hero.salle_actuelle == START_ROOM
        assert hero.owner_id is None

        session.add(
            Hero(
                nom="Legolas",
                classe="voleur",
                force=2,
                agilite=6,
                intelligence=2,
                pv=24,
                pv_max=24,
                salle_actuelle=START_ROOM,
            )
        )
        session.commit()
        created_hero_id = session.exec(
            select(Hero.id).where(Hero.nom == "Legolas")
        ).one()
    engine.dispose()

    assert "salle_actuelle" in column_names
    assert "salle" not in column_names
    assert "monstre_pv" in column_names
    assert "or_" in column_names
    assert "victoire" in column_names
    assert "owner_id" in column_names
    assert created_hero_id == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"nom": "Al"},
        {"nom": "A" * 21},
        {"classe": "paladin"},
        {"force": 0},
        {"agilite": 9},
        {"intelligence": 3},
    ],
)
def test_create_hero_rejects_invalid_data(client: TestClient, changes: dict) -> None:
    payload = {
        "nom": "Aragorn",
        "classe": "guerrier",
        "force": 6,
        "agilite": 2,
        "intelligence": 2,
    }
    payload.update(changes)

    response = client.post("/heroes", json=payload)

    assert response.status_code == 422
