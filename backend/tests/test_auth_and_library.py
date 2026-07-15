from app.ingest.youtube import expand_youtube_urls
from app.security import hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_register_login_and_search(client):
    reg = client.post("/api/auth/register", json={"email": "a@example.com", "password": "secret123"})
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    text = client.post(
        "/api/sources/text",
        headers=headers,
        json={"title": "Protein guide", "text": "Eat more protein every day for recovery.", "auto_summarize": False},
    )
    assert text.status_code == 200, text.text
    source_id = text.json()["id"]

    col = client.post("/api/library/collections", headers=headers, json={"name": "Health"})
    assert col.status_code == 200
    cid = col.json()["id"]
    added = client.post(f"/api/library/collections/{cid}/sources/{source_id}", headers=headers)
    assert added.status_code == 200
    assert source_id in added.json()["source_ids"]

    tag = client.post(f"/api/library/sources/{source_id}/tags", headers=headers, json={"name": "Diet"})
    assert tag.status_code == 200
    assert any(t["name"] == "diet" for t in tag.json())

    note = client.post(
        f"/api/library/sources/{source_id}/notes",
        headers=headers,
        json={"body": "Remember protein timing"},
    )
    assert note.status_code == 200

    search = client.get("/api/library/search", headers=headers, params={"q": "protein"})
    assert search.status_code == 200, search.text
    assert search.json()["hits"]


def test_expand_youtube_urls_passthrough():
    urls = expand_youtube_urls(["https://www.youtube.com/watch?v=abcdefghijk"])
    assert urls == ["https://www.youtube.com/watch?v=abcdefghijk"]
