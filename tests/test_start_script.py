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
