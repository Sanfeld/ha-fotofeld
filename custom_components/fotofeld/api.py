"""Talks to the Fotofeld service on the Windows computer (its HTTP API, port 8765 by default)."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class FotofeldError(Exception):
    """Fotofeld could not be reached or answered with an error."""


class FotofeldAuthError(FotofeldError):
    """The pairing code is wrong."""


class FotofeldNotFound(FotofeldError):
    """Nothing matched (no such picture, person, or Vision is not installed)."""


class FotofeldApi:
    """A thin client for the Fotofeld service."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int, code: str) -> None:
        self._session = session
        self.host = host.strip().removeprefix("http://").rstrip("/")
        self.port = port
        self._headers = {"Authorization": f"Bearer {code.strip().upper()}"}

    @property
    def base(self) -> str:
        return f"http://{self.host}:{self.port}"

    async def _request(self, method: str, path: str, *, params: dict | None = None, raw: bool = False, timeout: int = 30) -> Any:
        try:
            async with self._session.request(
                method, self.base + path, params=params, headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 401:
                    raise FotofeldAuthError("Wrong pairing code")
                if resp.status == 404:
                    raise FotofeldNotFound(await _error_text(resp))
                if resp.status >= 400:
                    raise FotofeldError(f"{resp.status}: {await _error_text(resp)}")
                if raw:
                    return await resp.read()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise FotofeldError(f"Cannot reach Fotofeld at {self.base}: {err}") from err

    async def status(self) -> dict:
        return await self._request("GET", "/api/status")

    async def info(self) -> dict:
        return await self._request("GET", "/api/info")

    async def stats(self) -> dict:
        return await self._request("GET", "/api/stats")

    async def events(self, after: int) -> dict:
        return await self._request("GET", "/api/events", params={"after": after})

    async def people(self) -> dict:
        return await self._request("GET", "/api/people")

    async def photo(self, mode: str, name: str | None = None) -> dict:
        params = {"mode": mode}
        if name:
            params["name"] = name
        return await self._request("GET", "/api/photo", params=params)

    async def photo_file(self, photo_id: str, size: int) -> bytes:
        return await self._request("GET", "/api/photo/file", params={"id": photo_id, "size": size}, raw=True, timeout=60)

    async def action(self, name: str) -> dict:
        return await self._request("POST", f"/api/actions/{name}")


async def _error_text(resp: aiohttp.ClientResponse) -> str:
    try:
        data = await resp.json(content_type=None)
        return str(data.get("error", data))
    except Exception:  # noqa: BLE001
        return resp.reason or str(resp.status)
