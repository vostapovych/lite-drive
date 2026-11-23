"""Web pages are served by the same app and add NO API endpoints."""


def test_pages_and_static(client):
    assert "Sign in" in client.get("/login").text
    assert "files-table" in client.get("/").text
    assert client.get("/static/htmx.min.js").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_web_client_adds_no_special_api_endpoints(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert paths == {"/auth/login", "/auth/logout", "/files", "/files/{file_id}", "/files/{file_id}/commit",
                     "/files/{file_id}/download-url", "/uploads", "/healthz"}
