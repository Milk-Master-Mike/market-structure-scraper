from __future__ import annotations

import asyncio
import time

import httpx

from .cache import TextFileCache
from .config import Settings


class SourceError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class SourceClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache = TextFileCache(settings.cache_dir, settings.cache_ttl_seconds)
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._rate_lock = asyncio.Lock()
        self._last_request = 0.0

    async def _throttle(self) -> None:
        async with self._rate_lock:
            delay = 1 / self.settings.requests_per_second - (
                time.monotonic() - self._last_request
            )
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request = time.monotonic()

    async def get_text(self, url: str) -> str:
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        user_agent = self.settings.validated_user_agent()
        async with self._semaphore:
            await self._throttle()
            try:
                async with httpx.AsyncClient(
                    headers={"User-Agent": user_agent, "Accept": "text/plain"},
                    timeout=self.settings.timeout_seconds,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    payload = response.text
            except httpx.TimeoutException as exc:
                raise SourceError("timeout", "Source request timed out", True) from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                raise SourceError(
                    f"http_{status}",
                    f"Source returned HTTP {status}",
                    status in {429, 500, 502, 503, 504},
                ) from exc
            except httpx.HTTPError as exc:
                raise SourceError("source_unavailable", "Source request failed", True) from exc
        if len(payload) > 25_000_000:
            raise SourceError("response_too_large", "Source response exceeded 25 MB")
        self.cache.put(url, payload)
        return payload

