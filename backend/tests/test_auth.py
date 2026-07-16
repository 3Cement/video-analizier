def test_api_keys_and_bearer_headers_cannot_impersonate(client):
    client.cookies.clear()
    assert client.get("/api/sources", headers={"X-API-Key": "secret-key"}).status_code == 401
    assert client.get("/api/sources", headers={"Authorization": "Bearer fixture-session"}).status_code == 401
    assert client.get("/api/sources", headers={"X-User-ID": "anonymous"}).status_code == 401
