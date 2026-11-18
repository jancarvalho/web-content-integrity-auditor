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

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "cmpid", "cid",
}


def normalize_url(base_url: str, href: str, allowed_domains: set[str],
                  allowed_path_prefixes: tuple[str, ...],
                  excluded_extensions: tuple[str, ...],
                  excluded_path_fragments: tuple[str, ...]) -> str | None:
    if not href:
        return None
    href = href.strip()
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    scheme = parsed.scheme.lower()
    netloc = parsed.hostname or ""
    if scheme not in {"http", "https"} or netloc not in allowed_domains or parsed.username is not None:
        return None
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    path_lower = path.lower()
    if allowed_path_prefixes and not path_lower.startswith(tuple(p.lower() for p in allowed_path_prefixes)):
        return None
    if any(fragment.lower() in path_lower for fragment in excluded_path_fragments):
        return None
    if path_lower.endswith(tuple(ext.lower() for ext in excluded_extensions)):
        return None
    filtered_query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                      if k.lower() not in TRACKING_QUERY_PARAMS]
    return urlunparse((
        scheme, parsed.netloc.lower(),
        path or "/", "", urlencode(filtered_query, doseq=True), "",
    ))


def count_words(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ’'-]+\b", text, flags=re.UNICODE))


def safe_filename(value: str, max_length: int = 110) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "page"
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"{cleaned[:max_length]}_{digest}"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
