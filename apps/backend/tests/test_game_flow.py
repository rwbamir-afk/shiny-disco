"""End-to-end game flow integration test (Section 70).

Auth -> Quick Match -> real-time view -> server-authoritative actions ->
result -> rating/XP. Driven entirely through the public API.
"""
import time

from conftest import client_headers

TRUMP = "hearts"


def _make_players(client, tg_auth, start_id=4001, count=4):
    players = []
    for i in range(count):
        tg_id = start_id + i
        data = tg_auth(client, telegram_id=tg_id, username=f"player{i}")
        players.append(
            {
                "user_id": data["user"]["id"],
                "token": data["tokens"]["access_token"],
            }
        )
    return players


def _match(client, players):
    for p in players:
        r = client.post("/api/v1/matchmaking/quick", json={"mode": "quick"}, headers=client_headers(p["token"]))
        assert r.status_code == 200, r.text
    game_id = None
    for _ in range(40):
        time.sleep(0.3)
        st = client.get("/api/v1/matchmaking/status", headers=client_headers(players[0]["token"])).json()
        if st.get("status") == "matched":
            game_id = st["game_id"]
            break
    assert game_id is not None, "matchmaking did not produce a game"
    return game_id


def _drive_game(client, players, game_id):
    acted_ids = {}
    for _ in range(150):
        made_move = False
        for p in players:
            headers = client_headers(p["token"])
            r = client.get(f"/api/v1/games/{game_id}/view", headers=headers)
            assert r.status_code == 200
            view = r.json()["view"]
            if view["phase"] == "game_ended":
                return view
            if view["phase"] == "trump_selection" and view["seat"] == view["hakem_seat"]:
                rid = f"{p['user_id']}:t"
                client.post(
                    f"/api/v1/games/{game_id}/action",
                    json={"type": "select_trump", "trump": TRUMP, "request_id": rid},
                    headers=headers,
                )
                made_move = True
                break
            if view["is_my_turn"]:
                card = view["legal_cards"][0]
                rid = f"{p['user_id']}:{len(view['hand'])}"
                client.post(
                    f"/api/v1/games/{game_id}/action",
                    json={"type": "play_card", "card": card, "request_id": rid},
                    headers=headers,
                )
                made_move = True
                break
        if not made_move:
            break
    return None


def test_full_game_via_api(client, tg_auth):
    players = _make_players(client, tg_auth)
    game_id = _match(client, players)
    final_view = _drive_game(client, players, game_id)
    assert final_view is not None, "game did not finish"
    assert final_view["scores"]["A"] + final_view["scores"]["B"] == 13

    # Result endpoint is authoritative.
    r = client.get(f"/api/v1/games/{game_id}/result", headers=client_headers(players[0]["token"]))
    assert r.status_code == 200
    result = r.json()
    assert result["winner_team"] in ("A", "B")
    assert result["scores"]["A"] + result["scores"]["B"] == 13

    # Winning/losing teams got their stats updated exactly once.
    for p in players:
        me = client.get("/api/v1/users/me", headers=client_headers(p["token"])).json()
        assert me["profile"]["games_played"] == 1
        assert me["profile"]["wins"] + me["profile"]["losses"] == 1


def test_action_idempotency(client, tg_auth):
    players = _make_players(client, tg_auth, start_id=5001)
    game_id = _match(client, players)
    # Make the first action (trump selection) twice with the same request_id.
    headers = client_headers(players[0]["token"])
    view = client.get(f"/api/v1/games/{game_id}/view", headers=headers).json()["view"]
    hakem = next(p for p in players if view["hakem_seat"] is not None)
    # Find the hakem's token.
    hakem_view = None
    for p in players:
        v = client.get(f"/api/v1/games/{game_id}/view", headers=client_headers(p["token"])).json()["view"]
        if v["seat"] == v["hakem_seat"]:
            hakem_view = v
            hakem_token = p["token"]
            break
    rid = "idem-trump-1"
    body = {"type": "select_trump", "trump": TRUMP, "request_id": rid}
    r1 = client.post(f"/api/v1/games/{game_id}/action", json=body, headers=client_headers(hakem_token))
    assert r1.status_code == 200
    # Duplicate delivery -> still OK, no error, and state unchanged.
    before = client.get(f"/api/v1/games/{game_id}/view", headers=client_headers(hakem_token)).json()["view"]
    r2 = client.post(f"/api/v1/games/{game_id}/action", json=body, headers=client_headers(hakem_token))
    assert r2.status_code == 200
    after = client.get(f"/api/v1/games/{game_id}/view", headers=client_headers(hakem_token)).json()["view"]
    assert before["phase"] == after["phase"] == "playing"
    assert before["trump"] == after["trump"] == TRUMP
