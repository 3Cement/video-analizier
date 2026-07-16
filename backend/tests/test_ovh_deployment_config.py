from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_compose_binds_caddy_through_configurable_host_ports():
    compose = (ROOT / "docker-compose.prod.yml").read_text()
    env_example = (ROOT / ".env.example").read_text()

    assert "${CADDY_HTTP_BIND:-0.0.0.0:80}:80" in compose
    assert "${CADDY_HTTPS_BIND:-0.0.0.0:443}:443" in compose
    assert "CADDY_HTTP_BIND=127.0.0.1:8082" in env_example
    assert "CADDY_HTTPS_BIND=127.0.0.1:8443" in env_example


def test_compose_runs_a_bounded_local_ollama_model():
    compose = (ROOT / "docker-compose.prod.yml").read_text()
    env_example = (ROOT / ".env.example").read_text()

    assert "ollama/ollama:latest" in compose
    assert 'command: ["pull", "${OLLAMA_MODEL:-qwen3:4b-instruct}"]' in compose
    assert "OLLAMA_BASE_URL: http://ollama:11434/v1" in compose
    assert 'JOB_MAX_WORKERS: "1"' in compose
    assert 'OLLAMA_CONTEXT_LENGTH: "8192"' in compose
    assert "mem_limit: 5g" in compose
    assert "LLM_PROVIDER=ollama" in env_example
    assert "OLLAMA_MODEL=qwen3:4b-instruct" in env_example


def test_ovh_nginx_routes_only_fallback_traffic_to_local_caddy():
    nginx = (ROOT / "deploy" / "nginx-video-analizier.conf").read_text()

    assert "listen 80 default_server;" in nginx
    assert "listen [::]:80 default_server;" in nginx
    assert "server_name _;" in nginx
    assert "proxy_pass http://127.0.0.1:8082;" in nginx
    assert "client_max_body_size 100m;" in nginx
    assert "api.investtracker.eu" not in nginx.split("server {")[1]
    assert "api.policzalne.pl" not in nginx.split("server {")[1]
