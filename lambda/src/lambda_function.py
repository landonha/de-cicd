import csv
import io
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import unquote_plus


def parse_csv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def normalize_record(record: dict[str, str]) -> dict[str, Any]:
    normalized = {
        "event_id": clean_string(record.get("event_id")),
        "customer_id": clean_string(record.get("customer_id")),
        "event_type": clean_string(record.get("event_type")).lower(),
        "amount": parse_decimal(record.get("amount")),
        "event_ts": clean_string(record.get("event_ts")),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    return {key: value for key, value in normalized.items() if value not in ("", None)}


def clean_string(value: str | None) -> str:
    return (value or "").strip()


def parse_decimal(value: str | None) -> str | None:
    raw_value = clean_string(value)
    if raw_value == "":
        return None

    try:
        return str(Decimal(raw_value))
    except InvalidOperation:
        return None


def records_to_jsonl(records: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n"


def build_output_key(input_key: str, output_prefix: str) -> str:
    file_name = input_key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{output_prefix.rstrip('/')}/run_date={run_date}/{file_name}.jsonl"


def get_s3_client():
    import boto3

    return boto3.client("s3")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    s3 = get_s3_client()
    output_bucket = os.environ.get("OUTPUT_BUCKET")
    output_prefix = os.environ.get("OUTPUT_PREFIX", "curated/events")
    processed_files = []

    for item in event.get("Records", []):
        source_bucket = item["s3"]["bucket"]["name"]
        source_key = unquote_plus(item["s3"]["object"]["key"])
        target_bucket = output_bucket or source_bucket
        target_key = build_output_key(source_key, output_prefix)

        source_object = s3.get_object(Bucket=source_bucket, Key=source_key)
        csv_text = source_object["Body"].read().decode("utf-8")
        records = [normalize_record(record) for record in parse_csv(csv_text)]

        s3.put_object(
            Bucket=target_bucket,
            Key=target_key,
            Body=records_to_jsonl(records).encode("utf-8"),
            ContentType="application/x-ndjson",
        )

        processed_files.append(
            {
                "source": f"s3://{source_bucket}/{source_key}",
                "target": f"s3://{target_bucket}/{target_key}",
                "record_count": len(records),
            }
        )

    return {"processed_files": processed_files}

