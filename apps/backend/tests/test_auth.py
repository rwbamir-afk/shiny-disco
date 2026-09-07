"""Auth integration tests (Section 24-26)."""
import time

from conftest import client_headers, make_init_data


def test_valid_telegram_auth_returns_tokens(client, tg_auth):
    data = tg_auth(client, telegram_id=1001, username="ali")
    assert data["user"]["telegram_id"] == 1001
    assert data["tokens"]["access_token"]
    assert data["tokens"]["refresh_token"]
    assert data["profile"]["level"] >= 1
    assert data["profile"]["games_played"] == 0


def test_invalid_init_data_rejected(client):
    resp = client.post("/api/v1/auth/telegram", json={"init_data": "id=1&hash=deadbeef"})
    assert resp.status_code == 401


def test_forged_signed_data_rejected(client):
    # A signature computed with the WRONG token must fail.
    fields = {"id": "999", "first_name": "x"}
    bad = make_init_data(fields, token="wrong-token")
    resp = client.post("/api/v1/auth/telegram", json={"init_data": bad})
    assert resp.status_code == 401


def test_refresh_rotates_token(client, tg_auth):
    data = tg_auth(client, telegram_id=1002)
    old_refresh = data["tokens"]["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["refresh_token"] != old_refresh
    # Old refresh token is now revoked.
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401


def test_profile_endpoint(client, tg_auth):
    data = tg_auth(client, telegram_id=1003)
    h = client_headers(data["tokens"]["access_token"])
    r = client.get("/api/v1/users/me", headers=h)
    assert r.status_code == 200
    assert r.json()["user"]["id"] == data["user"]["id"]
