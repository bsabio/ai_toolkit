"""Infrastructure: Web search provider implementations (Brave, Google, SerpAPI)."""

from __future__ import annotations

import httpx

from research_toolkit.application.ports import SearchProvider
from research_toolkit.domain.entities import SearchResult


class BraveSearchProvider(SearchProvider):
    """Web search via Brave Search API."""

    API_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(
        self, query: str, *, max_results: int = 10, recency_days: int | None = None
    ) -> list[SearchResult]:
        params: dict[str, str | int] = {"q": query, "count": min(max_results, 20)}
        if recency_days is not None:
            # Brave uses freshness param: pd (past day), pw (past week), pm (past month), py (past year)
            if recency_days <= 1:
                params["freshness"] = "pd"
            elif recency_days <= 7:
                params["freshness"] = "pw"
            elif recency_days <= 30:
                params["freshness"] = "pm"
            else:
                params["freshness"] = "py"

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._api_key,
        }

        resp = httpx.get(self.API_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results: list[SearchResult] = []
        for i, item in enumerate(data.get("web", {}).get("results", [])):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    position=i + 1,
                )
            )
        return results[:max_results]


class GoogleSearchProvider(SearchProvider):
    """Web search via Google Custom Search JSON API."""

    API_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cx: str) -> None:
        self._api_key = api_key
        self._cx = cx

    def search(
        self, query: str, *, max_results: int = 10, recency_days: int | None = None
    ) -> list[SearchResult]:
        params: dict[str, str | int] = {
            "key": self._api_key,
            "cx": self._cx,
            "q": query,
            "num": min(max_results, 10),
        }
        if recency_days is not None:
            params["dateRestrict"] = f"d{recency_days}"

        resp = httpx.get(self.API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results: list[SearchResult] = []
        for i, item in enumerate(data.get("items", [])):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    position=i + 1,
                )
            )
        return results[:max_results]


class SerpAPISearchProvider(SearchProvider):
    """Web search via SerpAPI."""

    API_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(
        self, query: str, *, max_results: int = 10, recency_days: int | None = None
    ) -> list[SearchResult]:
        params: dict[str, str | int] = {
            "api_key": self._api_key,
            "q": query,
            "num": min(max_results, 10),
            "engine": "google",
        }
        if recency_days is not None:
            params["tbs"] = f"qdr:d{recency_days}"

        resp = httpx.get(self.API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results: list[SearchResult] = []
        for i, item in enumerate(data.get("organic_results", [])):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    position=i + 1,
                )
            )
        return results[:max_results]
