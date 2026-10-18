"""Connexion à la base de données — FOURNI, rien à modifier pour les paliers 1 à 4.

Par défaut, la base est un fichier SQLite `dungeon.db` créé à la racine du projet.
Bonus PostgreSQL : il suffit de définir la variable d'environnement DATABASE_URL,
par exemple : postgresql+psycopg://dungeon:dungeon@localhost:5432/dungeon
"""

import os
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dungeon.db")

# check_same_thread n'est nécessaire (et accepté) que pour SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def create_db_and_tables() -> None:
    """Crée toutes les tables déclarées avec `table=True`.

    Attention : SQLModel ne connaît une table que si le module qui la déclare
    a été importé AVANT l'appel à cette fonction (voir app/main.py).
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dépendance FastAPI : fournit une session par requête.

    Utilisation dans une route :
        def ma_route(session: Session = Depends(get_session)): ...
    """
    with Session(engine) as session:
        yield session
