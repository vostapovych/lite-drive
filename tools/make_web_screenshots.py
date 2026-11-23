"""Browser screenshots: headless Chromium (Playwright) against the real app on FakeSupabase with seeded demo data.

    .venv/Scripts/python tools/make_web_screenshots.py [--out screenshots/web]

Folder sync does not exist in the browser (it cannot read a local folder), so there is no sync shot."""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.demo_server import start_demo_server  # noqa: E402  (sets LITEDRIVE_FAKE_SUPABASE=1)

from playwright.sync_api import sync_playwright  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="screenshots/web")
args = ap.parse_args()
out = Path(args.out)
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True, exist_ok=True)

DROP_JS = """
([sel, files, types]) => {
  const dt = new DataTransfer();
  for (const [name, text] of files) dt.items.add(new File([text], name, {type: 'text/plain'}));
  const el = document.querySelector(sel);
  for (const t of types) el.dispatchEvent(new DragEvent(t, {dataTransfer: dt, bubbles: true, cancelable: true}));
}
"""
n = 0
index: list[str] = []


def shot(page, name: str, caption: str) -> None:
    global n
    n += 1
    page.wait_for_timeout(150)
    fname = f"{n:02d}-{name}.png"
    page.screenshot(path=str(out / fname))
    index.append(f"- `{fname}` — {caption}")
    print("saved", fname)


url, sb, stop = start_demo_server()
tmp = Path(tempfile.mkdtemp(prefix="litedrive-webshots-"))
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1200, "height": 720}, color_scheme="light", accept_downloads=True)
    page = ctx.new_page()

    page.goto(url + "/login")
    page.fill("#email", "alice@example.com")
    shot(page, "login", "Login page")
    page.fill("#password", "wrong-password")
    page.click("#login-btn")
    page.wait_for_selector("#login-status.error")
    shot(page, "login-error", "Login rejected by the server")
    page.fill("#password", "alice123")
    page.click("#login-btn")
    page.wait_for_url(url + "/")
    page.wait_for_selector("#rows tr")
    shot(page, "file-list", "File list (only Alice's files; Bob's are never returned)")

    page.click("#sort-asc")
    shot(page, "sort-az", "Sorted by name A→Z (case-insensitive)")
    page.click("#sort-desc")
    shot(page, "sort-za", "Sorted by name Z→A (case-insensitive)")
    page.click("#sort-asc")

    page.select_option("#filter", "cpp_png")
    shot(page, "filter-cpp-png", "Filter: only .cpp and .png")
    page.select_option("#filter", "all")
    shot(page, "filter-all", "Filter: all files")

    page.click("#rows tr:has-text('hello.js')")
    page.wait_for_selector("#preview-text:not([hidden])")
    shot(page, "preview-js", "Preview: .js shown as plain text")
    page.click("#rows tr:has-text('logo.png')")
    page.wait_for_selector("#preview-image:not([hidden])")
    shot(page, "preview-png", "Preview: .png shown as an image")
    page.click("#rows tr:has-text('main.cpp')")
    page.wait_for_function("document.getElementById('preview-message').textContent === 'Preview unavailable'")
    shot(page, "preview-unavailable", "Preview: any other type shows “Preview unavailable”")

    page.click("#columns-menu summary")
    shot(page, "columns-menu", "Columns menu (Name is locked on)")
    page.uncheck("#columns-list input[data-col=createdAt]")
    page.uncheck("#columns-list input[data-col=lastEditedBy]")
    page.click("#columns-menu summary")
    shot(page, "columns-hidden", "“Created” and “Last edited by” hidden")
    page.click("#columns-menu summary")
    page.check("#columns-list input[data-col=createdAt]")
    page.check("#columns-list input[data-col=lastEditedBy]")
    page.click("#columns-menu summary")

    f = tmp / "report.js"
    f.write_text("// uploaded with the Upload button\nexport const answer = 42;\n")
    page.set_input_files("#file-input", str(f))
    page.wait_for_selector("#rows tr:has-text('report.js')")
    page.click("#rows tr:has-text('report.js')")
    page.wait_for_selector("#preview-text:not([hidden])")
    shot(page, "upload", "After Upload…: report.js is listed and previewable")

    drop = [["dropped.cpp", "int dropped() { return 1; }\n"], ["dropped.js", "console.log('dropped');\n"]]
    page.evaluate(DROP_JS, ["#dropzone", drop, ["dragenter", "dragover"]])
    shot(page, "drag-over", "Dragging files over the table shows the drop target")
    page.evaluate(DROP_JS, ["#dropzone", drop, ["drop"]])
    page.wait_for_selector("#rows tr:has-text('dropped.cpp')")
    page.wait_for_selector("#rows tr:has-text('dropped.js')")
    shot(page, "drag-and-drop-upload", "Two files dropped onto the table were uploaded")

    page.click("#rows tr:has-text('hello.js')")
    with page.expect_download() as d:
        page.click("#btn-download")
    page.wait_for_function("document.getElementById('status').textContent.includes('Downloading')")
    shot(page, "download", f"Download started: browser saved {d.value.suggested_filename}")

    page.click("#rows tr:has-text('zeta.md')")
    page.click("#btn-delete")
    page.wait_for_selector("#confirm-dialog[open]")
    shot(page, "delete-confirmation", "Delete asks for confirmation")
    page.click("#confirm-ok")
    page.wait_for_function("![...document.querySelectorAll('#rows tr td:first-child')].some(e => e.textContent === 'zeta.md')")
    shot(page, "delete-done", "After confirming: zeta.md is gone")
    browser.close()

(out / "README.md").write_text("# Web screenshots (generated by tools/make_web_screenshots.py)\n\n" + "\n".join(index) + "\n",
                               encoding="utf-8")
stop()
shutil.rmtree(tmp, ignore_errors=True)
print(f"done: {n} screenshots in {out}")
