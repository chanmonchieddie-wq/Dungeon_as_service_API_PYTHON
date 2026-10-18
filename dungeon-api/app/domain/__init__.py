"""Classes métier (POO), sans dépendance à FastAPI ni à la base de données."""

from app.domain.heroes import Guerrier, Heros, Mage, Voleur, creer_heros

__all__ = ["Guerrier", "Heros", "Mage", "Voleur", "creer_heros"]
