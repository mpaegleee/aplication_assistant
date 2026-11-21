"""Application-owned Chromium. Credentials stay in the portal, state in encrypted Store."""

import asyncio
import concurrent.futures
import sqlite3
import threading
from contextlib import suppress
from urllib.parse import urlsplit

from playwright.async_api import Error as BrowserError

from .store import now

PORTALS = {
    "linkedin": ("https://www.linkedin.com/login", ("linkedin.com",)),
    "gupy": ("https://login.gupy.io/candidate/signin", ("gupy.io",)),
    "indeed": ("https://br.indeed.com/", ("indeed.com", "indeed.com.br")),
    "inhire": ("", ("inhire.app",)),
}
AUTH_DOMAINS = ("accounts.google.com", "login.microsoftonline.com")


def allowed_url(url, platform):
    if platform not in PORTALS:
        return False
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    return (
        p.scheme == "https"
        and not p.username
        and not p.password
        and p.port in (None, 443)
        and any(
            host == d or host.endswith("." + d)
            for d in PORTALS[platform][1] + AUTH_DOMAINS
        )
    )


class BrowserManager:
    def __init__(self, store):
        self.store = store
        self.loop = None
        self.thread = None
        self.contexts = {}
        self.pages = {}
        self.leases = {}
        self.busy = set()
        self.start_lock = threading.Lock()
        self.context_lock = asyncio.Lock()
        self.driver = None
        self.browser = None

    def schedule(self, coroutine):
        with self.start_lock:
            if self.loop is None:
                self.loop = asyncio.new_event_loop()
                self.thread = threading.Thread(
                    target=self.loop.run_forever, daemon=True
                )
                self.thread.start()
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def call(self, coroutine, timeout=120):
        future = self.schedule(coroutine)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise ValueError(
                "O navegador excedeu o tempo limite. Confira o portal antes de repetir."
            ) from None

    async def context(self, platform):
        async with self.context_lock:
            return await self._context(platform)

    async def _context(self, platform):
        if platform not in PORTALS:
            raise ValueError("Portal não suportado.")
        if platform in self.contexts:
            return self.contexts[platform]
        if not self.browser:
            import os
            from pathlib import Path

            bundled = Path(__file__).resolve().parents[2] / "browsers"
            if bundled.is_dir():
                os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled))
            from playwright.async_api import async_playwright

            self.driver = await async_playwright().start()
            try:
                self.browser = await self.driver.chromium.launch(
                    headless=True, channel="chromium", chromium_sandbox=True
                )
            except BrowserError:
                await self.driver.stop()
                self.driver = None
                raise ValueError(
                    "Não foi possível iniciar o Chromium. Instale o navegador da aplicação conforme a ajuda; no Linux, confira as dependências e o sandbox."
                ) from None
        saved = self.store.get("browser_sessions", platform, {})
        context = await self.browser.new_context(
            storage_state=saved.get("state"),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            viewport={"width": 1280, "height": 800},
            accept_downloads=False,
            service_workers="block",
            permissions=[],
        )

        async def route(request_route):
            request = request_route.request
            # Remote pages cannot reach this installation or private network resources.
            parsed = urlsplit(request.url)
            host = (parsed.hostname or "").lower()
            import ipaddress

            private = host in (
                "localhost",
                "metadata.google.internal",
            ) or host.endswith((".localhost", ".local", ".internal"))
            try:
                private = private or not ipaddress.ip_address(host).is_global
            except ValueError:
                pass
            if host and not private:
                import socket

                try:
                    addresses = await asyncio.get_running_loop().getaddrinfo(
                        host, parsed.port or 443, type=socket.SOCK_STREAM
                    )
                    private = not addresses or any(
                        not ipaddress.ip_address(a[4][0]).is_global for a in addresses
                    )
                except OSError:
                    private = True
            if (
                private
                or parsed.scheme not in ("https", "data", "blob")
                or (
                    request.is_navigation_request()
                    and request.frame == request.frame.page.main_frame
                    and not allowed_url(request.url, platform)
                )
            ):
                await request_route.abort()
            else:
                await request_route.continue_()

        await context.route("**/*", route)
        await context.route_web_socket("**/*", lambda ws: ws.close())
        context.set_default_timeout(8000)

        async def new_page(page):
            self.pages[platform] = page
            page.on("dialog", lambda dialog: dialog.dismiss())

        context.on("page", new_page)
        self.contexts[platform] = context
        return context

    async def open(self, platform, url=""):
        if platform in self.busy or platform in self.leases:
            raise ValueError(
                "Portal em uso. Libere o controle antes de abrir outra página."
            )
        target = url or PORTALS.get(platform, ("", ()))[0]
        if not target or not allowed_url(target, platform):
            raise ValueError("Informe um endereço HTTPS do portal selecionado.")
        self.busy.add(platform)
        try:
            context = await self.context(platform)
            page = self.pages.get(platform)
            if not page or page.is_closed():
                page = await context.new_page()
                self.pages[platform] = page
            await page.goto(target, wait_until="domcontentloaded", timeout=45000)
            return {"ok": True}
        finally:
            self.busy.discard(platform)

    async def save(self, platform):
        if platform in self.contexts:
            state = await self.contexts[platform].storage_state(indexed_db=True)
            # Discard identity-provider cookies; keep only this portal's session.
            domains = PORTALS[platform][1]
            state["cookies"] = [
                c
                for c in state["cookies"]
                if any(
                    c["domain"].lstrip(".") == d
                    or c["domain"].lstrip(".").endswith("." + d)
                    for d in domains
                )
            ]
            state["origins"] = [
                o
                for o in state["origins"]
                if any(
                    (urlsplit(o["origin"]).hostname or "") == d
                    or (urlsplit(o["origin"]).hostname or "").endswith("." + d)
                    for d in domains
                )
            ]
            self.store.put(
                "browser_sessions", {"state": state, "saved_at": now()}, platform
            )

    async def forget(self, platform):
        if platform in self.busy or platform in self.leases:
            raise ValueError("Libere o controle do portal antes de apagar a sessão.")
        context = self.contexts.pop(platform, None)
        if context:
            await context.close()
        self.pages.pop(platform, None)
        with self.store.connection() as c:
            c.execute(
                "DELETE FROM objects WHERE kind=? AND id=?",
                ("browser_sessions", platform),
            )
        return {"ok": True}

    async def status(self):
        return [
            {
                "id": p,
                "open": p in self.pages and not self.pages[p].is_closed(),
                "saved_at": self.store.get("browser_sessions", p, {}).get("saved_at"),
                "busy": p in self.busy,
                "controlled": p in self.leases,
            }
            for p in PORTALS
        ]

    async def acquire(self, platform, owner):
        if platform in self.busy or platform in self.leases:
            raise ValueError("O portal já está em uso em outra tela ou pela rotina.")
        if platform not in self.pages or self.pages[platform].is_closed():
            raise ValueError("Abra o portal antes de assumir o controle.")
        self.leases[platform] = owner

    async def release(self, platform, owner):
        if self.leases.get(platform) == owner:
            try:
                await self.save(platform)
            finally:
                self.leases.pop(platform, None)

    async def frame(self, platform):
        page = self.pages.get(platform)
        if not page or page.is_closed():
            raise ValueError("Abra o portal para visualizar o navegador.")
        return await page.screenshot(type="jpeg", quality=65, timeout=5000)

    async def control(self, platform, owner, message):
        if self.leases.get(platform) != owner:
            raise ValueError("Assuma o controle para interagir.")
        page = self.pages[platform]
        action = message.get("type")
        if action == "click":
            x, y = float(message["x"]), float(message["y"])
            if not (0 <= x <= 1280 and 0 <= y <= 800):
                raise ValueError("Coordenadas inválidas.")
            await page.mouse.click(x, y)
        elif action == "text":
            await page.keyboard.insert_text(str(message.get("text", ""))[:2000])
        elif action == "key":
            key = message.get("key")
            if key not in (
                "Tab",
                "Shift+Tab",
                "Enter",
                "Backspace",
                "Delete",
                "Escape",
                "ArrowDown",
                "ArrowUp",
                "ArrowLeft",
                "ArrowRight",
                "ControlOrMeta+A",
                "Space",
            ):
                raise ValueError("Tecla não permitida.")
            await page.keyboard.press(key)
        elif action == "scroll":
            await page.mouse.wheel(
                0, max(-1600, min(1600, int(message.get("delta", 0))))
            )
        else:
            raise ValueError("Comando inválido.")

    async def inhire(self, url, profile, pdf, submit=False, before_submit=None):
        from .portal_forms import fill_inhire

        platform = "inhire"
        if platform in self.leases or platform in self.busy:
            raise ValueError(
                "Libere o navegador InHire antes de executar a candidatura."
            )
        self.busy.add(platform)
        try:
            context = await self.context(platform)
            for old_page in list(context.pages):
                await old_page.close()
            page = await context.new_page()
            self.pages[platform] = page
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            result = await fill_inhire(page, profile, pdf, submit, before_submit)
            await self.save(platform)
            return result
        finally:
            self.busy.discard(platform)

    async def shutdown(self):
        for p in list(self.contexts):
            with suppress(BrowserError, OSError, sqlite3.Error):
                await self.save(p)
        if self.browser:
            await self.browser.close()
        if self.driver:
            await self.driver.stop()

    def close(self):
        if self.loop:
            try:
                self.call(self.shutdown(), timeout=15)
            finally:
                self.loop.call_soon_threadsafe(self.loop.stop)
                self.thread.join(timeout=5)
