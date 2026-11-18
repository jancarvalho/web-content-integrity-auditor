from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()
from typing import Iterable
from urllib.parse import urlsplit


@dataclass(slots=True)
class AuditConfig:
    start_urls: list[str] = field(default_factory=lambda: [
        os.getenv("START_URL", "http://fixture:8080/section"),
    ])
    allowed_domains: set[str] = field(default_factory=set)
    allowed_path_prefixes: tuple[str, ...] = ()
    excluded_path_fragments: tuple[str, ...] = (
        "/privacy-policy", "/terms-and-conditions", "/cookie-policy",
    )
    excluded_extensions: tuple[str, ...] = (
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".doc", ".docx", ".xls", ".xlsx",
        ".ppt", ".pptx", ".mp3", ".mp4", ".avi", ".mov", ".css", ".js",
    )
    low_content_threshold: int = int(os.getenv("LOW_CONTENT_THRESHOLD", "30"))
    blank_content_threshold: int = 0
    navigation_timeout_ms: int = 60000
    content_wait_timeout_ms: int = 12000
    poll_interval_ms: int = 500
    post_navigation_wait_ms: int = 1500
    discovery_max_pages: int = int(os.getenv("MAX_PAGES", "10000"))
    discovery_max_depth: int = int(os.getenv("MAX_DEPTH", "12"))
    audit_concurrency: int = int(os.getenv("AUDIT_CONCURRENCY", "3"))
    headless: bool = os.getenv("HEADLESS", "true").strip().lower() in {"1", "true", "yes", "y"}
    browser_name: str = "chromium"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    screenshot_full_page: bool = True
    screenshot_only_failures: bool = True
    include_text_sample_chars: int = 500
    save_html_for_failures: bool = False
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "output"))
    screenshots_dir_name: str = "screenshots"
    html_dir_name: str = "html"
    report_filename: str = "web_content_audit.xlsx"
    raw_results_filename: str = "web_content_results.json"
    discovered_urls_filename: str = "discovered_urls.json"
    use_sitemap_discovery: bool = os.getenv("USE_SITEMAP_DISCOVERY", "false").lower() == "true"
    restrict_scope: bool = os.getenv("RESTRICT_SCOPE", "true").lower() == "true"
    include_parent_urls: bool = os.getenv("INCLUDE_PARENT_URLS", "true").lower() == "true"
    expand_dynamic: bool = os.getenv("EXPAND_DYNAMIC_CONTENT", "true").lower() == "true"
    max_clicks: int = int(os.getenv("DYNAMIC_MAX_CLICKS", "30"))
    dynamic_wait_ms: int = int(os.getenv("DYNAMIC_WAIT_MS", "2500"))
    sitemap_candidates: tuple[str, ...] = ()
    cookie_accept_selectors: tuple[str, ...] = (
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept All Cookies')",
        "button:has-text('Accept all cookies')",
        "button:has-text('Accept Cookies')",
        "button:has-text('I Accept')",
    )
    main_content_selectors: tuple[str, ...] = (
        "main", "[role='main']", "#main-content", "#main", ".main-content",
        ".page-content", ".content-main", ".cmp-container--main", ".root-container",
    )
    header_selectors: tuple[str, ...] = ("header", "[role='banner']", ".header", "#header")
    footer_selectors: tuple[str, ...] = ("footer", "[role='contentinfo']", ".footer", "#footer")
    excluded_content_selectors: tuple[str, ...] = (
        "header", "footer", "nav", "aside", "script", "style", "noscript",
        "template", "[role='navigation']", "[role='banner']", "[role='contentinfo']",
        "[role='dialog']", ".modal", ".cookie-banner", "#onetrust-banner-sdk",
        "#onetrust-consent-sdk", ".breadcrumb", ".breadcrumbs", ".social-share",
    )

    def __post_init__(self):
        self.update_start_urls(self.start_urls)

    def in_scope(self, url: str) -> bool:
        u = urlsplit(url)
        if u.hostname not in self.allowed_domains:
            return False
        if not self.restrict_scope:
            return True
        for seed in self.start_urls:
            root = urlsplit(seed)
            path = root.path.rstrip('/')
            if (u.scheme, u.netloc) == (root.scheme, root.netloc) and (u.path.rstrip('/') == path or u.path.startswith(path + '/')):
                return True
        return False

    def ensure_output_directories(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        if self.save_html_for_failures:
            self.html_dir.mkdir(parents=True, exist_ok=True)

    @property
    def screenshots_dir(self) -> Path:
        return self.output_dir / self.screenshots_dir_name

    @property
    def html_dir(self) -> Path:
        return self.output_dir / self.html_dir_name

    @property
    def report_path(self) -> Path:
        return self.output_dir / self.report_filename

    @property
    def raw_results_path(self) -> Path:
        return self.output_dir / self.raw_results_filename

    @property
    def discovered_urls_path(self) -> Path:
        return self.output_dir / self.discovered_urls_filename

    def update_start_urls(self, urls: Iterable[str]) -> None:
        cleaned = [str(url).strip() for url in urls if str(url).strip()]
        if cleaned:
            self.start_urls = cleaned
            roots = [urlsplit(x) for x in cleaned]
            if any(x.scheme not in {'http','https'} or not x.hostname or x.username for x in roots):
                raise ValueError('Start URLs must be HTTP(S) without credentials')
            self.allowed_domains = {x.hostname for x in roots}
            self.sitemap_candidates = tuple(dict.fromkeys(f'{x.scheme}://{x.netloc}/{name}' for x in roots for name in ('sitemap.xml','robots.txt')))


CONFIG = AuditConfig()
