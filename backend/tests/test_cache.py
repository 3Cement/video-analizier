from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.cache import clone_source_from_cache, extract_youtube_video_id
from app.models import Segment, Source, Summary


def test_extract_youtube_video_id():
    url = "https://www.youtube.com/watch?v=tPsVjYR0tGY"
    assert extract_youtube_video_id(url) == "tPsVjYR0tGY"


def test_clone_source_from_cache(db_session):
    cached = Source(
        source_type="youtube",
        title="Cached",
        video_id="abc123",
        status="ready",
        transcript_method="captions",
    )
    db_session.add(cached)
    db_session.flush()
    db_session.add(Segment(source_id=cached.id, start=0.0, end=1.0, text="Hello", ord=0))
    db_session.add(Summary(source_id=cached.id, kind="briefing", content="Brief"))
    db_session.commit()

    target = Source(source_type="youtube", title="New", url="https://youtu.be/abc123", status="pending")
    db_session.add(target)
    db_session.commit()

    clone_source_from_cache(db_session, target, cached)
    db_session.commit()

    target = db_session.scalar(
        select(Source)
        .where(Source.id == target.id)
        .options(selectinload(Source.segments), selectinload(Source.summaries))
    )
    assert target is not None

    assert target.status == "ready"
    assert target.title == "Cached"
    assert len(target.segments) == 1
    assert target.summaries[0].content == "Brief"
