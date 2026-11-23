"""SupabaseClient: the only place that talks to Supabase (Auth, PostgREST `files` table, Storage).

Two implementations:
- HttpSupabase  — real project over httpx. Publishable key for client-facing Auth calls, secret key
                  for server-only PostgREST/Storage/admin calls. Both go in the `apikey` header.
- FakeSupabase  — in-memory, no network (LITEDRIVE_FAKE_SUPABASE=1). Its signed URLs are relative
                  paths under /_fake_storage that the dev-only router in server/fake_storage.py serves.
"""
from __future__ import annotations

import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx
import jwt

from server.config import Settings
from server.models import AuthUser, FileRow


class SupabaseError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class SupabaseClient(Protocol):
    # --- design methods ---
    def signIn(self, email: str, password: str) -> tuple[str, AuthUser]: ...
    def verifyJwt(self, token: str) -> AuthUser: ...
    def signOut(self, token: str) -> None: ...
    def signUpload(self, path: str) -> str: ...
    def signDownload(self, path: str, download_name: str | None = None) -> str: ...
    def removeObject(self, path: str) -> None: ...
    def userNames(self, ids: set[str]) -> dict[str, str]: ...
    # --- `files` table helpers (PostgREST); every one is scoped by owner_id ---
    def listRows(self, owner_id: str) -> list[FileRow]: ...
    def getRow(self, owner_id: str, file_id: str) -> FileRow | None: ...
    def getRowByName(self, owner_id: str, name: str) -> FileRow | None: ...
    def insertRow(self, row: FileRow) -> FileRow: ...
    def updateRow(self, owner_id: str, file_id: str, changes: dict) -> FileRow | None: ...
    def deleteRow(self, owner_id: str, file_id: str) -> None: ...


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# ---------------------------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------------------------
DEMO_USERS = {
    "alice@example.com": ("alice123", "Alice"),
    "bob@example.com": ("bob123", "Bob"),
}


def make_png(width: int = 48, height: int = 48, rgb: tuple[int, int, int] = (46, 117, 182)) -> bytes:
    """Tiny valid PNG (solid colour with a diagonal stripe) — no Pillow needed."""
    import struct
    import zlib

    rows = b""
    for y in range(height):
        row = b"\x00"
        for x in range(width):
            row += bytes((255, 255, 255)) if abs(x - y) < 3 else bytes(rgb)
        rows += row

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


class FakeSupabase:
    """Thread-safe in-memory stand-in for Auth + `files` table + Storage bucket."""

    def __init__(self, seed: bool = True, ttl_seconds: int = 300):
        self._lock = threading.RLock()
        self.ttl = ttl_seconds
        self.users: dict[str, AuthUser] = {}  # email -> user
        self.passwords: dict[str, str] = {}
        self.display: dict[str, str] = {}  # user id -> display name
        self.tokens: dict[str, str] = {}  # token -> user id
        self.rows: dict[str, FileRow] = {}  # file id -> row
        self.blobs: dict[str, bytes] = {}  # storage path -> bytes
        self.signed: dict[str, tuple[str, str, float]] = {}  # token -> (mode, path, expires)
        for email, (pw, name) in DEMO_USERS.items():
            self.add_user(email, pw, name)
        if seed:
            self._seed()

    # --- setup helpers (tests/demo) ---
    def add_user(self, email: str, password: str, display: str | None = None) -> AuthUser:
        with self._lock:
            user = AuthUser(id=str(uuid.uuid4()), email=email)
            self.users[email] = user
            self.passwords[email] = password
            self.display[user.id] = display or email
            return user

    def put_file(self, owner_email: str, name: str, data: bytes, modified: datetime) -> FileRow:
        owner = self.users[owner_email]
        fid = str(uuid.uuid4())
        row = FileRow(
            id=fid, owner_id=owner.id, name=name, storage_path=f"{owner.id}/{fid}", size=len(data),
            created_at=modified - timedelta(days=1), modified_at=modified,
            uploaded_by=owner.id, last_edited_by=owner.id, committed=True,
        )
        with self._lock:
            self.rows[fid] = row
            self.blobs[row.storage_path] = data
        return row

    def _seed(self) -> None:
        base = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
        a = "alice@example.com"
        self.put_file(a, "hello.js", b"// Lite Drive demo\nfunction hello(name) {\n  return `Hello, ${name}!`;\n}\nconsole.log(hello('world'));\n", base)
        self.put_file(a, "logo.png", make_png(), base + timedelta(hours=1))
        self.put_file(a, "main.cpp", b"#include <iostream>\nint main() { std::cout << \"hi\\n\"; }\n", base + timedelta(hours=2))
        self.put_file(a, "Notes.txt", b"Plain text notes - preview unavailable for .txt\n", base + timedelta(hours=3))
        self.put_file(a, "apple.cpp", b"// apple\n", base + timedelta(hours=4))
        self.put_file(a, "Banner.PNG", make_png(64, 32, (200, 80, 60)), base + timedelta(hours=5))
        self.put_file(a, "zeta.md", b"# zeta\n", base + timedelta(hours=6))
        b = "bob@example.com"
        self.put_file(b, "bob-secret.cpp", b"// only bob may see this\n", base)
        self.put_file(b, "bob-photo.png", make_png(32, 32, (40, 160, 90)), base + timedelta(hours=1))

    # --- auth ---
    def signIn(self, email: str, password: str) -> tuple[str, AuthUser]:
        with self._lock:
            user = self.users.get(email.strip().lower())
            if not user or self.passwords.get(user.email) != password:
                raise SupabaseError(400, "Invalid login credentials")
            token = "fake-" + secrets.token_urlsafe(24)
            self.tokens[token] = user.id
            return token, user

    def verifyJwt(self, token: str) -> AuthUser:
        with self._lock:
            uid = self.tokens.get(token)
            if uid is None:
                raise SupabaseError(401, "Invalid or expired token")
            return next(u for u in self.users.values() if u.id == uid)

    def signOut(self, token: str) -> None:
        with self._lock:
            self.tokens.pop(token, None)

    # --- storage ---
    def _sign(self, mode: str, path: str) -> str:
        tok = secrets.token_urlsafe(24)
        with self._lock:
            self.signed[tok] = (mode, path, time.time() + self.ttl)
        return tok

    def signUpload(self, path: str) -> str:
        return f"/_fake_storage/upload/{self._sign('upload', path)}"

    def signDownload(self, path: str, download_name: str | None = None) -> str:
        return f"/_fake_storage/object/{self._sign('download', path)}"

    def resolve_signed(self, token: str, mode: str) -> str | None:
        with self._lock:
            entry = self.signed.get(token)
            if not entry or entry[0] != mode or entry[2] < time.time():
                return None
            return entry[1]

    def removeObject(self, path: str) -> None:
        with self._lock:
            self.blobs.pop(path, None)

    def userNames(self, ids: set[str]) -> dict[str, str]:
        with self._lock:
            return {i: self.display.get(i, i) for i in ids}

    # --- table ---
    def listRows(self, owner_id: str) -> list[FileRow]:
        with self._lock:
            return [r.model_copy() for r in self.rows.values() if r.owner_id == owner_id]

    def getRow(self, owner_id: str, file_id: str) -> FileRow | None:
        with self._lock:
            r = self.rows.get(file_id)
            return r.model_copy() if r and r.owner_id == owner_id else None

    def getRowByName(self, owner_id: str, name: str) -> FileRow | None:
        with self._lock:
            for r in self.rows.values():
                if r.owner_id == owner_id and r.name == name:
                    return r.model_copy()
            return None

    def insertRow(self, row: FileRow) -> FileRow:
        with self._lock:
            if self.getRowByName(row.owner_id, row.name):
                raise SupabaseError(409, "duplicate name")
            self.rows[row.id] = row.model_copy()
            return row

    def updateRow(self, owner_id: str, file_id: str, changes: dict) -> FileRow | None:
        with self._lock:
            r = self.rows.get(file_id)
            if not r or r.owner_id != owner_id:
                return None
            self.rows[file_id] = r.model_copy(update=changes)
            return self.rows[file_id].model_copy()

    def deleteRow(self, owner_id: str, file_id: str) -> None:
        with self._lock:
            r = self.rows.get(file_id)
            if r and r.owner_id == owner_id:
                del self.rows[file_id]


# ---------------------------------------------------------------------------------------------
# Real Supabase over httpx
# ---------------------------------------------------------------------------------------------
class HttpSupabase:
    """Real project. Verification per current Supabase docs: JWKS (asymmetric ES256/RS256 signing keys)
    at /auth/v1/.well-known/jwks.json; if the project has no asymmetric keys (legacy HS256) we ask
    Auth itself via GET /auth/v1/user instead of holding the shared JWT secret."""

    def __init__(self, s: Settings):
        if not (s.supabase_url and s.supabase_publishable_key and s.supabase_secret_key):
            raise RuntimeError(
                "Set SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY (or LITEDRIVE_FAKE_SUPABASE=1)."
            )
        self.url = s.supabase_url.rstrip("/")
        self.pub = s.supabase_publishable_key
        self.secret = s.supabase_secret_key
        self.bucket = s.supabase_bucket
        self.ttl = s.signed_url_ttl_seconds
        self.http = httpx.Client(timeout=20)
        self.issuer = f"{self.url}/auth/v1"
        self._jwks = jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=600)
        self._names: dict[str, str] = {}

    # headers
    def _pub_headers(self, bearer: str | None = None) -> dict:
        h = {"apikey": self.pub}
        if bearer:
            h["Authorization"] = f"Bearer {bearer}"
        return h

    def _secret_headers(self, **extra) -> dict:
        return {"apikey": self.secret, **extra}

    @staticmethod
    def _check(r: httpx.Response) -> httpx.Response:
        if r.status_code >= 400:
            try:
                body = r.json()
                msg = body.get("msg") or body.get("message") or body.get("error_description") or body.get("error") or r.text
            except Exception:
                msg = r.text
            raise SupabaseError(r.status_code, str(msg))
        return r

    # --- auth ---
    def signIn(self, email: str, password: str) -> tuple[str, AuthUser]:
        r = self._check(self.http.post(
            f"{self.issuer}/token", params={"grant_type": "password"},
            json={"email": email, "password": password}, headers=self._pub_headers(),
        ))
        body = r.json()
        u = body["user"]
        self._names[u["id"]] = u.get("email", u["id"])
        return body["access_token"], AuthUser(id=u["id"], email=u.get("email", ""))

    def verifyJwt(self, token: str) -> AuthUser:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as e:
            raise SupabaseError(401, f"Malformed token: {e}")
        if header.get("alg") in ("ES256", "RS256"):
            try:
                key = self._jwks.get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token, key.key, algorithms=["ES256", "RS256"], audience="authenticated", issuer=self.issuer,
                )
            except jwt.PyJWTError as e:
                raise SupabaseError(401, f"Invalid token: {e}")
            return AuthUser(id=claims["sub"], email=claims.get("email", ""))
        # Legacy HS256 project: let Auth verify it.
        r = self.http.get(f"{self.issuer}/user", headers=self._pub_headers(token))
        if r.status_code != 200:
            raise SupabaseError(401, "Invalid or expired token")
        u = r.json()
        return AuthUser(id=u["id"], email=u.get("email", ""))

    def signOut(self, token: str) -> None:
        self.http.post(f"{self.issuer}/logout", headers=self._pub_headers(token))

    # --- storage ---
    def signUpload(self, path: str) -> str:
        r = self._check(self.http.post(
            f"{self.url}/storage/v1/object/upload/sign/{self.bucket}/{path}",
            headers=self._secret_headers(**{"x-upsert": "true"}),
        ))
        return f"{self.url}/storage/v1{r.json()['url']}"

    def signDownload(self, path: str, download_name: str | None = None) -> str:
        r = self._check(self.http.post(
            f"{self.url}/storage/v1/object/sign/{self.bucket}/{path}",
            json={"expiresIn": self.ttl}, headers=self._secret_headers(),
        ))
        url = f"{self.url}/storage/v1{r.json()['signedURL']}"
        if download_name:
            from urllib.parse import quote

            url += "&download=" + quote(download_name)
        return url

    def removeObject(self, path: str) -> None:
        self._check(self.http.request(
            "DELETE", f"{self.url}/storage/v1/object/{self.bucket}", json={"prefixes": [path]},
            headers=self._secret_headers(),
        ))

    def userNames(self, ids: set[str]) -> dict[str, str]:
        out = {}
        for i in ids:
            if i not in self._names:
                r = self.http.get(f"{self.url}/auth/v1/admin/users/{i}", headers=self._secret_headers())
                self._names[i] = r.json().get("email", i) if r.status_code == 200 else i
            out[i] = self._names[i]
        return out

    # --- table (PostgREST, secret key bypasses RLS; we scope by owner_id ourselves) ---
    def _rest(self) -> str:
        return f"{self.url}/rest/v1/files"

    @staticmethod
    def _row(d: dict) -> FileRow:
        return FileRow.model_validate(d)

    def listRows(self, owner_id: str) -> list[FileRow]:
        r = self._check(self.http.get(self._rest(), params={"owner_id": f"eq.{owner_id}", "select": "*"},
                                      headers=self._secret_headers()))
        return [self._row(d) for d in r.json()]

    def getRow(self, owner_id: str, file_id: str) -> FileRow | None:
        r = self._check(self.http.get(self._rest(), params={"owner_id": f"eq.{owner_id}", "id": f"eq.{file_id}", "select": "*"},
                                      headers=self._secret_headers()))
        rows = r.json()
        return self._row(rows[0]) if rows else None

    def getRowByName(self, owner_id: str, name: str) -> FileRow | None:
        r = self._check(self.http.get(self._rest(), params={"owner_id": f"eq.{owner_id}", "name": f"eq.{name}", "select": "*"},
                                      headers=self._secret_headers()))
        rows = r.json()
        return self._row(rows[0]) if rows else None

    def insertRow(self, row: FileRow) -> FileRow:
        r = self._check(self.http.post(self._rest(), json=row.model_dump(mode="json"),
                                       headers=self._secret_headers(Prefer="return=representation")))
        return self._row(r.json()[0])

    def updateRow(self, owner_id: str, file_id: str, changes: dict) -> FileRow | None:
        payload = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in changes.items()}
        r = self._check(self.http.patch(self._rest(), params={"owner_id": f"eq.{owner_id}", "id": f"eq.{file_id}"},
                                        json=payload, headers=self._secret_headers(Prefer="return=representation")))
        rows = r.json()
        return self._row(rows[0]) if rows else None

    def deleteRow(self, owner_id: str, file_id: str) -> None:
        self._check(self.http.delete(self._rest(), params={"owner_id": f"eq.{owner_id}", "id": f"eq.{file_id}"},
                                     headers=self._secret_headers()))


def build_supabase(s: Settings) -> SupabaseClient:
    return FakeSupabase(ttl_seconds=s.signed_url_ttl_seconds) if s.litedrive_fake_supabase else HttpSupabase(s)
