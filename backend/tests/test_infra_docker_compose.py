from pathlib import Path


def test_local_compose_includes_celery_beat_service() -> None:
    compose_text = Path("infra/docker/docker-compose.yml").read_text(encoding="utf-8")

    assert "\n  beat:\n" in compose_text
    assert "celery -A app.workers.celery_app.celery_app beat --loglevel=info" in compose_text
    assert "migrator:" in compose_text
    assert "redis:" in compose_text
