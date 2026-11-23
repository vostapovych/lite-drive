// Login page: POST /auth/login (the same REST endpoint the desktop client uses), keep the token for this tab only.
(() => {
  const form = document.getElementById("login-form");
  const status = document.getElementById("login-status");
  const btn = document.getElementById("login-btn");
  try { if (sessionStorage.getItem("litedrive.token")) { location.replace("/"); return; } } catch (_) {}

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    btn.disabled = true;
    status.className = "status";
    status.textContent = "Signing in… (a free server can take up to a minute to wake up)";
    try {
      const r = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.email.value.trim(), password: form.password.value }),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.detail || `Login failed (${r.status})`);
      sessionStorage.setItem("litedrive.token", body.accessToken);
      sessionStorage.setItem("litedrive.email", body.email || form.email.value.trim());
      location.replace("/");
    } catch (e) {
      status.className = "status error";
      status.textContent = e.message;
      btn.disabled = false;
    }
  });
})();
