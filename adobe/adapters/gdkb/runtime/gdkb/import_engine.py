import hashlib, json
from dataclasses import dataclass
from .normalize import normalize_name

@dataclass(frozen=True)
class ImportRecord:
    source_name: str
    external_id: str
    record_type: str
    payload: dict

def canonical_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def payload_hash(payload: dict) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()

def validate_record(record: ImportRecord) -> None:
    if not record.source_name.strip():
        raise ValueError("source_name is required")
    if not record.external_id.strip():
        raise ValueError("external_id is required")
    if not record.record_type.strip():
        raise ValueError("record_type is required")
    if not isinstance(record.payload, dict):
        raise TypeError("payload must be an object")

def normalize_record(record: ImportRecord) -> dict:
    validate_record(record)
    p=dict(record.payload)
    if "name" in p and isinstance(p["name"],str):
        p["normalized_name"]=normalize_name(p["name"])
    return {
        "source_name":record.source_name,
        "external_id":record.external_id,
        "record_type":record.record_type,
        "payload":p,
        "payload_hash":payload_hash(p)
    }

def import_records(records):
    out=[]
    for record in records:
        out.append(normalize_record(record))
    return out
