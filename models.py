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

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class AuditResult:
    url: str
    page_title: str = ""
    final_url: str = ""
    http_status: int | None = None
    classification: str = ""
    main_content_word_count: int | None = None
    header_found: bool | None = None
    footer_found: bool | None = None
    standard_layout_found: bool | None = None
    content_load_status: str = ""
    detected_at: str = ""
    screenshot_path: str = ""
    html_path: str = ""
    text_sample: str = ""
    notes: str = ""
    error_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiscoveryResult:
    discovered_urls: list[str]
    source_counts: dict[str, int]
    errors: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovered_urls": self.discovered_urls,
            "source_counts": self.source_counts,
            "errors": self.errors,
        }
