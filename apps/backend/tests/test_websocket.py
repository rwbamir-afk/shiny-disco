"""Real-time WebSocket tests (Sections 30, 31, 13).

Auth on connect, state delivery, ping/pong, action, and reconnect.
"""
from conftest import client_headers


def _start_room_game(client, tg_auth, start_id):
    u = tg_auth(client, start_id)
    u2 = tg_auth(client, start_id + 1)
    h = client_headers(u["tokens"]["access_token"])
    h2 = client_headers(u2["tokens"]["access_token"])
    r = client.post("/api/v1/rooms", json={}, headers=h)
    room = r.json()
    r = client.post("/api/v1/rooms/join", json={"invite_code": room["invite_code"]}, headers=h2)
    assert r.status_code == 200, r.text
    client.post(f"/api/v1/rooms/{room['id']}/ready", json={"ready": True}, headers=h)
    client.post(f"/api/v1/rooms/{room['id']}/ready", json={"ready": True}, headers=h2)
    game_service = client.app.state.game_service
    before = set(game_service.registry.keys())
    r = client.post(f"/api/v1/rooms/{room['id']}/start", json={}, headers=h)
    assert r.status_code == 200, r.text
    new = set(game_service.registry.keys()) - before
    assert new, "no new game created in registry"
    gid = next(iter(new))
    return u, gid


def _recv_until(ws, want_type, max_msg=10):
    """Read messages, tolerating interleaved pushes of other types."""
    for _ in range(max_msg):
        msg = ws.receive_json()
        if msg.get("type") == want_type:
            return msg
    return None


def test_ws_rejects_bad_token(client):
    import pytest

    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=garbage"):
            pass


def test_ws_state_and_reconnect(client, tg_auth):
    u, gid = _start_room_game(client, tg_auth, 7001)
    token = u["tokens"]["access_token"]

    with client.websocket_connect(f"/ws?token={token}") as ws:
        # Server pushes authoritative state on connect (reconnect flow).
        msg = _recv_until(ws, "game.state")
        assert msg is not None and msg["data"]["game_id"] == gid
        view = msg["data"]

        # ping -> pong (ignore any bot broadcasts interleaved).
        ws.send_json({"type": "ping", "ts": 1})
        assert _recv_until(ws, "pong") is not None

        # If it's this player's turn, drive one action and expect a fresh state.
        if view.get("is_my_turn"):
            card = view["legal_cards"][0]
            ws.send_json(
                {"type": "game.action", "game_id": gid,
                 "action": {"type": "play_card", "card": card, "request_id": f"{u['user']['id']}:ws1"}}
            )
            assert _recv_until(ws, "game.state") is not None

    # Reconnect -> server locates the active game and resends authoritative state.
    with client.websocket_connect(f"/ws?token={token}") as ws2:
        msg2 = _recv_until(ws2, "game.state")
        assert msg2 is not None and msg2["data"]["game_id"] == gid
