# =============================================================================
# Project: Web Content Integrity Auditor (WCIA)
# Original Author: Jânio Ribeiro
# Role: Senior Data QA Engineer & Data Engineer
# Copyright (c) 2026 Jânio Ribeiro
# SPDX-License-Identifier: MIT
# =============================================================================

FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# Project metadata and original authorship
LABEL org.opencontainers.image.title="Web Content Integrity Auditor" \
      org.opencontainers.image.description="An asynchronous web crawling and content integrity auditing framework." \
      org.opencontainers.image.authors="Jânio Ribeiro - Senior Data QA Engineer & Data Engineer" \
      org.opencontainers.image.vendor="Jânio Ribeiro" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/jancarvalho/web-content-integrity-auditor" \
      org.opencontainers.image.documentation="https://github.com/jancarvalho/web-content-integrity-auditor/blob/main/README.md" \
      org.opencontainers.image.url="https://github.com/jancarvalho/web-content-integrity-auditor" \
      io.wcia.original-author="Jânio Ribeiro" \
      io.wcia.copyright="Copyright (c) 2026 Jânio Ribeiro" \
      io.wcia.tagline="Discover. Validate. Reconcile."

# Python environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=UTF-8

# Application working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create output directory
RUN mkdir -p /app/output

# Application entry point
ENTRYPOINT ["python", "main.py"]

# Default execution mode
CMD ["--mode", "all"]