"""Security integration tests (Sections 25, 71, 72).

Verifies the client cannot bypass server authority and that no private
information leaks through the API.
"""
from conftest import client_headers


def _auth_header_from(data):
    return client_headers(data["tokens"]["access_token"])


def test_protected_endpoint_without_token(client):
    r = client.get("/api/v1/users/me")
    assert r.status_code == 401


def test_protected_endpoint_with_bad_token(client):
    r = client.get("/api/v1/users/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_cannot_read_others_private_me(client, tg_auth):
    u1 = tg_auth(client, 2001)
    u2 = tg_auth(client, 2002)
    r = client.get("/api/v1/users/me", headers=_auth_header_from(u1))
    assert r.json()["user"]["id"] == u1["user"]["id"]


def test_game_view_rejects_non_participant_and_does_not_leak(client, tg_auth):
    u = tg_auth(client, 3001)
    h = _auth_header_from(u)
    r = client.post("/api/v1/rooms", json={}, headers=h)
    assert r.status_code == 200
    room = r.json()

    u2 = tg_auth(client, 3002)
    h2 = _auth_header_from(u2)
    r = client.post("/api/v1/rooms/join", json={"invite_code": room["invite_code"]}, headers=h2)
    assert r.status_code == 200

    client.post(f"/api/v1/rooms/{room['id']}/ready", json={"ready": True}, headers=h)
    client.post(f"/api/v1/rooms/{room['id']}/ready", json={"ready": True}, headers=h2)
    r = client.post(f"/api/v1/rooms/{room['id']}/start", json={}, headers=h)
    assert r.status_code == 200, r.text

    game_service = client.app.state.game_service
    gid = next(gid for gid, rt in game_service.registry.items() if not rt.finished)

    # A third party (not in the game) must be rejected.
    u3 = tg_auth(client, 3003)
    h3 = _auth_header_from(u3)
    assert client.get(f"/api/v1/games/{gid}/view", headers=h3).status_code == 403

    rt = game_service.registry[gid]
    # Every participant's view must never contain another seat's unrevealed card.
    for p in rt.players:
        if p.is_bot:
            continue
        view = game_service.view_payload(rt, p.seat)
        visible = set(view["hand"])
        for row in view["table"]:
            visible.update(row["played"])
        for s, c in view["trick"].get("plays", []):
            visible.add(c)
        for other in range(4):
            if other == p.seat:
                continue
            other_remaining = {c.id for c in rt.engine.hand(other)}
            assert not (visible & other_remaining), f"leak from seat {other}"
