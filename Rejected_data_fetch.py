#!/usr/bin/env python3
"""
Fetch BRE evaluator data from MySQL, filter by evaluation_mode and bre_status,
and export to separate Excel files.
"""

import json
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

import mysql.connector
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "prod-datascience-replica.turnocloud.com"),
    "user": os.getenv("MYSQL_USER", "ishan_goel_ro"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "risk_analytics"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
}

TABLE_NAME = os.getenv("MYSQL_TABLE", "api_request_logs")
HTTP_PATH_FILTER = "/api/v1/bre-evaluator"

# Validate table name to prevent SQL injection
if not TABLE_NAME.replace("_", "").isalnum():
    raise ValueError("Invalid MYSQL_TABLE: only alphanumeric and underscore allowed")


def get_db_connection():
    """Create and return a MySQL database connection."""
    return mysql.connector.connect(**MYSQL_CONFIG)


def fetch_bre_data(connection) -> pd.DataFrame:
    """Fetch rows for bre-evaluator path in February 2026."""
    query = """
        SELECT uuid, request_uuid, http_path, created_at, 
               request_payload, response_payload, request_curl, error, warning
        FROM {table}
        WHERE http_path = %s
          AND created_at >= '2026-02-01 00:00:00'
          AND created_at < '2026-03-01 00:00:00'
    """.format(
        table=TABLE_NAME
    )

    return pd.read_sql(query, connection, params=(HTTP_PATH_FILTER,))


def _to_json_string(val) -> str:
    """Convert value to JSON string for Excel storage."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    return json.dumps(val)


def _extract_loan_uuid(row, data: dict) -> str | None:
    """Extract loan_uuid from response_payload or request_payload."""
    loan_uuid = data.get("loan_uuid")
    if loan_uuid:
        return loan_uuid
    req = row["request_payload"]
    if req is None:
        return None
    try:
        req_data = json.loads(req) if isinstance(req, str) else req
        return req_data.get("loan_uuid") if isinstance(req_data, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def parse_response_and_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Parse response_payload JSON and split into two datasets:
    - applicant_reject: evaluation_mode=applicant, bre_status=reject
    - combined_reject: evaluation_mode=combined, bre_status=reject

    Each record contains only: uuid, request_uuid, loan_uuid, request_payload, response_payload.
    """
    OUTPUT_COLUMNS = ["uuid", "request_uuid", "loan_uuid", "request_payload", "response_payload"]
    applicant_rows = []
    combined_rows = []

    for _, row in df.iterrows():
        try:
            payload = row["response_payload"]
            if payload is None or (isinstance(payload, str) and payload.strip() == ""):
                continue

            if isinstance(payload, str):
                data = json.loads(payload)
            else:
                data = payload

            evaluation_mode = data.get("evaluation_mode")
            bre_status = data.get("bre_status")

            record = {
                "uuid": row["uuid"],
                "request_uuid": row["request_uuid"],
                "loan_uuid": _extract_loan_uuid(row, data),
                "request_payload": _to_json_string(row["request_payload"]),
                "response_payload": _to_json_string(row["response_payload"]),
            }

            if evaluation_mode == "applicant" and bre_status == "reject":
                applicant_rows.append(record)
            elif evaluation_mode == "combined" and bre_status == "reject":
                combined_rows.append(record)

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Could not parse response_payload for uuid=%s: %s", row["uuid"], e)
            continue

    applicant_df = (
        pd.DataFrame(applicant_rows, columns=OUTPUT_COLUMNS)
        if applicant_rows
        else pd.DataFrame(columns=OUTPUT_COLUMNS)
    )
    combined_df = (
        pd.DataFrame(combined_rows, columns=OUTPUT_COLUMNS)
        if combined_rows
        else pd.DataFrame(columns=OUTPUT_COLUMNS)
    )

    return applicant_df, combined_df


def main():
    """Main execution flow."""
    password = MYSQL_CONFIG["password"]
    if not password or password == "XXXXXXXXX":
        logger.error("Please set MYSQL_PASSWORD in your .env file with the actual password.")
        return 1

    logger.info("Connecting to MySQL...")
    connection = get_db_connection()

    try:
        logger.info(
            "Fetching data from %s (http_path='%s', Feb 2026)...",
            TABLE_NAME,
            HTTP_PATH_FILTER,
        )
        df = fetch_bre_data(connection)
        fetched_len = len(df)
        logger.info("Fetched raw data: length=%d rows", fetched_len)

        if df.empty:
            logger.info("No data found. Exiting.")
            return 0

        logger.info("Parsing response_payload and filtering...")
        applicant_df, combined_df = parse_response_and_filter(df)

        applicant_len = len(applicant_df)
        combined_len = len(combined_df)
        total_len = applicant_len + combined_len

        logger.info(
            "Processed datasets: applicant_reject length=%d rows, combined_reject length=%d rows, total=%d rows",
            applicant_len,
            combined_len,
            total_len,
        )

        output_dir = Path(__file__).parent
        applicant_path = output_dir / "applicant_reject_table.xlsx"
        combined_path = output_dir / "combined_reject_table.xlsx"

        applicant_df.to_excel(applicant_path, index=False, engine="openpyxl")
        logger.info("Saved applicant_reject_table.xlsx (length=%d rows)", applicant_len)

        combined_df.to_excel(combined_path, index=False, engine="openpyxl")
        logger.info("Saved combined_reject_table.xlsx (length=%d rows)", combined_len)

        logger.info("Done!")
        return 0

    finally:
        connection.close()


if __name__ == "__main__":
    exit(main())
