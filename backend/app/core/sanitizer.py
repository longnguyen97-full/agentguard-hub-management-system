import unicodedata
from typing import Any, Dict, List, Union
import ftfy


def sanitize_text(text: Union[str, Any]) -> Union[str, Any]:
    """
    Automatically detects, unescapes, and repairs broken encoding (mojibake)
    and normalizes Unicode (NFC) for Vietnamese and international characters.
    """
    if not isinstance(text, str):
        return text

    if not text:
        return text

    try:
        # 1. Use ftfy to fix mojibake (e.g. latin1/cp1252 misinterpreted as utf-8)
        fixed = ftfy.fix_text(text)

        # 2. Normalize unicode composed characters (NFC form standard)
        normalized = unicodedata.normalize("NFC", fixed)

        # 3. Handle double-escaped unicode sequences like \u00e0 or \u1ebd
        if "\\u" in normalized:
            try:
                normalized = normalized.encode("utf-8").decode("unicode_escape")
            except Exception:
                pass

        return normalized
    except Exception:
        return text


def sanitize_payload(obj: Any) -> Any:
    """Recursively cleans all strings in dictionaries and lists."""
    if isinstance(obj, str):
        return sanitize_text(obj)
    elif isinstance(obj, dict):
        return {k: sanitize_payload(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_payload(elem) for elem in obj]
    return obj

