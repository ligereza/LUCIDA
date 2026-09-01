import re
import unicodedata

def normalize_name(value: str) -> str:
    """Deterministic comparison form; never use this to overwrite the original."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    value = re.sub(r"[^0-9a-zA-ZÀ-ÿ\u00a0-\uFFFF]+", " ", value)
    return " ".join(value.split())
