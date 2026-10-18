import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.domain.heroes import Guerrier, Mage, Voleur
from app.models.hero import Hero
from app.routes.auth import router as auth_router
from app.routes.heroes import router
from app.services.dungeon_map import FINAL_ROOM


@pytest.fixture
def test_engine(tmp_path):
    engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "combat.db")),
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


def create_hero(client: TestClient, classe: str = "guerrier") -> int:
    stats = {
        "guerrier": {"force": 6, "agilite": 2, "intelligence": 2},
        "mage": {"force": 2, "agilite": 2, "intelligence": 6},
        "voleur": {"force": 2, "agilite": 6, "intelligence": 2},
    }
    response = client.post(
        "/heroes",
        json={"nom": "Aragorn", "classe": classe, **stats[classe]},
    )
    assert response.status_code == 201
    return response.json()["id"]


def reach_ogre_room(client: TestClient, hero_id: int) -> None:
    for direction in ("nord", "nord"):
        response = client.post(
            f"/heroes/{hero_id}/move",
            json={"direction": direction},
        )
        assert response.status_code == 200
    rat_response = client.post(f"/heroes/{hero_id}/attack")
    assert rat_response.status_code == 200
    assert rat_response.json()["issue"] == "monstre_vaincu"
    response = client.post(f"/heroes/{hero_id}/move", json={"direction": "nord"})
    assert response.status_code == 200


def test_domain_damage_and_max_hp_formulas() -> None:
    warrior = Guerrier(force=6, agilite=2, intelligence=2)
    mage = Mage(force=2, agilite=2, intelligence=6)

    assert warrior.pv_max == 32
    assert warrior.calculer_degats() == (14, False)
    assert warrior.subir_degats(6) == 5
    assert warrior.subir_degats(1) == 1
    assert mage.pv_max == 24
    assert mage.calculer_degats() == (19, False)
    assert mage.subir_degats(6) == 6


def test_thief_critical_hit_is_double_damage(monkeypatch: pytest.MonkeyPatch) -> None:
    thief = Voleur(force=2, agilite=6, intelligence=2)
    monkeypatch.setattr(
        "app.domain.heroes.random.randint",
        lambda low, high: low if high == 3 else high,
    )

    assert thief.pv_max == 24
    assert thief.calculer_degats() == (28, True)
    assert thief.subir_degats(6) == 6


def test_thief_noncritical_hit_has_normal_damage(monkeypatch: pytest.MonkeyPatch) -> None:
    thief = Voleur(force=2, agilite=6, intelligence=2)
    monkeypatch.setattr(
        "app.domain.heroes.random.randint",
        lambda low, high: low + high - 1,
    )

    assert thief.calculer_degats() == (14, False)


def test_attack_without_monster_returns_no_monster(client: TestClient) -> None:
    hero_id = create_hero(client)

    response = client.post(f"/heroes/{hero_id}/attack")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "NO_MONSTER"


def test_move_during_combat_returns_in_combat(client: TestClient) -> None:
    hero_id = create_hero(client)
    reach_ogre_room(client, hero_id)

    response = client.post(f"/heroes/{hero_id}/move", json={"direction": "sud"})

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "IN_COMBAT"


def test_warrior_attack_and_monster_riposte(client: TestClient) -> None:
    hero_id = create_hero(client)
    reach_ogre_room(client, hero_id)

    response = client.post(f"/heroes/{hero_id}/attack")

    assert response.status_code == 200
    assert response.json() == {
        "degats_infliges": 14,
        "critique": False,
        "degats_subis": 5,
        "pv_heros": 27,
        "pv_monstre": 16,
        "issue": "en_cours",
        "or_gagne": 0,
        "victoire": False,
    }


def test_mage_attack_uses_intelligence_damage(client: TestClient) -> None:
    hero_id = create_hero(client, "mage")
    client.post(f"/heroes/{hero_id}/move", json={"direction": "nord"})
    client.post(f"/heroes/{hero_id}/move", json={"direction": "ouest"})

    response = client.post(f"/heroes/{hero_id}/attack")

    assert response.status_code == 200
    assert response.json()["degats_infliges"] == 19
    assert response.json()["pv_monstre"] == 0
    assert response.json()["degats_subis"] == 0


def test_killing_monster_awards_gold_and_clears_combat(
    client: TestClient,
    test_engine,
) -> None:
    hero_id = create_hero(client)
    reach_ogre_room(client, hero_id)
    hero_response = client.get(f"/heroes/{hero_id}")
    assert hero_response.status_code == 200
    session_response = client.post(f"/heroes/{hero_id}/attack")
    assert session_response.status_code == 200
    assert session_response.json()["issue"] == "en_cours"

    with Session(test_engine) as session:
        hero = session.get(Hero, hero_id)
        assert hero is not None
        hero.monstre_pv = 1
        session.add(hero)
        session.commit()

    response = client.post(f"/heroes/{hero_id}/attack")

    assert response.status_code == 200
    assert response.json()["pv_monstre"] == 0
    assert response.json()["issue"] == "monstre_vaincu"
    assert response.json()["or_gagne"] == 40
    assert response.json()["degats_subis"] == 0
    hero_after_attack = client.get(f"/heroes/{hero_id}").json()
    assert hero_after_attack["en_combat"] is False
    assert hero_after_attack["or_"] == 45
    assert hero_after_attack["victoire"] is False


def test_monster_respawns_when_hero_reenters_its_room(client: TestClient) -> None:
    hero_id = create_hero(client)
    client.post(f"/heroes/{hero_id}/move", json={"direction": "nord"})
    client.post(f"/heroes/{hero_id}/move", json={"direction": "ouest"})
    defeated = client.post(f"/heroes/{hero_id}/attack")
    assert defeated.status_code == 200
    assert defeated.json()["issue"] == "monstre_vaincu"

    client.post(f"/heroes/{hero_id}/move", json={"direction": "est"})
    reentered = client.post(f"/heroes/{hero_id}/move", json={"direction": "ouest"})

    assert reentered.status_code == 200
    assert reentered.json()["monster"]["id"] == "gobelin"
    assert reentered.json()["monster"]["hp"] == 12


def test_killing_liche_reports_victory(client: TestClient, test_engine) -> None:
    hero_id = create_hero(client)
    with Session(test_engine) as session:
        hero = session.get(Hero, hero_id)
        assert hero is not None
        hero.salle_actuelle = FINAL_ROOM
        hero.monstre_pv = 1
        session.add(hero)
        session.commit()

    response = client.post(f"/heroes/{hero_id}/attack")

    assert response.status_code == 200
    assert response.json()["victoire"] is True
    assert response.json()["or_gagne"] == 100
    hero_response = client.get(f"/heroes/{hero_id}")
    assert hero_response.status_code == 200
    assert hero_response.json()["victoire"] is True
    assert hero_response.json()["or_"] == 100


def test_dead_hero_cannot_move_or_attack(client: TestClient, test_engine) -> None:
    hero_id = create_hero(client)
    reach_ogre_room(client, hero_id)
    with Session(test_engine) as session:
        hero = session.get(Hero, hero_id)
        assert hero is not None
        hero.pv = 0
        session.add(hero)
        session.commit()

    move_response = client.post(
        f"/heroes/{hero_id}/move",
        json={"direction": "sud"},
    )
    attack_response = client.post(f"/heroes/{hero_id}/attack")

    assert move_response.status_code == 409
    assert move_response.json()["detail"]["error"] == "HERO_DEAD"
    assert attack_response.status_code == 409
    assert attack_response.json()["detail"]["error"] == "HERO_DEAD"
    rest_response = client.post(f"/heroes/{hero_id}/rest")
    assert rest_response.status_code == 409
    assert rest_response.json()["detail"]["error"] == "HERO_DEAD"


def test_rest_heals_hero_after_three_seconds(
    client: TestClient,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hero_id = create_hero(client)
    with Session(test_engine) as session:
        hero = session.get(Hero, hero_id)
        assert hero is not None
        hero.pv = 7
        session.add(hero)
        session.commit()

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.hero_service.asyncio.sleep", fake_sleep)
    response = client.post(f"/heroes/{hero_id}/rest")

    assert response.status_code == 200
    assert sleep_calls == [3]
    assert response.json()["pv"] == 32
    assert response.json()["or_"] == 0


def test_rest_during_combat_returns_in_combat(client: TestClient) -> None:
    hero_id = create_hero(client)
    client.post(f"/heroes/{hero_id}/move", json={"direction": "nord"})
    client.post(f"/heroes/{hero_id}/move", json={"direction": "ouest"})

    response = client.post(f"/heroes/{hero_id}/rest")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "IN_COMBAT"


def test_hero_can_die_from_monster_riposte_and_remains_consultable(
    client: TestClient,
    test_engine,
) -> None:
    hero_id = create_hero(client)
    reach_ogre_room(client, hero_id)
    with Session(test_engine) as session:
        hero = session.get(Hero, hero_id)
        assert hero is not None
        hero.pv = 1
        session.add(hero)
        session.commit()

    attack_response = client.post(f"/heroes/{hero_id}/attack")
    hero_response = client.get(f"/heroes/{hero_id}")

    assert attack_response.status_code == 200
    assert attack_response.json()["issue"] == "heros_mort"
    assert attack_response.json()["pv_heros"] == 0
    assert hero_response.status_code == 200
    assert hero_response.json()["est_vivant"] is False
    assert hero_response.json()["en_combat"] is True


def test_hero_response_hides_combat_storage_fields(client: TestClient) -> None:
    hero_id = create_hero(client)

    response = client.get(f"/heroes/{hero_id}")

    assert response.status_code == 200
    assert response.json()["en_combat"] is False
    assert response.json()["est_vivant"] is True
    assert "monstre_pv" not in response.json()
    assert "owner_id" not in response.json()
    assert "gold" not in response.json()
    assert "salle" not in response.json()
