from typing import Literal

from pydantic import BaseModel, Field, model_validator


class HeroCreate(BaseModel):
    nom: str = Field(min_length=3, max_length=20)
    classe: Literal["guerrier", "mage", "voleur"]
    force: int = Field(ge=1, le=8)
    agilite: int = Field(ge=1, le=8)
    intelligence: int = Field(ge=1, le=8)

    @model_validator(mode="after")
    def stats_total_ten(self) -> "HeroCreate":
        if self.force + self.agilite + self.intelligence != 10:
            raise ValueError("La somme de force, agilite et intelligence doit être égale à 10.")
        return self


class HeroRead(BaseModel):
    id: int
    nom: str
    classe: str
    force: int
    agilite: int
    intelligence: int
    pv: int
    pv_max: int
    salle_actuelle: str
    or_: int
    victoire: bool
    en_combat: bool
    est_vivant: bool

    model_config = {"from_attributes": True}
