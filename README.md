# Web Content Integrity Auditor (WCIA)
Discover. Validate. Reconcile.
An open-source, asynchronous web crawling and content integrity auditing framework designed to identify content quality issues, improve URL discovery coverage, and ensure consistency across discovery, auditing, and reporting processes.

## About the Author
### Jânio Ribeiro

Founder, Creator & Original Author of Web Content Integrity Auditor (WCIA).

Senior Data QA Engineer & Data Engineer with professional experience in information technology since 2007, specializing in software engineering, data quality, data engineering, test automation, and enterprise data platforms.

## Areas of Expertise
 - Data Quality Engineering
 - Data Engineering
 - Software Engineering
 - Test Automation
 - Data Integrity and Reconciliation
 - ETL and Data Pipeline Validation
 - Cloud Data Platforms
 - Database Engineering
 - Enterprise Automation

## Project Background
The Web Content Integrity Auditor was originally designed and developed by Jânio Ribeiro, inspired by real-world engineering challenges involving automated website discovery, dynamic content extraction, content quality validation, and end-to-end audit coverage.

The project aims to provide a reusable, platform-independent solution that can be applied across different industries and website architectures.

## Original Authorship
WCIA was originally created by Jânio Ribeiro in 2026.

Contributions, improvements, and extensions from the open-source community are welcome under the terms of the MIT License.

## Copyright and License
Copyright © 2026 Jânio Ribeiro.

This project is distributed under the MIT License. See the LICENSE file for details.

# Web Content Integrity Auditor (WCIA)

A generic Python/Playwright website discovery and content audit utility adapted from an earlier crawler. It discovers internal links, optionally expands common load-more buttons, generates intermediate path candidates, audits pages, and writes Excel and JSON outputs.

## Run with Docker

Requires Docker Engine and Docker Compose v2.24+ (or Docker Desktop). No local Python/browser installation is required. Docker still needs a host, which may be a remote VM or CI runner. Run from this directory:

```sh
docker compose build
docker compose run --rm auditor --mode all --max-pages 100 --max-depth 5
```

The bundled local fixture has 40 article URLs, one index inferred from paths, and one seed (42 expected audit rows). It includes a blank page, a short page, a 503 and an outside-scope link. The fixture is synthetic and is not an independent public reference repository. Results persist in `output/` on the Docker host.

## Authorized website

Copy `.env.example` to `.env` and adjust the seed and options, or override the seed directly:

```sh
docker compose run --rm auditor --mode all --start-url https://example.org/ --max-pages 100 --max-depth 3
```

Only crawl websites you have permission to audit. Use conservative concurrency. Scope defaults to the seed origin and path subtree. Sitemap discovery is off by default; enabling it adds matching URLs from sitemap/robots declarations. This is not a robots exclusion enforcement mechanism. Parent paths are inferred candidates, not proof of existing pages. Avoid running against untrusted sites with access to sensitive networks; browser navigation can follow redirects and load external resources.

## Local execution (optional)

```sh
python -m pip install -r requirements.txt
python -m playwright install chromium
python fixture/server.py
```

In a second terminal:

```sh
python main.py --mode all --start-url http://localhost:8080/section --max-pages 100 --max-depth 5
python -m unittest discover -s tests
```

## Output

- `discovered_urls.json`: normalized discovery results, sources and errors.
- `web_content_results.json`: individual audit outcomes.
- `web_content_audit.xlsx`: summary, all results, findings, errors and screenshots.
- `reconciliation.json`: requested vs returned audit records by original URL (including multiplicity).

`--mode discover` stops after discovery; `--mode audit --urls-file output/discovered_urls.json` reuses its URL list. `--headed` is for local graphical environments, not the default Docker run.

## Limitations

This is an initial public-oriented adaptation, not a production completeness guarantee. Dynamic discovery uses common English button labels and bounded polling, not arbitrary API pagination, virtualized scrolling, or restart checkpoints. Content classification is heuristic and depends on header/footer detection; hidden text may affect word counts. Reconciliation covers input versus audit results, not independent workbook verification. Screenshot links may be container paths. Docker build and end-to-end browser workflow have not been exercised in the preparation environment. The included unit tests cover scope and URL normalization only.

## Publication

Review all code and dependency licenses, confirm rights to publish the original implementation, and select a license before publishing. No license is granted by this package for third-party or employer-owned code. Do not publish client data, logs, screenshots, secrets, or corporate Git history. This adaptation includes AI-assisted changes and is not suitable as an AI-free assessment reference where such repositories are excluded.
