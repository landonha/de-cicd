import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "lambda" / "src"))

import lambda_function


def test_parse_csv_and_normalize_record():
    rows = lambda_function.parse_csv(
        "event_id,customer_id,event_type,amount,event_ts\n"
        " e-1 , c-7 , Purchase , 10.50 , 2026-07-06T12:00:00Z\n"
    )

    normalized = lambda_function.normalize_record(rows[0])

    assert normalized["event_id"] == "e-1"
    assert normalized["customer_id"] == "c-7"
    assert normalized["event_type"] == "purchase"
    assert normalized["amount"] == "10.50"
    assert normalized["event_ts"] == "2026-07-06T12:00:00Z"
    assert "processed_at" in normalized


def test_records_to_jsonl():
    output = lambda_function.records_to_jsonl([{"event_id": "e-1"}, {"event_id": "e-2"}])

    lines = output.strip().splitlines()
    assert json.loads(lines[0]) == {"event_id": "e-1"}
    assert json.loads(lines[1]) == {"event_id": "e-2"}


def test_build_output_key_uses_partitioned_curated_prefix():
    key = lambda_function.build_output_key("raw/events/input.csv", "curated/events")

    assert key.startswith("curated/events/run_date=")
    assert key.endswith("/input.jsonl")

