"""Web client in a real headless Chromium against a live (fake-backed) server. Skipped if Playwright/Chromium is absent."""
import pytest

sync_api = pytest.importorskip("playwright.sync_api")

DROP_JS = """
([sel, files]) => {
  const dt = new DataTransfer();
  for (const [name, text] of files) dt.items.add(new File([text], name, {type: 'text/plain'}));
  const el = document.querySelector(sel);
  for (const t of ['dragenter', 'dragover', 'drop'])
    el.dispatchEvent(new DragEvent(t, {dataTransfer: dt, bubbles: true, cancelable: true}));
}
"""


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Chromium not available: {e}")
        yield b
        b.close()


def login(browser, base, email="alice@example.com", password="alice123"):
    page = browser.new_page(viewport={"width": 1200, "height": 720})
    page.goto(base + "/login")
    page.fill("#email", email)
    page.fill("#password", password)
    page.click("#login-btn")
    page.wait_for_url(base + "/")
    page.wait_for_selector("#rows tr")
    return page


def names(page):
    return page.eval_on_selector_all("#rows tr td:first-child", "els => els.map(e => e.textContent)")


def test_bad_login_shows_error(browser, live_server):
    page = browser.new_page()
    page.goto(live_server + "/login")
    page.fill("#email", "alice@example.com")
    page.fill("#password", "wrong")
    page.click("#login-btn")
    page.wait_for_selector("#login-status.error")
    assert "Invalid" in page.inner_text("#login-status")
    assert page.url.endswith("/login")


def test_unauthenticated_root_redirects_to_login(browser, live_server):
    page = browser.new_page()
    page.goto(live_server + "/")
    page.wait_for_url(live_server + "/login")


def test_list_sort_filter(browser, live_server):
    page = login(browser, live_server)
    ci = sorted(names(page), key=str.casefold)
    assert names(page) == ci and len(ci) == 7 and "bob-secret.cpp" not in ci
    page.click("#sort-desc")
    assert names(page) == ci[::-1]
    page.click("#sort-asc")
    page.select_option("#filter", "cpp_png")
    assert set(names(page)) == {"apple.cpp", "Banner.PNG", "logo.png", "main.cpp"}
    page.select_option("#filter", "all")
    assert len(names(page)) == 7


def test_columns_toggle_name_locked(browser, live_server):
    page = login(browser, live_server)
    assert page.is_disabled("#columns-list input[data-col=name]")
    page.click("#columns-menu summary")
    page.uncheck("#columns-list input[data-col=createdAt]")
    page.uncheck("#columns-list input[data-col=lastEditedBy]")
    heads = page.eval_on_selector_all("#head-row th", "els => els.map(e => e.dataset.col)")
    assert heads == ["name", "modifiedAt", "uploadedBy"]


def test_preview_js_png_unavailable(browser, live_server):
    page = login(browser, live_server)
    page.click("#rows tr:has-text('hello.js')")
    page.wait_for_selector("#preview-text:not([hidden])")
    assert "function hello" in page.inner_text("#preview-text")
    page.click("#rows tr:has-text('logo.png')")
    page.wait_for_selector("#preview-image:not([hidden])")
    assert page.eval_on_selector("#preview-image", "i => i.naturalWidth") > 0
    page.click("#rows tr:has-text('main.cpp')")
    page.wait_for_function("document.getElementById('preview-message').textContent === 'Preview unavailable'")
    assert page.is_hidden("#preview-text") and page.is_hidden("#preview-image")


def test_upload_by_button_and_by_drop(browser, live_server, tmp_path):
    page = login(browser, live_server)
    f = tmp_path / "picked.js"
    f.write_text("console.log('x')")
    page.set_input_files("#file-input", str(f))
    page.wait_for_selector("#rows tr:has-text('picked.js')")
    page.evaluate(DROP_JS, ["#dropzone", [["dropped.cpp", "int a;"], ["dropped2.js", "//"]]])
    page.wait_for_selector("#rows tr:has-text('dropped.cpp')")
    page.wait_for_selector("#rows tr:has-text('dropped2.js')")
    page.click("#rows tr:has-text('dropped2.js')")
    page.wait_for_selector("#preview-text:not([hidden])")
    assert page.inner_text("#preview-text") == "//"


def test_download(browser, live_server):
    page = login(browser, live_server)
    page.click("#rows tr:has-text('hello.js')")
    with page.expect_download() as d:
        page.click("#btn-download")
    assert d.value.suggested_filename == "hello.js"


def test_delete_needs_confirmation(browser, live_server):
    page = login(browser, live_server)
    page.click("#rows tr:has-text('zeta.md')")
    page.click("#btn-delete")
    page.wait_for_selector("#confirm-dialog[open]")
    assert "zeta.md" in page.inner_text("#confirm-text")
    page.click("#confirm-cancel")
    assert "zeta.md" in names(page)
    page.click("#btn-delete")
    page.click("#confirm-ok")
    page.wait_for_function("![...document.querySelectorAll('#rows tr td:first-child')].some(e => e.textContent === 'zeta.md')")


def test_other_user_sees_only_own_files(browser, live_server):
    page = login(browser, live_server, "bob@example.com", "bob123")
    assert set(names(page)) == {"bob-secret.cpp", "bob-photo.png"}
