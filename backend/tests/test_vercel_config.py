import json
from pathlib import Path


def test_vercel_rewrites_every_path_to_vps_without_cache():
    config = json.loads((Path(__file__).parents[2] / "vercel.json").read_text())

    assert config["rewrites"] == [
        {"source": "/:path*", "destination": "http://57.131.51.89/:path*"}
    ]
    assert config["headers"] == [
        {
            "source": "/(.*)",
            "headers": [
                {"key": "Cache-Control", "value": "private, no-store, max-age=0"},
                {"key": "x-vercel-enable-rewrite-caching", "value": "0"},
            ],
        }
    ]
