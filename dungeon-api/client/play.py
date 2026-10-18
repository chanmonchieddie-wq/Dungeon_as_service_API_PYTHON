"""Client terminal pour jouer à Dungeon as a Service.

Lancez l'API dans un autre terminal, puis utilisez :
    python client/play.py register --username alice --password secret123
    python client/play.py login --username alice --password secret123
    python client/play.py create --name Aragorn --classe guerrier --force 6 --agilite 2 --intelligence 2
    python client/play.py look --hero 1
    python client/play.py move --hero 1 --direction nord
    python client/play.py attack --hero 1
    python client/play.py rest --hero 1
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

import requests

API_URL = os.getenv("DUNGEON_API_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN_PATH = Path(__file__).resolve().parents[1] / ".token"
REQUEST_TIMEOUT_SECONDS = 10


class ApiError(Exception):
    pass


def request_api(
    method: str,
    path: str,
    *,
    authenticated: bool = False,
    **kwargs: Any,
) -> Any:
    headers = kwargs.pop("headers", {})
    if authenticated:
        token = read_token()
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method,
            f"{API_URL}{path}",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            **kwargs,
        )
    except requests.RequestException as error:
        raise ApiError(
            f"Impossible de joindre l'API ({error}). Vérifie que le serveur tourne."
        ) from error

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError:
        payload = response.text or f"Réponse HTTP {response.status_code} sans contenu."

    if not response.ok:
        raise ApiError(
            f"Erreur HTTP {response.status_code} : "
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
    return payload


def read_token() -> str:
    try:
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ApiError(
            "Aucun jeton trouvé. Connecte-toi d'abord avec la commande login."
        ) from error
    if not token:
        raise ApiError("Le fichier .token est vide. Relance la commande login.")
    return token


def print_result(result: Any) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Jouer à Dungeon as a Service depuis le terminal."
    )
    parser.add_argument(
        "--api-url",
        default=API_URL,
        help=f"URL de l'API (défaut : {API_URL})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register", help="Créer un compte joueur")
    register_parser.add_argument("--username", required=True)
    register_parser.add_argument("--password", required=True)

    login_parser = subparsers.add_parser("login", help="Se connecter et sauvegarder le jeton")
    login_parser.add_argument("--username", required=True)
    login_parser.add_argument("--password", required=True)

    create_parser = subparsers.add_parser("create", help="Créer un héros")
    create_parser.add_argument("--name", "--nom", dest="name", required=True)
    create_parser.add_argument(
        "--classe",
        required=True,
        choices=("guerrier", "mage", "voleur"),
    )
    create_parser.add_argument("--force", type=int, required=True)
    create_parser.add_argument("--agilite", type=int, required=True)
    create_parser.add_argument("--intelligence", type=int, required=True)

    look_parser = subparsers.add_parser("look", help="Consulter le héros et sa salle")
    look_parser.add_argument("--hero", type=int, required=True)

    move_parser = subparsers.add_parser("move", help="Déplacer le héros")
    move_parser.add_argument("--hero", type=int, required=True)
    move_parser.add_argument(
        "--direction",
        required=True,
        choices=("nord", "sud", "est", "ouest"),
    )

    attack_parser = subparsers.add_parser("attack", help="Attaquer le monstre")
    attack_parser.add_argument("--hero", type=int, required=True)

    rest_parser = subparsers.add_parser("rest", help="Récupérer tous les PV")
    rest_parser.add_argument("--hero", type=int, required=True)

    return parser


def run_command(args: argparse.Namespace) -> None:
    global API_URL
    API_URL = args.api_url.rstrip("/")

    if args.command == "register":
        result = request_api(
            "POST",
            "/auth/register",
            json={"username": args.username, "password": args.password},
        )
        print("Compte créé :")
        print_result(result)
    elif args.command == "login":
        result = request_api(
            "POST",
            "/auth/login",
            data={"username": args.username, "password": args.password},
        )
        try:
            TOKEN_PATH.write_text(result["access_token"], encoding="utf-8")
        except (KeyError, OSError) as error:
            raise ApiError(f"Impossible de sauvegarder le jeton dans {TOKEN_PATH}.") from error
        print(f"Connexion réussie. Jeton sauvegardé dans {TOKEN_PATH.name}.")
    elif args.command == "create":
        result = request_api(
            "POST",
            "/heroes",
            authenticated=True,
            json={
                "nom": args.name,
                "classe": args.classe,
                "force": args.force,
                "agilite": args.agilite,
                "intelligence": args.intelligence,
            },
        )
        print("Héros créé :")
        print_result(result)
    elif args.command == "look":
        hero = request_api("GET", f"/heroes/{args.hero}", authenticated=True)
        room = request_api(
            "GET",
            f"/heroes/{args.hero}/room",
            authenticated=True,
        )
        print("Héros :")
        print_result(hero)
        print("Salle actuelle :")
        print_result(room)
    elif args.command == "move":
        result = request_api(
            "POST",
            f"/heroes/{args.hero}/move",
            authenticated=True,
            json={"direction": args.direction},
        )
        print("Nouvelle salle :")
        print_result(result)
    elif args.command == "attack":
        result = request_api(
            "POST",
            f"/heroes/{args.hero}/attack",
            authenticated=True,
        )
        print("Résultat du combat :")
        print_result(result)
    elif args.command == "rest":
        result = request_api(
            "POST",
            f"/heroes/{args.hero}/rest",
            authenticated=True,
        )
        print("Le héros s'est reposé :")
        print_result(result)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run_command(args)
    except ApiError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
