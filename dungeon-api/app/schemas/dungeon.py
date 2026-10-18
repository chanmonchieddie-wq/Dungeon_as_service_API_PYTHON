from typing import Literal

from pydantic import BaseModel


class HeroMove(BaseModel):
    direction: Literal["nord", "sud", "est", "ouest"]


class MonsterRead(BaseModel):
    id: str
    name: str
    hp: int
    attack: int
    gold: int


class RoomRead(BaseModel):
    id: str
    name: str
    description: str
    exits: dict[str, str]
    monster: MonsterRead | None


class CombatRead(BaseModel):
    degats_infliges: int
    critique: bool
    degats_subis: int
    pv_heros: int
    pv_monstre: int
    issue: Literal["en_cours", "monstre_vaincu", "heros_mort"]
    or_gagne: int
    victoire: bool
