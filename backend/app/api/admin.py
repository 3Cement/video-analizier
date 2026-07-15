from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.db import get_db
from app.models import Source
from app.schemas import QueueStatsOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_api_key)])


@router.get("/queue", response_model=QueueStatsOut)
def queue_stats(db: Session = Depends(get_db)) -> QueueStatsOut:
    rows = db.execute(select(Source.status, func.count()).group_by(Source.status)).all()
    counts = {status: int(count) for status, count in rows}
    now = datetime.now(timezone.utc)
    retry_scheduled = db.scalar(
        select(func.count())
        .select_from(Source)
        .where(Source.status == "pending", Source.next_run_at.is_not(None), Source.next_run_at > now)
    ) or 0
    oldest = db.scalar(
        select(Source).where(Source.status == "pending").order_by(Source.id.asc()).limit(1)
    )
    age = None
    oldest_id = None
    if oldest is not None:
        oldest_id = oldest.id
        created = oldest.created_at
        if created is not None:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = max(0.0, (now - created).total_seconds())
    return QueueStatsOut(
        pending=counts.get("pending", 0),
        downloading=counts.get("downloading", 0),
        transcribing=counts.get("transcribing", 0),
        summarizing=counts.get("summarizing", 0),
        ready=counts.get("ready", 0),
        failed=counts.get("failed", 0),
        retry_scheduled=int(retry_scheduled),
        oldest_pending_id=oldest_id,
        oldest_pending_age_seconds=age,
    )
