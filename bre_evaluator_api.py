#!/usr/bin/env python3
"""
Read data from applicant_reject_table.xlsx and combined_reject_table.xlsx,
call the bre-evaluator API for each row, and append bre_status and loan_terms
from the response to the respective sheets.
"""

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000/api/v1/bre-evaluator"
REQUEST_TIMEOUT = 60
MAX_WORKERS = 10  # concurrent API requests


def load_excel(path: Path) -> pd.DataFrame:
    """Load an Excel file into a DataFrame."""
    return pd.read_excel(path, engine="openpyxl")


def call_bre_api(request_payload) -> dict | None:
    """POST request_payload to bre-evaluator API and return parsed JSON response."""
    try:
        if pd.isna(request_payload) or request_payload is None:
            return None
        if isinstance(request_payload, str):
            if not request_payload.strip():
                return None
            payload = json.loads(request_payload)
        elif isinstance(request_payload, dict):
            payload = request_payload
        else:
            return None

        response = requests.post(
            API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        logger.warning("API request failed: %s", e)
        return None
    except json.JSONDecodeError as e:
        logger.warning("Invalid API response JSON: %s", e)
        return None


def _extract_result(result: dict | None) -> tuple:
    """Extract bre_status and loan_terms from API response."""
    if result is None:
        return (None, None)
    loan_terms = result.get("loan_terms")
    loan_terms_str = (
        json.dumps(loan_terms) if isinstance(loan_terms, (dict, list)) else loan_terms
    )
    return (result.get("bre_status"), loan_terms_str)


def enrich_df(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """Call API for each row in parallel, extract bre_status and loan_terms, add as columns."""
    total = len(df)
    results = [None] * total  # pre-allocate to preserve order

    payloads = df["request_payload"].tolist()

    logger.info(
        "[%s] Starting ThreadPoolExecutor with max_workers=%d for %d rows",
        sheet_name,
        MAX_WORKERS,
        total,
    )
    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {executor.submit(call_bre_api, p): i for i, p in enumerate(payloads)}
        logger.info("[%s] Submitted %d tasks to thread pool", sheet_name, len(future_to_idx))
        done = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            thread_name = threading.current_thread().name
            try:
                result = future.result()
                results[idx] = _extract_result(result)
                logger.debug(
                    "[%s] Thread %s completed row %d (bre_status=%s)",
                    sheet_name,
                    thread_name,
                    idx,
                    results[idx][0] if results[idx] else None,
                )
            except Exception as e:
                logger.warning(
                    "[%s] Thread %s failed row %d: %s",
                    sheet_name,
                    thread_name,
                    idx,
                    e,
                )
                results[idx] = (None, None)
            done += 1
            if done % 50 == 0 or done == total:
                elapsed = time.perf_counter() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                logger.info(
                    "[%s] %d/%d rows done | %.1f req/s | active threads: %d",
                    sheet_name,
                    done,
                    total,
                    rate,
                    threading.active_count(),
                )

    elapsed = time.perf_counter() - start_time
    logger.info(
        "[%s] ThreadPoolExecutor finished: %d rows in %.2fs (%.1f req/s avg)",
        sheet_name,
        total,
        elapsed,
        total / elapsed if elapsed > 0 else 0,
    )

    bre_statuses = [r[0] for r in results]
    loan_terms_list = [r[1] for r in results]

    df = df.copy()
    df["bre_status"] = bre_statuses
    df["loan_terms"] = loan_terms_list
    return df


def main() -> int:
    """Main execution flow."""
    script_dir = Path(__file__).parent
    applicant_path = script_dir / "applicant_reject_table.xlsx"
    combined_path = script_dir / "combined_reject_table.xlsx"

    for path in [applicant_path, combined_path]:
        if not path.exists():
            logger.error("File not found: %s. Run bre_evaluator_export.py first.", path)
            return 1

    logger.info("Loading Excel files...")
    applicant_df = load_excel(applicant_path)
    combined_df = load_excel(combined_path)

    logger.info("Applicant sheet: length=%d rows", len(applicant_df))
    logger.info("Combined sheet: length=%d rows", len(combined_df))

    logger.info("Calling API for applicant_reject_table...")
    applicant_df = enrich_df(applicant_df, "applicant_reject")
    applicant_df.to_excel(applicant_path, index=False, engine="openpyxl")
    logger.info("Saved applicant_reject_table.xlsx (length=%d rows)", len(applicant_df))

    logger.info("Calling API for combined_reject_table...")
    combined_df = enrich_df(combined_df, "combined_reject")
    combined_df.to_excel(combined_path, index=False, engine="openpyxl")
    logger.info("Saved combined_reject_table.xlsx (length=%d rows)", len(combined_df))

    logger.info("Done!")
    return 0


if __name__ == "__main__":
    exit(main())
