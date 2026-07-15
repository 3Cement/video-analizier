from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_optional_user_id, verify_api_key
from app.db import get_db
from app.models import Collection, Note, Segment, Source, Summary, Tag
from app.schemas import (
    CollectionCreateRequest,
    CollectionOut,
    NoteCreateRequest,
    NoteOut,
    SearchHit,
    SearchResponse,
    TagAssignRequest,
    TagOut,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/search", response_model=SearchResponse)
def search_library(
    q: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_optional_user_id),
    limit: int = 30,
) -> SearchResponse:
    query = (q or "").strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Query too short")
    like = f"%{query}%"
    hits: list[SearchHit] = []

    sources = db.scalars(
        select(Source)
        .where(Source.user_id == user_id, Source.title.ilike(like))
        .order_by(Source.updated_at.desc())
        .limit(limit)
    ).all()
    for source in sources:
        hits.append(
            SearchHit(
                source_id=source.id,
                title=source.title,
                source_type=source.source_type,
                snippet=source.title,
                match_kind="title",
            )
        )

    if len(hits) < limit:
        segs = db.execute(
            select(Segment, Source)
            .join(Source, Source.id == Segment.source_id)
            .where(Source.user_id == user_id, Segment.text.ilike(like))
            .limit(limit)
        ).all()
        seen = {h.source_id for h in hits}
        for segment, source in segs:
            if source.id in seen:
                continue
            snippet = segment.text[:220]
            hits.append(
                SearchHit(
                    source_id=source.id,
                    title=source.title,
                    source_type=source.source_type,
                    snippet=snippet,
                    match_kind="transcript",
                )
            )
            seen.add(source.id)
            if len(hits) >= limit:
                break

    if len(hits) < limit:
        summaries = db.execute(
            select(Summary, Source)
            .join(Source, Source.id == Summary.source_id)
            .where(Source.user_id == user_id, Summary.content.ilike(like))
            .limit(limit)
        ).all()
        seen = {h.source_id for h in hits}
        for summary, source in summaries:
            if source.id in seen:
                continue
            hits.append(
                SearchHit(
                    source_id=source.id,
                    title=source.title,
                    source_type=source.source_type,
                    snippet=summary.content[:220],
                    match_kind="summary",
                )
            )
            seen.add(source.id)
            if len(hits) >= limit:
                break

    return SearchResponse(query=query, hits=hits[:limit])


@router.get("/collections", response_model=list[CollectionOut])
def list_collections(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_optional_user_id),
) -> list[CollectionOut]:
    rows = db.scalars(
        select(Collection)
        .where(Collection.user_id == user_id)
        .options(selectinload(Collection.sources))
        .order_by(Collection.created_at.desc())
    ).all()
    return [
        CollectionOut(id=c.id, name=c.name, source_ids=[s.id for s in c.sources])
        for c in rows
    ]


@router.post("/collections", response_model=CollectionOut)
def create_collection(
    payload: CollectionCreateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_optional_user_id),
) -> CollectionOut:
    collection = Collection(user_id=user_id, name=payload.name.strip())
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return CollectionOut(id=collection.id, name=collection.name, source_ids=[])


@router.post("/collections/{collection_id}/sources/{source_id}", response_model=CollectionOut)
def add_source_to_collection(
    collection_id: int,
    source_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_optional_user_id),
) -> CollectionOut:
    collection = db.scalar(
        select(Collection)
        .where(Collection.id == collection_id, Collection.user_id == user_id)
        .options(selectinload(Collection.sources))
    )
    source = db.scalar(select(Source).where(Source.id == source_id, Source.user_id == user_id))
    if collection is None or source is None:
        raise HTTPException(status_code=404, detail="Collection or source not found")
    if source not in collection.sources:
        collection.sources.append(source)
        db.commit()
        db.refresh(collection)
    return CollectionOut(id=collection.id, name=collection.name, source_ids=[s.id for s in collection.sources])


@router.get("/tags", response_model=list[TagOut])
def list_tags(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_optional_user_id),
) -> list[TagOut]:
    tags = db.scalars(select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)).all()
    return [TagOut.model_validate(tag) for tag in tags]


@router.post("/sources/{source_id}/tags", response_model=list[TagOut])
def assign_tag(
    source_id: int,
    payload: TagAssignRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_optional_user_id),
) -> list[TagOut]:
    source = db.scalar(
        select(Source)
        .where(Source.id == source_id, Source.user_id == user_id)
        .options(selectinload(Source.tags))
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    name = payload.name.strip().lower()
    tag = db.scalar(select(Tag).where(Tag.user_id == user_id, Tag.name == name))
    if tag is None:
        tag = Tag(user_id=user_id, name=name)
        db.add(tag)
        db.flush()
    if tag not in source.tags:
        source.tags.append(tag)
    db.commit()
    db.refresh(source)
    return [TagOut.model_validate(t) for t in source.tags]


@router.get("/sources/{source_id}/notes", response_model=list[NoteOut])
def list_notes(
    source_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_optional_user_id),
) -> list[NoteOut]:
    source = db.scalar(select(Source).where(Source.id == source_id, Source.user_id == user_id))
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    notes = db.scalars(
        select(Note).where(Note.source_id == source_id, Note.user_id == user_id).order_by(Note.created_at.desc())
    ).all()
    return [NoteOut.model_validate(n) for n in notes]


@router.post("/sources/{source_id}/notes", response_model=NoteOut)
def create_note(
    source_id: int,
    payload: NoteCreateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_optional_user_id),
) -> NoteOut:
    source = db.scalar(select(Source).where(Source.id == source_id, Source.user_id == user_id))
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    note = Note(user_id=user_id, source_id=source_id, body=payload.body.strip())
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteOut.model_validate(note)
