from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import requests


ADMIE_BASE_URL = "https://www.admie.gr"
FILETYPES_ENDPOINT_EN = f"{ADMIE_BASE_URL}/getFiletypeInfoEN"
FILE_SEARCH_ENDPOINT = f"{ADMIE_BASE_URL}/getOperationMarketFile"
FILE_RANGE_SEARCH_ENDPOINT = f"{ADMIE_BASE_URL}/getOperationMarketFilewRange"


@dataclass(frozen=True)
class DownloadResult:
    record: dict[str, Any]
    local_path: Path | None
    status: str
    error: str | None = None


class IPTOClient:
    def __init__(
        self,
        *,
        timeout: int = 45,
        retries: int = 3,
        backoff_seconds: float = 1.5,
        logger: logging.Logger | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "energy-investment-platform-ipto-loader/1.0",
                "Accept": "application/json,text/plain,*/*",
            }
        )

    def fetch_filetypes(self, language: str = "EN") -> Any:
        if language.upper() != "EN":
            raise ValueError("Only ADMIE English filetype metadata is currently supported")
        self.logger.info("Fetching ADMIE filetype metadata: %s", FILETYPES_ENDPOINT_EN)
        response = self._get(FILETYPES_ENDPOINT_EN)
        return self._decode_json_response(response)

    def find_files(
        self,
        date_start: str,
        date_end: str,
        file_category: str = "RealTimeSCADASystemLoad",
        use_range: bool = True,
    ) -> Any:
        endpoint = FILE_RANGE_SEARCH_ENDPOINT if use_range else FILE_SEARCH_ENDPOINT
        params = {
            "dateStart": date_start,
            "dateEnd": date_end,
            "FileCategory": file_category,
        }
        self.logger.info("Searching ADMIE files: %s params=%s", endpoint, params)
        response = self._get(endpoint, params=params)
        return self._decode_json_response(response)

    def download_files(
        self,
        file_records: list[dict[str, Any]],
        output_dir: Path,
        *,
        force: bool = False,
    ) -> list[DownloadResult]:
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[DownloadResult] = []
        for record in file_records:
            file_path = record.get("file_path")
            if not file_path:
                results.append(DownloadResult(record, None, "failed", "missing file_path"))
                continue

            url = self._resolve_file_url(str(file_path))
            filename = self._filename_from_url(url)
            local_path = output_dir / filename
            if local_path.exists() and not force:
                self.logger.info("Skipping existing raw file: %s", local_path)
                results.append(DownloadResult(record, local_path, "skipped_existing"))
                continue

            try:
                self.logger.info("Downloading %s -> %s", url, local_path)
                response = self._get(url, stream=True)
                with local_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            handle.write(chunk)
                results.append(DownloadResult(record, local_path, "downloaded"))
            except Exception as exc:  # noqa: BLE001 - keep batch downloads moving.
                self.logger.warning("Failed downloading %s: %s", url, exc)
                results.append(DownloadResult(record, None, "failed", str(exc)))
        return results

    def _get(self, url: str, **kwargs: Any) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except Exception as exc:  # noqa: BLE001 - retry network and HTTP failures.
                last_error = exc
                if attempt >= self.retries:
                    break
                sleep_for = self.backoff_seconds * (2 ** (attempt - 1))
                self.logger.warning(
                    "Request failed on attempt %s/%s for %s: %s; retrying in %.1fs",
                    attempt,
                    self.retries,
                    url,
                    exc,
                    sleep_for,
                )
                time.sleep(sleep_for)
        raise RuntimeError(f"Request failed after {self.retries} attempts for {url}: {last_error}")

    @staticmethod
    def _decode_json_response(response: requests.Response) -> Any:
        try:
            return response.json()
        except json.JSONDecodeError:
            return json.loads(response.text.lstrip("\ufeff"))

    @staticmethod
    def _resolve_file_url(file_path: str) -> str:
        if file_path.startswith(("http://", "https://")):
            return file_path
        return urljoin(f"{ADMIE_BASE_URL}/", file_path.lstrip("/"))

    @staticmethod
    def _filename_from_url(url: str) -> str:
        parsed = urlparse(url)
        filename = Path(unquote(parsed.path)).name
        if not filename:
            raise ValueError(f"Could not derive filename from URL: {url}")
        return filename
