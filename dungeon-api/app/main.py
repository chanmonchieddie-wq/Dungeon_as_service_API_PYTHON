"""Point d'entrée de l'API Dungeon as a Service.

Lancer le serveur depuis la racine du projet :
    fastapi dev app/main.py
Puis ouvrir http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import create_db_and_tables, engine
from app.models.hero import Hero  # noqa: F401
from app.models.player import Player  # noqa: F401
from app.routes.auth import router as auth_router
from app.routes.heroes import router as heroes_router
from app.schemas.system import HealthRead
from app.services.hero_migrations import migrate_hero_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Exécuté une fois au démarrage du serveur : crée les tables si besoin
    create_db_and_tables()
    migrate_hero_schema(engine)
    yield


app = FastAPI(
    title="Dungeon as a Service",
    description="Moteur de jeu de rôle textuel — Pixel Crypt",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(heroes_router)
app.include_router(auth_router)


@app.get("/health", response_model=HealthRead, tags=["Système"])
def health() -> HealthRead:
    """Vérifie que le serveur répond."""
    return HealthRead(status="ok", message="Le donjon vous attend...")
