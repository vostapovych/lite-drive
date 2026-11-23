"""Test 4: user B cannot list or fetch user A's files (plus owner-from-token checks)."""


def test_list_is_per_user(client, alice, bob):
    a = {f["name"] for f in client.get("/files", headers=alice).json()}
    b = {f["name"] for f in client.get("/files", headers=bob).json()}
    assert "hello.js" in a and "bob-secret.cpp" not in a
    assert b == {"bob-secret.cpp", "bob-photo.png"}


def test_b_cannot_fetch_delete_or_commit_a_file(client, alice, bob, sb):
    a_file = next(f for f in client.get("/files", headers=alice).json() if f["name"] == "hello.js")
    fid = a_file["id"]
    assert client.get(f"/files/{fid}/download-url", headers=bob).status_code == 404
    assert client.post(f"/files/{fid}/commit", headers=bob, json={}).status_code == 404
    assert client.delete(f"/files/{fid}", headers=bob).status_code == 404
    # still there for A, and A can fetch it
    assert client.get(f"/files/{fid}/download-url", headers=alice).status_code == 200
    assert any(f["id"] == fid for f in client.get("/files", headers=alice).json())


def test_requires_valid_token(client):
    assert client.get("/files").status_code == 401
    assert client.get("/files", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_owner_comes_from_token_not_body(client, alice, bob):
    r = client.post("/uploads", headers=bob, json={"name": "mine.txt", "size": 3, "owner_id": "alice", "ownerId": "alice"})
    assert r.status_code == 200
    fid = r.json()["fileId"]
    client.post(f"/files/{fid}/commit", headers=bob, json={})
    assert "mine.txt" in {f["name"] for f in client.get("/files", headers=bob).json()}
    assert "mine.txt" not in {f["name"] for f in client.get("/files", headers=alice).json()}


def test_upload_download_roundtrip_via_signed_urls(client, alice):
    r = client.post("/uploads", headers=alice, json={"name": "new.js", "size": 5}).json()
    assert client.put(r["uploadUrl"], content=b"hello").status_code == 200  # bytes go to storage, not the API
    assert client.post(f"/files/{r['fileId']}/commit", headers=alice, json={"size": 5}).status_code == 200
    d = client.get(f"/files/{r['fileId']}/download-url", headers=alice).json()
    assert client.get(d["url"]).content == b"hello"
    assert client.delete(f"/files/{r['fileId']}", headers=alice).status_code == 204
    assert "new.js" not in {f["name"] for f in client.get("/files", headers=alice).json()}
