# =============================================================================
# Project: Web Content Integrity Auditor (WCIA)
#
# Original Author: Jânio Ribeiro
# Role: Senior Data QA Engineer & Data Engineer
#
# Copyright (c) 2026 Jânio Ribeiro
#
# SPDX-License-Identifier: MIT
#
# Description:
# An asynchronous framework for website discovery,
# content integrity validation, and audit reconciliation.
#
# Originally designed and developed by Jânio Ribeiro.
# =============================================================================
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import deque
from urllib.parse import urljoin

import aiohttp

from config import AuditConfig
from utils import normalize_url


async def _fetch_text(session: aiohttp.ClientSession, url: str, timeout_seconds: int = 30) -> tuple[int | None, str, str]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_seconds), allow_redirects=True) as response:
            return response.status, await response.text(errors="ignore"), str(response.url)
    except Exception as exc:
        return None, "", f"{type(exc).__name__}: {exc}"


def _extract_sitemap_locations(xml_text: str) -> tuple[list[str], list[str]]:
    page_urls: list[str] = []
    sitemap_urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return page_urls, sitemap_urls
    tag = root.tag.lower()
    if tag.endswith("sitemapindex"):
        for element in root.iter():
            if element.tag.lower().endswith("loc") and element.text:
                sitemap_urls.append(element.text.strip())
    elif tag.endswith("urlset"):
        for element in root.iter():
            if element.tag.lower().endswith("loc") and element.text:
                page_urls.append(element.text.strip())
    return page_urls, sitemap_urls


def _extract_sitemaps_from_robots(text: str, base_url: str) -> list[str]:
    results: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*Sitemap\s*:\s*(.+?)\s*$", line, flags=re.IGNORECASE)
        if match:
            results.append(urljoin(base_url, match.group(1).strip()))
    return results


async def discover_urls_from_sitemaps(config: AuditConfig) -> tuple[set[str], list[dict[str, str]]]:
    discovered: set[str] = set()
    errors: list[dict[str, str]] = []
    queue: deque[str] = deque(config.sitemap_candidates)
    visited: set[str] = set()
    headers = {"User-Agent": config.user_agent}

    async with aiohttp.ClientSession(headers=headers) as session:
        while queue:
            sitemap_url = queue.popleft()
            if sitemap_url in visited:
                continue
            visited.add(sitemap_url)
            status, text, final_value = await _fetch_text(session, sitemap_url)
            if status is None:
                errors.append({"url": sitemap_url, "error": final_value})
                continue
            if status >= 400:
                errors.append({"url": sitemap_url, "error": f"HTTP {status}"})
                continue
            if sitemap_url.lower().endswith("robots.txt") or "user-agent:" in text.lower():
                for child in _extract_sitemaps_from_robots(text, sitemap_url):
                    if child not in visited:
                        queue.append(child)
                continue
            page_urls, sitemap_urls = _extract_sitemap_locations(text)
            for child in sitemap_urls:
                if child not in visited:
                    queue.append(child)
            for candidate in page_urls:
                normalized = normalize_url(
                    candidate, candidate, config.allowed_domains,
                    config.allowed_path_prefixes, config.excluded_extensions,
                    config.excluded_path_fragments,
                )
                if normalized:
                    discovered.add(normalized)
    return discovered, errors
