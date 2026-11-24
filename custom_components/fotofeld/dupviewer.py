"""Duplicates viewer: one original and one of its duplicates at a time, for spot checks from Home Assistant."""

from __future__ import annotations

import logging
import random

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .api import FotofeldApi, FotofeldError, FotofeldNotFound

_LOGGER = logging.getLogger(__name__)

SIGNAL_DUPS = "fotofeld_dups_{}"


class DuplicateViewer:
    """Where the viewer is (which original, which duplicate), and the two pictures."""

    def __init__(self, hass: HomeAssistant, api: FotofeldApi, entry_id: str, size: int) -> None:
        self.hass, self.api, self.entry_id, self.size = hass, api, entry_id, size
        self.query = ""
        self.index = 0          # which original (of those matching the filter)
        self.dup = 0            # which of its duplicates
        self.total = 0
        self.originals: int | None = None
        self.duplicates: int | None = None
        self.group: dict | None = None
        self.original_bytes: bytes | None = None
        self.duplicate_bytes: bytes | None = None
        self.available = True
        self.error: str | None = None
        self.last_delete: str | None = None
        self._retry = None
        self.picture_error: dict[str, str | None] = {"original": None, "duplicate": None}

    @property
    def original(self) -> dict | None:
        return self.group["original"] if self.group else None

    @property
    def duplicate(self) -> dict | None:
        if not self.group or not self.group.get("dups"):
            return None
        return self.group["dups"][min(self.dup, len(self.group["dups"]) - 1)]

    def _signal(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_DUPS.format(self.entry_id))

    async def _picture(self, f: dict | None, which: str) -> bytes | None:
        self.picture_error[which] = None
        if not f:
            return None
        if not f.get("exists"):
            self.picture_error[which] = "This file is gone (deleted or moved)."
            return None
        if not f.get("picture"):
            self.picture_error[which] = "Not a picture Home Assistant can show (a video or HEIC). Open it in the Fotofeld web page."
            return None
        try:
            return await self.api.dup_image(f["path"], self.size)
        except FotofeldError as err:
            # Say why: "Windows could not read this file" usually means the disk is failing there.
            msg = str(err)
            self.picture_error[which] = msg.split(": ", 1)[1] if msg[:4] in ("500:", "404:", "415:") else msg
            _LOGGER.debug("No picture for %s: %s", f.get("path"), err)
            return None

    async def load(self) -> None:
        """Fetch the current original with its duplicates, and both pictures."""
        try:
            r = await self.api.dups(self.index, 1, self.query)
        except FotofeldNotFound:
            self.available, self.error = False, "This Fotofeld has no duplicates viewer yet: update Fotofeld on the server."
            self._signal()
            return
        except FotofeldError as err:
            # Fotofeld reads its sort logs the first time (a minute or two for a big library), or was busy: try again soon.
            msg = str(err)
            self.error = msg.split(": ", 1)[1] if msg.startswith("503: ") else msg
            self._schedule_retry()
            self._signal()
            return
        self.available, self.error = True, None
        self.total = int(r.get("total") or 0)
        self.originals, self.duplicates = r.get("originals"), r.get("duplicates")
        groups = r.get("groups") or []
        self.group = groups[0] if groups else None
        if self.group:
            self.dup = min(self.dup, max(0, len(self.group.get("dups") or []) - 1))
        self.original_bytes = await self._picture(self.original, "original")
        self.duplicate_bytes = await self._picture(self.duplicate, "duplicate")
        self._signal()

    def _schedule_retry(self) -> None:
        if self._retry is None:
            self._retry = async_call_later(self.hass, 15, self._retry_now)

    async def _retry_now(self, _now) -> None:
        self._retry = None
        await self.load()

    def shutdown(self) -> None:
        if self._retry is not None:
            self._retry()
            self._retry = None

    async def next_original(self, step: int = 1) -> None:
        if self.total:
            self.index = (self.index + step) % self.total
        self.dup = 0
        await self.load()

    async def random_original(self) -> None:
        if self.total:
            self.index = random.randrange(self.total)
        self.dup = 0
        await self.load()

    async def next_duplicate(self, step: int = 1) -> None:
        if not self.group:
            return
        n = len(self.group.get("dups") or [])
        if n:
            self.dup = (self.dup + step) % n
            self.duplicate_bytes = await self._picture(self.duplicate, "duplicate")
            self._signal()

    async def _delete(self, paths: list[str]) -> None:
        if not paths:
            return
        r = await self.api.delete_dups(paths)
        kept = [x for x in r.get("results") or [] if x.get("result") not in ("recycled", "deleted", "gone")]
        reasons = sorted({x.get("reason") or "" for x in kept})
        self.last_delete = f"{r.get('deleted', 0)} deleted" + (f", {len(kept)} kept: " + " ".join(reasons) if kept else "")
        await self.load()

    async def delete_current(self) -> None:
        """Deletes the duplicate being shown (never the original)."""
        d = self.duplicate
        await self._delete([d["path"]] if d else [])

    async def delete_group(self) -> None:
        """Deletes every duplicate of the original being shown."""
        await self._delete([d["path"] for d in (self.group or {}).get("dups") or []])

    async def set_query(self, query: str) -> None:
        self.query, self.index, self.dup = query.strip(), 0, 0
        await self.load()

    def attributes(self, which: str) -> dict:
        o, d = self.original, self.duplicate
        base = {
            "filter": self.query or None,
            "original_number": self.index + 1 if self.group else None,
            "originals_matching": self.total,
            "originals_with_duplicates": self.originals,
            "duplicates_in_logs": self.duplicates,
            "original_path": o and (o.get("rel") or o.get("path")),
            "original_size": o and o.get("size"),
        }
        if which == "duplicate":
            n = len(self.group.get("dups") or []) if self.group else 0
            base.update({
                "duplicate_number": self.dup + 1 if d else None,
                "duplicates_of_this_original": n,
                "duplicate_path": d and (d.get("rel") or d.get("path")),
                "duplicate_size": d and d.get("size"),
                "kind": d and ("left in place (only listed)" if d.get("kind") == "listed" else "copy in _Duplicates"),
                "same_size": bool(d and o and d.get("exists") and o.get("exists") and d.get("size") == o.get("size")),
                "exists": d and d.get("exists"),
                "logged": d and d.get("time"),
            })
        if self.picture_error.get(which):
            base["picture_error"] = self.picture_error[which]
        if self.error:
            base["error"] = self.error
        if self.last_delete:
            base["last_delete"] = self.last_delete
        return base
