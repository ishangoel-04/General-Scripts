#!/usr/bin/env python3
"""
Filter applicant_reject_table.xlsx and combined_reject_table.xlsx to retain only
rows where loan_terms JSON has "low_ltv_exp" flag as true.
Adds filtered data as new sheets in the original files (does not overwrite).
"""

import json
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def has_low_ltv_exp(loan_terms_val) -> bool:
    """Return True if loan_terms has low_ltv_exp flag set to true."""
    if pd.isna(loan_terms_val) or loan_terms_val is None:
        return False
    try:
        if isinstance(loan_terms_val, str):
            if not loan_terms_val.strip():
                return False
            data = json.loads(loan_terms_val)
        elif isinstance(loan_terms_val, dict):
            data = loan_terms_val
        else:
            return False
        return data.get("low_ltv_exp") is True
    except (json.JSONDecodeError, TypeError, AttributeError):
        return False


def filter_excel(path: Path) -> tuple[pd.DataFrame, int, int]:
    """Load Excel, filter rows with low_ltv_exp=true, return (filtered_df, original_len, filtered_len)."""
    df = pd.read_excel(path, engine="openpyxl")

    if "loan_terms" not in df.columns:
        logger.warning("No 'loan_terms' column in %s, skipping", path.name)
        return df, len(df), 0

    original_len = len(df)
    mask = df["loan_terms"].apply(has_low_ltv_exp)
    filtered_df = df[mask].copy()
    filtered_len = len(filtered_df)

    return filtered_df, original_len, filtered_len


def main() -> int:
    script_dir = Path(__file__).parent
    applicant_path = script_dir / "applicant_reject_table.xlsx"
    combined_path = script_dir / "combined_reject_table.xlsx"

    for path in [applicant_path, combined_path]:
        if not path.exists():
            logger.error("File not found: %s", path)
            return 1

    NEW_SHEET_NAME = "low_ltv_exp"

    for path in [applicant_path, combined_path]:
        logger.info("Processing %s...", path.name)
        filtered_df, original_len, filtered_len = filter_excel(path)
        logger.info(
            "%s: %d rows total, %d rows with low_ltv_exp=true",
            path.name,
            original_len,
            filtered_len,
        )
        with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            filtered_df.to_excel(writer, sheet_name=NEW_SHEET_NAME, index=False)
        logger.info("Added sheet '%s' to %s", NEW_SHEET_NAME, path.name)

    logger.info("Done!")
    return 0


if __name__ == "__main__":
    exit(main())
