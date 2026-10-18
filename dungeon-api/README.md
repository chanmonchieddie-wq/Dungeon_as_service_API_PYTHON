# Dungeon as a Service — starter

Squelette fourni pour le projet bonus du module Python Backend & FastAPI.

## Installation (à faire une seule fois)

Prérequis : Python 3.10 ou plus récent (`python --version`).

```bash
# 1. Créer et activer un environnement virtuel
python -m venv .venv
# Windows (PowerShell) :
.venv\Scripts\Activate.ps1
# macOS / Linux :
source .venv/bin/activate

# 2. Installer les dépendances
pip install -r requirements.txt
```

## Lancer l'API

Depuis la racine du projet (le dossier qui contient `app/`) :

```bash
fastapi dev app/main.py
```

Ouvrez ensuite http://127.0.0.1:8000/docs : la route `GET /health` doit répondre
`{"status": "ok", ...}`. Si c'est le cas, vous êtes prêts.

## Palier 1 — Création d'un héros

Dans Swagger (`POST /heroes`), envoyez par exemple :

```json
{
  "nom": "Aragorn",
  "classe": "guerrier",
  "force": 6,
  "agilite": 2,
  "intelligence": 2
}
```

Le nom doit contenir de 3 à 20 caractères, la classe doit être `guerrier`, `mage`
ou `voleur`, et chaque statistique doit être comprise entre 1 et 8. Leur somme doit être exactement 10. Une création réussie renvoie le héros avec
le code 201, ses PV maximum (`20 + force × 2`) et la salle de départ. Une requête
invalide renvoie le code 422.

## Palier 1 — Consultation des héros

- `GET /heroes` renvoie la liste des héros enregistrés (liste vide si aucun héros
  n'existe).
- `GET /heroes/{id}` renvoie le héros correspondant à son identifiant.
- Si l'identifiant n'existe pas, l'API renvoie 404 avec le format structuré
  `{"detail":{"error":"HERO_NOT_FOUND","message":"..."}}`.

## Palier 2 — Persistance des héros

Les héros sont stockés dans la base SQLite `dungeon.db` à l'aide de SQLModel.
La table est créée au démarrage de l'API et les héros restent enregistrés après
un redémarrage du serveur.

## Palier 2 — Exploration du donjon

- `GET /heroes/{id}/room` décrit la salle actuelle : identifiant, nom,
  description, sorties et monstre en combat éventuel.
- `POST /heroes/{id}/move` reçoit une direction (`nord`, `sud`, `est` ou `ouest`)
  et renvoie la nouvelle salle. Une direction non valide renvoie 422 ; une sortie
  inexistante renvoie 400 avec `{"detail":{"error":"NO_EXIT","message":"..."}}`.
- Entrer dans une salle hantée démarre un combat contre son monstre avec ses PV
  au maximum. L'état du monstre courant est sauvegardé avec le héros.

Au démarrage, les colonnes d'état de combat sont ajoutées automatiquement à une
base SQLite existante ; les héros déjà enregistrés sont conservés.

## Palier 3 — Combat et états du héros

`POST /heroes/{id}/attack` joue un tour : le héros attaque d'abord, puis le
monstre riposte s'il survit. La réponse inclut dégâts infligés/subis, PV restants,
l'issue du tour, l'or gagné et l'indicateur de victoire. Le voleur réussit un
coup critique avec une chance sur trois.

Les dégâts sont calculés dans les classes métier de `app/domain/heroes.py` :
guerrier `2 + force × 2` (armure : dégâts reçus réduits de 1, minimum 1),
mage `1 + intelligence × 3`, voleur `2 + agilité × 2` (doublés en cas de critique).
Les PV maximum valent `20 + force × 2`.

Un héros en combat ne peut pas se déplacer ; un héros mort ne peut ni se déplacer
ni attaquer. Ces actions renvoient une erreur 409 avec le code `IN_COMBAT`,
`NO_MONSTER` ou `HERO_DEAD`. Les réponses de héros exposent `en_combat`,
`est_vivant`, `or_` et `victoire`, sans révéler les colonnes internes du combat
ni `owner_id`.

## Palier 3 — Repos

`POST /heroes/{id}/rest` attend trois secondes de manière asynchrone puis restaure
tous les PV du héros. Le repos est refusé avec une erreur 409 (`IN_COMBAT`) en
combat ou (`HERO_DEAD`) si le héros est mort.

## Palier 4 — Authentification et propriété des héros

- `POST /auth/register` crée un compte avec `username` et `password`. Les mots de
  passe sont hachés et ne sont jamais renvoyés par l'API.
- `POST /auth/login` utilise le formulaire OAuth2 (`username`, `password`) et
  renvoie un jeton JWT à utiliser dans Swagger avec **Authorize**.
- Toutes les routes `/heroes` nécessitent `Authorization: Bearer <token>`.
  Chaque joueur ne voit et ne peut utiliser que ses propres héros. Tenter
  d'accéder au héros d'un autre joueur renvoie 403 (`NOT_YOUR_HERO`).
- Les jetons expirent après 30 minutes. Définissez une valeur secrète aléatoire
  via `JWT_SECRET_KEY` avant tout déploiement ; la valeur intégrée par défaut
  sert uniquement au développement local.

Les colonnes `owner_id`, `salle_actuelle`, `monstre_pv`, `or_` et `victoire` sont
ajoutées automatiquement aux bases SQLite existantes. Les anciennes valeurs
`gold`, `salle` et `combat_monster_hp` sont migrées vers les champs actuels.
Les héros déjà présents ne sont pas supprimés ; les anciens héros sans
propriétaire ne sont pas visibles par les nouveaux comptes.

## Structure

```
app/
  main.py              point d'entrée, branchement des routers
  database.py          connexion SQLite (FOURNI)
  models/              tables SQLModel
  schemas/             schémas Pydantic d'entrée et de sortie
  domain/              classes métier (Heros, Guerrier, Mage, Voleur)
  services/            logique du jeu
    hero_service.py    création, déplacement, combat et repos
    dungeon_map.py     lecture de la carte (FOURNI)
  routes/              routers FastAPI
data/dungeon_map.json  carte du donjon (FOURNI, ne pas modifier)
client/play.py         client terminal (BONUS)
```

## Jouer depuis le terminal

Lance d'abord l'API dans un terminal, depuis la racine du projet :

```powershell
fastapi dev app/main.py
```

Dans un **second terminal**, active l'environnement virtuel si nécessaire puis
crée un compte et connecte-toi. La connexion sauvegarde le JWT dans `.token` à la
racine du projet :

```powershell
.\.venv\Scripts\Activate.ps1
python client/play.py register --username alice --password secret123
python client/play.py login --username alice --password secret123
```

Crée ensuite un héros. Les trois statistiques doivent totaliser exactement 10.
Note l'identifiant affiché après la création (par exemple `1`) :

```powershell
python client/play.py create --name Aragorn --classe guerrier --force 6 --agilite 2 --intelligence 2
python client/play.py look --hero 1
```

Déplace le héros, consulte sa salle, attaque les monstres et repose-toi après
les combats. Le programme affiche les réponses de l'API et ses erreurs :

```powershell
python client/play.py move --hero 1 --direction nord
python client/play.py attack --hero 1
python client/play.py rest --hero 1
python client/play.py look --hero 1
```

Commandes disponibles : `register`, `login`, `create`, `look`, `move`, `attack`
et `rest`. Le fichier `.token` est ignoré par Git. Pour changer l'adresse du
serveur, passe `--api-url http://adresse:port` avant la sous-commande, par
exemple `python client/play.py --api-url http://127.0.0.1:8000 login ...`.

## Réinitialiser la partie

Arrêtez le serveur et supprimez le fichier `dungeon.db` : il sera recréé au prochain lancement.
À faire aussi si vous ajoutez une colonne à une table (SQLite ne met pas à jour une table existante).

---

## Notre rendu

- **Membres du groupe :** Lovaniaina Sitraka, Rakhis Mannany et Eddie Chan.
- **Lien du dépôt Git :** [Dungeon_as_service_API_PYTHON](https://github.com/lovaniainasitraka/Dungeon_as_service_API_PYTHON)
- **Palier atteint :** Palier 4 — fonctionnalités FT-1 à FT-11, incluant l'authentification et la propriété des héros.
- **Bonus réalisés :** client de jeu en terminal (`client/play.py`) avec inscription, connexion, création de héros, exploration, combat et repos ; migration des bases SQLite existantes en conservant les héros enregistrés.
- **Ce qui ne fonctionne pas / difficultés :** aucun problème connu à la date du rendu. La suite de tests passe (44 tests).
