import json
import hashlib
from pathlib import Path
from typing import Any, Optional


def _key(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def cache_get_json(cache_dir: str, key_str: str) -> Optional[dict]:
    p = Path(cache_dir) / f"{_key(key_str)}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def cache_set_json(cache_dir: str, key_str: str, data: Any) -> str:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    p = Path(cache_dir) / f"{_key(key_str)}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)
