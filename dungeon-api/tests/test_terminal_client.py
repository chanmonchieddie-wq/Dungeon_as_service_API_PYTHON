from types import SimpleNamespace

from client import play


def test_terminal_client_runs_game_commands_and_saves_bearer_token(
    monkeypatch,
    tmp_path,
) -> None:
    token_path = tmp_path / ".token"
    calls: list[dict] = []
    monkeypatch.setattr(play, "TOKEN_PATH", token_path)

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        if url.endswith("/auth/login"):
            payload = {"access_token": "jwt-test-token", "token_type": "bearer"}
        elif url.endswith("/heroes/1/attack"):
            payload = {"issue": "monstre_vaincu", "or_gagne": 10}
        elif url.endswith("/heroes/1/rest"):
            payload = {"pv": 32, "pv_max": 32}
        else:
            payload = {"id": 1, "username": "alice"}
        return SimpleNamespace(ok=True, json=lambda: payload, text="", status_code=200)

    monkeypatch.setattr(play.requests, "request", fake_request)

    commands = [
        [
            "register",
            "--username",
            "alice",
            "--password",
            "password123",
        ],
        ["login", "--username", "alice", "--password", "password123"],
        [
            "create",
            "--name",
            "Aragorn",
            "--classe",
            "guerrier",
            "--force",
            "6",
            "--agilite",
            "2",
            "--intelligence",
            "2",
        ],
        ["look", "--hero", "1"],
        ["move", "--hero", "1", "--direction", "nord"],
        ["attack", "--hero", "1"],
        ["rest", "--hero", "1"],
    ]

    for command in commands:
        assert play.main(command) == 0

    assert token_path.read_text(encoding="utf-8") == "jwt-test-token"
    assert [call["url"].removeprefix("http://127.0.0.1:8000") for call in calls] == [
        "/auth/register",
        "/auth/login",
        "/heroes",
        "/heroes/1",
        "/heroes/1/room",
        "/heroes/1/move",
        "/heroes/1/attack",
        "/heroes/1/rest",
    ]
    assert calls[0]["json"] == {
        "username": "alice",
        "password": "password123",
    }
    assert calls[1]["data"] == {
        "username": "alice",
        "password": "password123",
    }
    assert calls[2]["headers"]["Authorization"] == "Bearer jwt-test-token"
    assert calls[-1]["headers"]["Authorization"] == "Bearer jwt-test-token"


def test_authenticated_terminal_command_requires_saved_token(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(play, "TOKEN_PATH", tmp_path / ".token")

    result = play.main(["look", "--hero", "1"])

    assert result == 1
    assert "commande login" in capsys.readouterr().err
