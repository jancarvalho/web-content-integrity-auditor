from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlsplit, urlunsplit
from collections import deque
from datetime import datetime
from typing import Iterable

from playwright.async_api import Browser, BrowserContext, Page, Playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from config import AuditConfig
from models import AuditResult, DiscoveryResult
from sitemap import discover_urls_from_sitemaps
from utils import count_words, normalize_url, safe_filename, write_json


class WebContentCrawler:
    def __init__(self, config: AuditConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "WebContentCrawler":
        self._playwright = await async_playwright().start()
        browser_type = getattr(self._playwright, self.config.browser_name)
        self._browser = await browser_type.launch(headless=self.config.headless)
        self._context = await self._browser.new_context(
            user_agent=self.config.user_agent,
            viewport={"width": 1440, "height": 1100},
            ignore_https_errors=False,
            locale="en-US",
        )
        self._context.set_default_timeout(15000)
        self._context.set_default_navigation_timeout(self.config.navigation_timeout_ms)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _new_page(self) -> Page:
        if not self._context:
            raise RuntimeError("Crawler context is not initialized.")
        return await self._context.new_page()

    async def _accept_cookies(self, page: Page) -> None:
        for selector in self.config.cookie_accept_selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() > 0 and await locator.is_visible():
                    await locator.click(timeout=2500)
                    await page.wait_for_timeout(500)
                    return
            except Exception:
                continue

    async def _extract_internal_links(self, page: Page, current_url: str) -> set[str]:
        hrefs = await page.locator("a[href], area[href]").evaluate_all(
            "(elements) => elements.map((el) => el.getAttribute('href')).filter(Boolean)"
        )
        results: set[str] = set()
        for href in hrefs:
            normalized = normalize_url(
                current_url, href, self.config.allowed_domains,
                self.config.allowed_path_prefixes, self.config.excluded_extensions,
                self.config.excluded_path_fragments,
            )
            if normalized:
                results.add(normalized)
        return results

    async def _expand_dynamic_content(self, page: Page) -> set[str]:
        total = await self._extract_internal_links(page, page.url)
        controls = page.get_by_role('button').filter(has_text=re.compile(r'^\s*(show|load|view|see) more\s*$', re.I))
        unchanged = 0
        for _ in range(self.config.max_clicks):
            control = None
            for candidate in await controls.all():
                if await candidate.is_visible() and await candidate.is_enabled():
                    control = candidate
                    break
            if control is None:
                break
            try:
                await control.click(timeout=5000)
            except PlaywrightTimeoutError:
                break
            before = set(total)
            for _ in range(max(1, self.config.dynamic_wait_ms // 250)):
                await page.wait_for_timeout(250)
                total.update(await self._extract_internal_links(page, page.url))
            unchanged = 0 if total - before else unchanged + 1
            self.logger.info('Dynamic links: %s (+%s)', len(total), len(total-before))
            if unchanged >= 2:
                break
        return total

    async def discover_site_urls(self) -> DiscoveryResult:
        discovered: set[str] = set()
        source_counts = {"seed": 0, "sitemap": 0, "crawl": 0}
        errors: list[dict[str, str]] = []

        for url in self.config.start_urls:
            normalized = normalize_url(
                url, url, self.config.allowed_domains,
                self.config.allowed_path_prefixes, self.config.excluded_extensions,
                self.config.excluded_path_fragments,
            )
            if normalized and self.config.in_scope(normalized) and len(discovered) < self.config.discovery_max_pages:
                discovered.add(normalized)
        source_counts["seed"] = len(discovered)

        if self.config.use_sitemap_discovery:
            sitemap_urls, sitemap_errors = await discover_urls_from_sitemaps(self.config)
            before = len(discovered)
            discovered.update(sorted(x for x in sitemap_urls if self.config.in_scope(x))[:max(0, self.config.discovery_max_pages-len(discovered))])
            source_counts["sitemap"] = len(discovered) - before
            errors.extend(sitemap_errors)

        queue: deque[tuple[str, int]] = deque((url, 0) for url in sorted(discovered))
        visited: set[str] = set()
        queued: set[str] = {url for url, _ in queue}

        while queue and len(visited) < self.config.discovery_max_pages:
            current_url, depth = queue.popleft()
            queued.discard(current_url)
            if current_url in visited:
                continue
            visited.add(current_url)
            page = await self._new_page()
            try:
                response = await page.goto(
                    current_url, wait_until="domcontentloaded",
                    timeout=self.config.navigation_timeout_ms,
                )
                await self._accept_cookies(page)
                await page.wait_for_timeout(500)
                if response and response.status >= 400:
                    errors.append({"url": current_url, "error": f"Discovery HTTP {response.status}"})
                    continue
                if not self.config.in_scope(page.url):
                    errors.append({"url": current_url, "error": "Redirect outside scope"})
                    continue
                if depth >= self.config.discovery_max_depth:
                    continue
                links = await self._extract_internal_links(page, page.url)
                if self.config.expand_dynamic:
                    try:
                        links.update(await self._expand_dynamic_content(page))
                    except Exception as exc:
                        errors.append({"url": current_url, "error": f"Expansion: {exc}"})
                if self.config.include_parent_urls:
                    for link in list(links):
                        u = urlsplit(link)
                        parts = u.path.strip('/').split('/')
                        for i in range(1, len(parts)):
                            links.add(urlunsplit((u.scheme, u.netloc, '/' + '/'.join(parts[:i]), '', '')))
                for link in sorted(links):
                    link = normalize_url(current_url, link, self.config.allowed_domains, self.config.allowed_path_prefixes, self.config.excluded_extensions, self.config.excluded_path_fragments)
                    if not link or not self.config.in_scope(link):
                        continue
                    if len(discovered) >= self.config.discovery_max_pages:
                        break
                    if link not in discovered:
                        discovered.add(link)
                        source_counts["crawl"] += 1
                    if link not in visited and link not in queued:
                        queue.append((link, depth + 1))
                        queued.add(link)
            except PlaywrightTimeoutError:
                errors.append({"url": current_url, "error": "Discovery timeout"})
            except Exception as exc:
                errors.append({"url": current_url, "error": f"{type(exc).__name__}: {exc}"})
            finally:
                await page.close()

        return DiscoveryResult(sorted(discovered), source_counts, errors)

    async def _detect_visible_selector(self, page: Page, selectors: Iterable[str]) -> tuple[bool, str]:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() > 0 and await locator.is_visible():
                    return True, selector
            except Exception:
                continue
        return False, ""

    async def _extract_main_content_text(self, page: Page) -> tuple[str, str]:
        result = await page.evaluate(
            r"""
            ({mainSelectors, excludedSelectors}) => {
                const normalize = (value) => (value || "").replace(/\s+/g, " ").trim();
                const isVisible = (element) => {
                    if (!element) return false;
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== "none" && style.visibility !== "hidden" &&
                           Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0;
                };
                for (const selector of mainSelectors) {
                    const candidates = Array.from(document.querySelectorAll(selector)).filter(isVisible);
                    for (const candidate of candidates) {
                        const clone = candidate.cloneNode(true);
                        clone.querySelectorAll(excludedSelectors.join(",")).forEach((el) => el.remove());
                        const text = normalize(clone.textContent);
                        return {text, selector};
                    }
                }
                const fallback = document.body.cloneNode(true);
                fallback.querySelectorAll(excludedSelectors.join(",")).forEach((el) => el.remove());
                return {text: normalize(fallback.innerText || fallback.textContent), selector: "body_fallback"};
            }
            """,
            {
                "mainSelectors": list(self.config.main_content_selectors),
                "excludedSelectors": list(self.config.excluded_content_selectors),
            },
        )
        return result.get("text", ""), result.get("selector", "")

    async def _wait_for_main_content(self, page: Page) -> tuple[str, str, str]:
        elapsed = 0
        previous_text = None
        stable_checks = 0
        selected_selector = ""
        while elapsed < self.config.content_wait_timeout_ms:
            text, selected_selector = await self._extract_main_content_text(page)
            if text == previous_text:
                stable_checks += 1
            else:
                previous_text = text
                stable_checks = 0
            if stable_checks >= 2:
                return text, selected_selector, "stable"
            await page.wait_for_timeout(self.config.poll_interval_ms)
            elapsed += self.config.poll_interval_ms
        text, selected_selector = await self._extract_main_content_text(page)
        return text, selected_selector, "timeout"

    def _classify(self, http_status: int | None, word_count: int,
                  header_found: bool, footer_found: bool) -> str:
        if http_status != 200:
            return "NON_200"
        if not header_found or not footer_found:
            return "LAYOUT_NOT_CONFIRMED"
        if word_count <= self.config.blank_content_threshold:
            return "BLANK"
        if word_count < self.config.low_content_threshold:
            return "LOW_CONTENT"
        return "PASS"

    async def audit_url(self, url: str) -> AuditResult:
        page = await self._new_page()
        detected_at = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            response = await page.goto(url, wait_until="domcontentloaded",
                                       timeout=self.config.navigation_timeout_ms)
            await self._accept_cookies(page)
            await page.wait_for_timeout(self.config.post_navigation_wait_ms)
            http_status = response.status if response else None
            final_url = page.url
            page_title = await page.title()
            header_found, header_selector = await self._detect_visible_selector(page, self.config.header_selectors)
            footer_found, footer_selector = await self._detect_visible_selector(page, self.config.footer_selectors)
            main_text, main_selector, load_status = await self._wait_for_main_content(page)
            word_count = count_words(main_text)
            classification = self._classify(http_status, word_count, header_found, footer_found)
            screenshot_path = ""
            html_path = ""
            should_capture = (not self.config.screenshot_only_failures or
                              classification in {"BLANK", "LOW_CONTENT", "LAYOUT_NOT_CONFIRMED", "NON_200"})
            filename_seed = safe_filename(url)
            if should_capture:
                path = self.config.screenshots_dir / f"{filename_seed}.png"
                await page.screenshot(path=str(path), full_page=self.config.screenshot_full_page, type="png")
                screenshot_path = str(path.resolve())
            if self.config.save_html_for_failures and classification in {"BLANK", "LOW_CONTENT", "LAYOUT_NOT_CONFIRMED"}:
                path = self.config.html_dir / f"{filename_seed}.html"
                path.write_text(await page.content(), encoding="utf-8")
                html_path = str(path.resolve())
            notes = (f"main_selector={main_selector}; header_selector={header_selector or 'not_found'}; "
                     f"footer_selector={footer_selector or 'not_found'}")
            return AuditResult(
                url=url, page_title=page_title, final_url=final_url, http_status=http_status,
                classification=classification, main_content_word_count=word_count,
                header_found=header_found, footer_found=footer_found,
                standard_layout_found=header_found and footer_found,
                content_load_status=load_status, detected_at=detected_at,
                screenshot_path=screenshot_path, html_path=html_path,
                text_sample=main_text[:self.config.include_text_sample_chars], notes=notes,
            )
        except PlaywrightTimeoutError as exc:
            return AuditResult(url=url, classification="NAVIGATION_TIMEOUT", detected_at=detected_at,
                               notes=str(exc), error_type="PlaywrightTimeoutError")
        except Exception as exc:
            return AuditResult(url=url, classification="EXECUTION_ERROR", detected_at=detected_at,
                               notes=str(exc), error_type=type(exc).__name__)
        finally:
            await page.close()

    async def audit_urls(self, urls: Iterable[str]) -> list[AuditResult]:
        semaphore = asyncio.Semaphore(self.config.audit_concurrency)
        urls_list = list(urls)
        total = len(urls_list)
        completed = 0
        completed_lock = asyncio.Lock()

        async def worker(url: str) -> AuditResult:
            nonlocal completed
            async with semaphore:
                result = await self.audit_url(url)
            async with completed_lock:
                completed += 1
                words = "" if result.main_content_word_count is None else result.main_content_word_count
                print(f"[{completed}/{total}] {result.classification:22} {str(words):>5} words | {url}")
            return result

        return await asyncio.gather(*(worker(url) for url in urls_list))


async def run_discovery(config: AuditConfig) -> DiscoveryResult:
    config.ensure_output_directories()
    async with WebContentCrawler(config) as crawler:
        result = await crawler.discover_site_urls()
    write_json(config.discovered_urls_path, result.to_dict())
    return result


async def run_audit(config: AuditConfig, urls: Iterable[str]) -> list[AuditResult]:
    config.ensure_output_directories()
    async with WebContentCrawler(config) as crawler:
        results = await crawler.audit_urls(urls)
    write_json(config.raw_results_path, [item.to_dict() for item in results])
    return results
