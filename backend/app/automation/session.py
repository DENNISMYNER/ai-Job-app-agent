"""Browser session manager.

Playwright's sync API objects are bound to the thread that created them, and FastAPI runs
requests on a pool. All browser work is therefore funnelled through ONE dedicated worker
thread. Pages stay open between steps (fill -> user review -> submit), and in headed mode
the user can click into the window and take over at any time.
"""
from __future__ import annotations

import logging
import queue
import threading
from concurrent.futures import Future
from typing import Any, Callable

from app.core.config import get_settings

log = logging.getLogger(__name__)


class BrowserWorker:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._pw = None
        self._ctx = None
        self.pages: dict[int, Any] = {}
        self.headless: bool | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------ thread loop
    def _loop(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                break
            fn, fut = item
            try:
                fut.set_result(fn(self))
            except BaseException as exc:  # noqa: BLE001 - propagate to caller
                fut.set_exception(exc)
        self._close()

    def _ensure_thread(self) -> None:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, name="browser-worker", daemon=True)
                self._thread.start()

    def call(self, fn: Callable[["BrowserWorker"], Any], timeout: float = 180) -> Any:
        self._ensure_thread()
        fut: Future = Future()
        self._q.put((fn, fut))
        return fut.result(timeout=timeout)

    # ------------------------------------------------- runs on worker thread
    def context(self, headless: bool | None = None):
        s = get_settings()
        want = s.browser_headless if headless is None else headless
        if self._ctx is not None and self.headless != want:
            self._close_context()
        if self._ctx is None:
            from playwright.sync_api import sync_playwright

            self._pw = self._pw or sync_playwright().start()
            s.profile_dir.mkdir(parents=True, exist_ok=True)
            # Persistent profile: sign-ins survive between runs and are controlled by the user.
            self._ctx = self._pw.chromium.launch_persistent_context(
                str(s.profile_dir),
                channel=s.browser_channel or None,
                headless=want,
                viewport={"width": 1280, "height": 900},
                args=[],
            )
            self.headless = want
        return self._ctx

    def new_page(self, key: int, headless: bool | None = None):
        old = self.pages.pop(key, None)
        if old is not None:
            try:
                old.close()
            except Exception:  # noqa: BLE001
                pass
        page = self.context(headless).new_page()
        page.set_default_timeout(15000)
        self.pages[key] = page
        return page

    def page(self, key: int):
        page = self.pages.get(key)
        if page is None or page.is_closed():
            return None
        return page

    def close_page(self, key: int) -> None:
        page = self.pages.pop(key, None)
        if page is not None:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass

    def _close_context(self) -> None:
        try:
            if self._ctx:
                self._ctx.close()
        except Exception:  # noqa: BLE001
            pass
        self._ctx = None
        self.pages.clear()

    def _close(self) -> None:
        self._close_context()
        try:
            if self._pw:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._pw = None


_worker: BrowserWorker | None = None


def get_worker() -> BrowserWorker:
    global _worker
    if _worker is None:
        _worker = BrowserWorker()
    return _worker


def shutdown_browser() -> None:
    global _worker
    if _worker is not None and _worker._thread is not None and _worker._thread.is_alive():
        _worker._q.put(None)
        _worker._thread.join(timeout=10)
    _worker = None


def check_browser_setup() -> dict:
    """Used by /api/automation/status and the installer to verify the browser is usable."""
    try:
        def probe(w: BrowserWorker):
            from playwright.sync_api import sync_playwright

            s = get_settings()

            with sync_playwright() as pw:
                b = pw.chromium.launch(
                    headless=True,
                    channel=s.browser_channel or None,
                )
                v = b.version
                b.close()
                return v

        return {"ok": True, "chromium": get_worker().call(probe, timeout=60)}

    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc)[:300],
            "hint": "Check that the configured browser is installed and accessible.",
        }