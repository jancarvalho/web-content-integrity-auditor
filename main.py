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

import argparse
import asyncio
import logging
from collections import Counter
from pathlib import Path

from config import CONFIG
from crawler import run_audit, run_discovery
from report import build_excel_report
from utils import read_json, write_json
from banner import print_banner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Crawl configured web pages and identify HTTP 200 pages whose main "
            "content is blank or contains fewer than the configured number of words."
        )
    )
    parser.add_argument("--mode", choices=("all", "discover", "audit"), default="all")
    parser.add_argument("--start-url", action="append", dest="start_urls")
    parser.add_argument("--urls-file", type=Path)
    parser.add_argument("--threshold", type=int, default=CONFIG.low_content_threshold)
    parser.add_argument("--max-pages", type=int, default=CONFIG.discovery_max_pages)
    parser.add_argument("--max-depth", type=int, default=CONFIG.discovery_max_depth)
    parser.add_argument("--audit-concurrency", type=int, default=CONFIG.audit_concurrency)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--capture-all", action="store_true")
    parser.add_argument("--save-html", action="store_true")
    return parser.parse_args()


def load_urls_from_file(path: Path) -> list[str]:
    data = read_json(path)
    if isinstance(data, list):
        return [str(item) for item in data]
    if isinstance(data, dict) and isinstance(data.get("discovered_urls"), list):
        return [str(item) for item in data["discovered_urls"]]
    raise ValueError("URLs file must contain a JSON list or an object with discovered_urls.")


async def async_main() -> None:
    print_banner()
    args = parse_args()
    CONFIG.low_content_threshold = max(1, args.threshold)
    CONFIG.discovery_max_pages = max(1, args.max_pages)
    CONFIG.discovery_max_depth = max(0, args.max_depth)
    CONFIG.audit_concurrency = max(1, args.audit_concurrency)
    CONFIG.headless = not args.headed
    CONFIG.screenshot_only_failures = not args.capture_all
    CONFIG.save_html_for_failures = args.save_html
    if args.start_urls:
        CONFIG.update_start_urls(args.start_urls)
    CONFIG.ensure_output_directories()

    discovery_result = None
    urls: list[str] = []
    if args.mode in {"all", "discover"}:
        print("Starting site-wide URL discovery...")
        discovery_result = await run_discovery(CONFIG)
        urls = discovery_result.discovered_urls
        print(f"Discovery completed: {len(urls)} normalized internal URL(s).")
        print(f"Discovery sources: {discovery_result.source_counts}")
        print(f"Discovery output: {CONFIG.discovered_urls_path.resolve()}")
        if args.mode == "discover":
            return

    if args.mode == "audit":
        if args.urls_file:
            urls = load_urls_from_file(args.urls_file)
        else:
            if not CONFIG.discovered_urls_path.exists():
                raise FileNotFoundError("No URLs file was supplied and no previous discovery file exists.")
            urls = load_urls_from_file(CONFIG.discovered_urls_path)

    if not urls:
        raise RuntimeError("No URLs are available for audit.")

    print(f"Starting content audit for {len(urls)} URL(s)...")
    results = await run_audit(CONFIG, urls)
    expected = Counter(urls)
    actual = Counter(row.url for row in results)
    reconciliation = {"requested": len(urls), "audited": len(results), "missing": list((expected-actual).elements()), "unexpected": list((actual-expected).elements())}
    write_json(CONFIG.output_dir / "reconciliation.json", reconciliation)
    report_path = build_excel_report(
        CONFIG,
        results,
        discovery_source_counts=discovery_result.source_counts if discovery_result else None,
        discovery_errors=discovery_result.errors if discovery_result else None,
    )
    print("\nAudit completed.")
    print(f"Excel report: {report_path.resolve()}")
    print(f"Raw JSON: {CONFIG.raw_results_path.resolve()}")
    print(f"Screenshots: {CONFIG.screenshots_dir.resolve()}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(async_main())
