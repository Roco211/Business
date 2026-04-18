import logging
import threading

from app.workers.v2_outbox_tasks import drain_v2_outbox

logger = logging.getLogger(__name__)


def _publish_v2_outbox_drain(
    *,
    tenant_id: str,
    shop_id: str,
    batch_limit: int = 50,
    max_batches: int = 10,
    retry_after_seconds: int | None = 60,
) -> bool:
    try:
        drain_v2_outbox.apply_async(
            args=(tenant_id, shop_id),
            kwargs={
                "batch_limit": batch_limit,
                "max_batches": max_batches,
                "retry_after_seconds": retry_after_seconds,
            },
            retry=False,
        )
    except Exception as exc:
        logger.warning(
            "Failed to enqueue V2 outbox drain for tenant=%s shop=%s: %s",
            tenant_id,
            shop_id,
            exc,
        )


def enqueue_v2_outbox_drain(
    *,
    tenant_id: str,
    shop_id: str,
    batch_limit: int = 50,
    max_batches: int = 10,
    retry_after_seconds: int | None = 60,
) -> bool:
    try:
        publish_thread = threading.Thread(
            target=_publish_v2_outbox_drain,
            kwargs={
                "tenant_id": tenant_id,
                "shop_id": shop_id,
                "batch_limit": batch_limit,
                "max_batches": max_batches,
                "retry_after_seconds": retry_after_seconds,
            },
            daemon=True,
            name="v2-outbox-enqueue",
        )
        publish_thread.start()
    except Exception as exc:
        logger.warning(
            "Failed to start V2 outbox enqueue thread for tenant=%s shop=%s: %s",
            tenant_id,
            shop_id,
            exc,
        )
        return False
    return True
