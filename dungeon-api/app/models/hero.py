from sqlmodel import Field, SQLModel


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    classe: str
    force: int
    agilite: int
    intelligence: int
    pv: int = 20
    pv_max: int = 20
    salle_actuelle: str
    monstre_pv: int | None = None
    or_: int = Field(default=0)
    victoire: bool = False
    owner_id: int | None = Field(default=None, foreign_key="player.id")

    @property
    def en_combat(self) -> bool:
        return self.monstre_pv is not None

    @property
    def est_vivant(self) -> bool:
        return self.pv > 0
