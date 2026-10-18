"""Chargement de la carte du donjon — FOURNI.

La carte est lue une seule fois depuis data/dungeon_map.json.
Vous pouvez utiliser directement les fonctions ci-dessous dans vos services.
"""

import json
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parents[2] / "data" / "dungeon_map.json"

with MAP_PATH.open(encoding="utf-8") as f:
    _MAP = json.load(f)

START_ROOM: str = _MAP["start_room"]
FINAL_ROOM: str = _MAP["final_room"]


def get_room(room_id: str) -> dict | None:
    """Renvoie la salle (name, description, exits, monster) ou None si elle n'existe pas."""
    return _MAP["rooms"].get(room_id)


def get_monster(monster_id: str) -> dict | None:
    """Renvoie le modèle de monstre (name, hp, attack, gold) ou None."""
    return _MAP["monsters"].get(monster_id)


def get_monster_of_room(room_id: str) -> dict | None:
    """Raccourci : le monstre qui hante une salle, ou None si la salle est sûre."""
    room = get_room(room_id)
    if room is None or room["monster"] is None:
        return None
    return get_monster(room["monster"])
