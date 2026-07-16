import json
from pathlib import Path


def test_vercel_rewrites_every_path_to_vps_without_cache():
    config = json.loads((Path(__file__).parents[2] / "vercel.json").read_text())

    assert config["rewrites"] == [
        {"source": "/:path*", "destination": "http://IP_VPS/:path*"}
    ]
    assert config["headers"] == [
        {
            "source": "/(.*)",
            "headers": [
                {"key": "Cache-Control", "value": "private, no-store, max-age=0"}
            ],
        }
    ]
