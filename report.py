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

from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from config import AuditConfig
from models import AuditResult

REPORT_COLUMNS = [
    "page_title", "url", "final_url", "http_status", "classification",
    "main_content_word_count", "header_found", "footer_found",
    "standard_layout_found", "content_load_status", "detected_at",
    "screenshot_path", "html_path", "text_sample", "notes", "error_type",
]


def _rows(results: Iterable[AuditResult]) -> list[dict]:
    return [result.to_dict() for result in results]


def _autosize(ws, max_width: int = 70) -> None:
    for column_cells in ws.columns:
        length = 0
        column_letter = get_column_letter(column_cells[0].column)
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            length = max(length, len(value))
        ws.column_dimensions[column_letter].width = min(length + 2, max_width)


def _style_header(ws) -> None:
    fill = PatternFill("solid", fgColor="1F4E78")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _write_dataframe(ws, df: pd.DataFrame) -> None:
    for col_idx, column_name in enumerate(df.columns, start=1):
        ws.cell(row=1, column=col_idx, value=column_name)
    for row_idx, row in enumerate(df.itertuples(index=False), start=2):
        for col_idx, value in enumerate(row, start=1):
            if pd.isna(value):
                value = ""
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            if isinstance(value, str):
                cell.data_type = "s"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _style_header(ws)
    _autosize(ws)


def _add_hyperlinks(ws, df: pd.DataFrame) -> None:
    column_index = {name: idx + 1 for idx, name in enumerate(df.columns)}
    for row_idx in range(2, len(df) + 2):
        for name in ("url", "final_url", "screenshot_path", "html_path"):
            idx = column_index.get(name)
            if not idx:
                continue
            cell = ws.cell(row=row_idx, column=idx)
            value = str(cell.value or "").strip()
            if not value:
                continue
            if name in {"url", "final_url"}:
                cell.hyperlink = value
            else:
                try:
                    cell.hyperlink = Path(value).resolve().as_uri()
                except Exception:
                    continue
            cell.style = "Hyperlink"


def build_excel_report(config: AuditConfig, results: Iterable[AuditResult],
                       discovery_source_counts: dict[str, int] | None = None,
                       discovery_errors: list[dict[str, str]] | None = None) -> Path:
    result_list = list(results)
    all_df = pd.DataFrame(_rows(result_list), columns=REPORT_COLUMNS)
    if all_df.empty:
        all_df = pd.DataFrame(columns=REPORT_COLUMNS)

    findings_df = all_df[all_df["classification"].isin(["BLANK", "LOW_CONTENT"])].copy()
    errors_df = all_df[all_df["classification"].isin([
        "NON_200", "LAYOUT_NOT_CONFIRMED", "NAVIGATION_TIMEOUT", "EXECUTION_ERROR",
    ])].copy()

    counts = Counter(all_df["classification"].tolist())
    summary_rows = [
        {"Metric": "Total URLs audited", "Value": len(all_df)},
        {"Metric": "HTTP 200 pages", "Value": int((all_df["http_status"] == 200).sum())},
        {"Metric": "Blank pages", "Value": counts.get("BLANK", 0)},
        {"Metric": "Low-content pages", "Value": counts.get("LOW_CONTENT", 0)},
        {"Metric": "Passed pages", "Value": counts.get("PASS", 0)},
        {"Metric": "Layout not confirmed", "Value": counts.get("LAYOUT_NOT_CONFIRMED", 0)},
        {"Metric": "Non-200 pages", "Value": counts.get("NON_200", 0)},
        {"Metric": "Navigation timeouts", "Value": counts.get("NAVIGATION_TIMEOUT", 0)},
        {"Metric": "Execution errors", "Value": counts.get("EXECUTION_ERROR", 0)},
        {"Metric": "Low-content threshold", "Value": config.low_content_threshold},
    ]
    if discovery_source_counts:
        for key, value in discovery_source_counts.items():
            summary_rows.append({"Metric": f"Discovery URLs from {key}", "Value": value})
    summary_df = pd.DataFrame(summary_rows)

    wb = Workbook()
    wb.remove(wb.active)
    sheet_data = [
        ("Summary", summary_df),
        ("Blank and Low Content", findings_df),
        ("All Results", all_df),
        ("Navigation and Errors", errors_df),
    ]
    if discovery_errors:
        sheet_data.append(("Discovery Errors", pd.DataFrame(discovery_errors)))

    for sheet_name, df in sheet_data:
        ws = wb.create_sheet(title=sheet_name[:31])
        _write_dataframe(ws, df)
        _add_hyperlinks(ws, df)

    screenshot_ws = wb.create_sheet(title="Issue Screenshots")
    screenshot_ws.append(["Page Title", "URL", "Classification", "Word Count", "Detected At", "Screenshot"])
    _style_header(screenshot_ws)
    screenshot_ws.freeze_panes = "A2"

    row_number = 2
    for result in result_list:
        if result.classification not in {"BLANK", "LOW_CONTENT"} or not result.screenshot_path:
            continue
        path = Path(result.screenshot_path)
        if not path.exists():
            continue
        screenshot_ws.cell(row=row_number, column=1, value=result.page_title)
        url_cell = screenshot_ws.cell(row=row_number, column=2, value=result.url)
        url_cell.hyperlink = result.url
        url_cell.style = "Hyperlink"
        screenshot_ws.cell(row=row_number, column=3, value=result.classification)
        screenshot_ws.cell(row=row_number, column=4, value=result.main_content_word_count)
        screenshot_ws.cell(row=row_number, column=5, value=result.detected_at)
        try:
            image = XLImage(str(path))
            scale = min(760 / max(image.width, 1), 520 / max(image.height, 1), 1)
            image.width = int(image.width * scale)
            image.height = int(image.height * scale)
            screenshot_ws.add_image(image, f"F{row_number}")
            screenshot_ws.row_dimensions[row_number].height = max(100, image.height * 0.75)
        except Exception as exc:
            screenshot_ws.cell(row=row_number, column=6, value=f"Image could not be embedded: {exc}")
        row_number += 1

    screenshot_ws.column_dimensions["A"].width = 35
    screenshot_ws.column_dimensions["B"].width = 85
    screenshot_ws.column_dimensions["C"].width = 20
    screenshot_ws.column_dimensions["D"].width = 14
    screenshot_ws.column_dimensions["E"].width = 24
    screenshot_ws.column_dimensions["F"].width = 105
    config.report_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(config.report_path)
    return config.report_path
