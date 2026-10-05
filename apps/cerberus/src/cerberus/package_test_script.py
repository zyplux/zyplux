from __future__ import annotations

import json


def parse_test_script(content: str) -> str:
    try:
        manifest = json.loads(content)
    except json.JSONDecodeError:
        return ""
    scripts = manifest.get("scripts") if isinstance(manifest, dict) else None
    script = scripts.get("test") if isinstance(scripts, dict) else None
    return script if isinstance(script, str) else ""
