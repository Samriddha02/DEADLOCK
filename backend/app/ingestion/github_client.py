from typing import Any

import httpx

from app.config.settings import settings


class GitHubClient:
    def __init__(self) -> None:
        self.base_url = settings.github_api_url.rstrip("/")

        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # Token is optional for public repositories.
        if settings.github_token:
            self.headers["Authorization"] = (
                f"Bearer {settings.github_token}"
            )

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:

        async with httpx.AsyncClient(timeout=20) as client:

            response = await client.get(
                f"{self.base_url}{path}",
                headers=self.headers,
                params=params,
            )

            response.raise_for_status()

            return response.json()

    async def get_repository(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any]:

        return await self._get(
            f"/repos/{owner}/{repo}"
        )

    async def get_issues(
        self,
        owner: str,
        repo: str,
    ) -> list[dict[str, Any]]:

        return await self._get(
            f"/repos/{owner}/{repo}/issues",
            {
                "state": "all",
                "per_page": 100,
            },
        )

    async def get_pull_requests(
        self,
        owner: str,
        repo: str,
    ) -> list[dict[str, Any]]:

        return await self._get(
            f"/repos/{owner}/{repo}/pulls",
            {
                "state": "all",
                "per_page": 100,
            },
        )

    async def get_commits(
        self,
        owner: str,
        repo: str,
    ) -> list[dict[str, Any]]:

        return await self._get(
            f"/repos/{owner}/{repo}/commits",
            {
                "per_page": 100,
            },
        )

    async def get_milestones(
        self,
        owner: str,
        repo: str,
    ) -> list[dict[str, Any]]:

        return await self._get(
            f"/repos/{owner}/{repo}/milestones",
            {
                "state": "all",
                "per_page": 100,
            },
        )