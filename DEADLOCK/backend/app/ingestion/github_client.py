from __future__ import annotations

from typing import Any

import httpx

from app.config.settings import settings


class GitHubAPIError(Exception):
    """Raised when the GitHub API request fails."""

    def __init__(
        self,
        status_code: int | None,
        message: str,
        *,
        remaining: str | None = None,
        reset_at: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.remaining = remaining
        self.reset_at = reset_at

        details = message

        if remaining is not None:
            details += f" | rate-limit remaining: {remaining}"

        if reset_at is not None:
            details += f" | rate-limit reset: {reset_at}"

        super().__init__(details)


class GitHubClient:
    def __init__(self) -> None:
        self.base_url = settings.github_api_url.rstrip("/")

        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # GitHub token is optional.
        # Public repositories can be accessed without authentication.
        token = str(settings.github_token or "").strip()

        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params=params,
                )

        except httpx.TimeoutException as exc:
            raise GitHubAPIError(
                None,
                "GitHub API request timed out after 20 seconds.",
            ) from exc

        except httpx.RequestError as exc:
            raise GitHubAPIError(
                None,
                f"Unable to connect to GitHub API: {exc}",
            ) from exc

        # Read rate-limit information whenever GitHub provides it.
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_timestamp = response.headers.get("X-RateLimit-Reset")

        if response.is_success:
            try:
                return response.json()
            except ValueError as exc:
                raise GitHubAPIError(
                    response.status_code,
                    "GitHub returned an invalid JSON response.",
                    remaining=remaining,
                    reset_at=reset_timestamp,
                ) from exc

        # Try to extract GitHub's useful error message.
        github_message = ""
        try:
            error_data = response.json()

            if isinstance(error_data, dict):
                github_message = str(
                    error_data.get("message", "")
                ).strip()
        except ValueError:
            pass

        # Authentication failure.
        if response.status_code == 401:
            message = (
                "GitHub authentication failed. "
                "Check GITHUB_TOKEN in the backend .env file."
            )

            raise GitHubAPIError(
                401,
                message,
                remaining=remaining,
                reset_at=reset_timestamp,
            )

        # Rate limit / forbidden request.
        if response.status_code == 403:
            if remaining == "0":
                message = (
                    "GitHub API rate limit exceeded. "
                    "Add a valid GitHub token or wait until the rate limit resets."
                )
            else:
                message = (
                    "GitHub rejected the request with HTTP 403."
                )

            if github_message:
                message += f" GitHub message: {github_message}"

            raise GitHubAPIError(
                403,
                message,
                remaining=remaining,
                reset_at=reset_timestamp,
            )

        # Repository/resource does not exist or is inaccessible.
        if response.status_code == 404:
            message = (
                "GitHub resource not found. "
                "Check the owner/repository name and repository visibility."
            )

            if github_message:
                message += f" GitHub message: {github_message}"

            raise GitHubAPIError(
                404,
                message,
                remaining=remaining,
                reset_at=reset_timestamp,
            )

        # Other GitHub API errors.
        message = (
            f"GitHub API request failed with HTTP {response.status_code}."
        )

        if github_message:
            message += f" GitHub message: {github_message}"

        raise GitHubAPIError(
            response.status_code,
            message,
            remaining=remaining,
            reset_at=reset_timestamp,
        )

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

    async def get_pr_reviews(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> list[dict[str, Any]]:
        """
        Fetch reviews for a specific pull request.
        Returns empty list on any error to keep ingestion resilient.
        """
        try:
            return await self._get(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                {"per_page": 100},
            )
        except Exception:
            return []

    async def get_pr_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> list[dict[str, Any]]:
        """
        Fetch the list of files changed in a pull request.
        Returns empty list on any error.
        """
        try:
            return await self._get(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
                {"per_page": 100},
            )
        except Exception:
            return []

    async def get_contributors(
        self,
        owner: str,
        repo: str,
    ) -> list[dict[str, Any]]:
        """
        Fetch top contributors (up to 100) sorted by commit count.
        Returns empty list on error.
        """
        try:
            return await self._get(
                f"/repos/{owner}/{repo}/contributors",
                {"per_page": 100, "anon": "false"},
            )
        except Exception:
            return []

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "HEAD",
    ) -> str | None:
        """
        Fetch the decoded text content of a single repository file.
        Returns None when the file does not exist or any error occurs.
        GitHub returns content base64-encoded inside a JSON envelope.
        """
        import base64
        try:
            data = await self._get(
                f"/repos/{owner}/{repo}/contents/{path}",
                {"ref": ref},
            )
            if isinstance(data, dict) and data.get("encoding") == "base64":
                raw = data.get("content", "")
                # GitHub includes newlines in the base64 blob
                decoded = base64.b64decode(raw.replace("\n", "")).decode("utf-8", errors="replace")
                return decoded
            return None
        except Exception:
            return None

    async def get_repo_topics(
        self,
        owner: str,
        repo: str,
    ) -> list[str]:
        """Return the GitHub Topics for a repository (empty list on error)."""
        try:
            data = await self._get(
                f"/repos/{owner}/{repo}/topics",
            )
            return data.get("names", []) if isinstance(data, dict) else []
        except Exception:
            return []