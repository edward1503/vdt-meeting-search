from __future__ import annotations

from pathlib import Path


def test_start_script_builds_compose_services_only_when_containers_are_missing() -> None:
    script = Path("start.sh").read_text(encoding="utf-8")

    assert 'COMPOSE_SERVICES="elasticsearch redis api frontend"' in script
    assert "missing_compose_services()" in script
    assert "docker compose ps --all --services" in script
    assert 'if [ -n "$missing_services" ]; then' in script
    assert 'docker compose up -d --build $COMPOSE_SERVICES' in script
    assert 'docker compose up -d $COMPOSE_SERVICES' in script
    assert "docker compose up -d --build elasticsearch redis api frontend" not in script


def test_start_script_falls_back_to_cpu_when_cuda_warmup_fails() -> None:
    script = Path("start.sh").read_text(encoding="utf-8")

    assert "start_embedding_service()" in script
    assert "warm_models_or_fallback()" in script
    assert 'if ! warm_embedding_model "" 384 "what connects alpha and beta"; then' in script
    assert "embedding warmup failed for" in script
    assert "Ignoring stale embedding PID file" in script
    assert 'Retrying embedding service on CPU' in script
    assert 'EMBEDDING_DEVICE="cpu"' in script


def test_frontend_host_port_can_be_overridden_when_default_port_is_busy() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    script = Path("start.sh").read_text(encoding="utf-8")

    assert '"${FRONTEND_PORT:-3001}:3001"' in compose
    assert "choose_frontend_port()" in script
    assert "export FRONTEND_PORT" in script
    assert "Frontend: $FRONTEND_URL" in script
