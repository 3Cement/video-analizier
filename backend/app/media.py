from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional


def probe_duration_seconds(path: Path) -> Optional[float]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout or "{}")
        duration = (data.get("format") or {}).get("duration")
        return float(duration) if duration is not None else None
    except Exception:
        return None
