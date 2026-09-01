import json
from pathlib import Path
from .import_engine import ImportRecord, import_records

def load_jsonl(path):
    records=[]
    with open(path,encoding="utf-8") as f:
        for line_no,line in enumerate(f,1):
            if not line.strip():
                continue
            try:
                row=json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON") from exc
            records.append(ImportRecord(
                source_name=row["source_name"],
                external_id=row["external_id"],
                record_type=row.get("record_type","entity"),
                payload=row["payload"]
            ))
    return import_records(records)
