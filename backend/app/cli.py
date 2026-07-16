from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.chunking import segments_to_transcript
from app.config import get_settings
from app.db import get_session, init_db
from app.llm.client import has_llm_credentials
from app.llm.qa import answer_question
from app.llm.summarize import summarize_segments
from app.llm_settings_store import apply_llm_overrides
from app.models import Source, Summary, User
from app.pipeline import process_youtube_source
from app.security import hash_password, new_api_token


def cmd_provision_user(args: argparse.Namespace) -> int:
    settings = get_settings()
    email = (args.email or settings.single_user_email).strip().lower()
    if not email:
        raise SystemExit("Email is required via --email or SINGLE_USER_EMAIL")
    configured_email = settings.single_user_email.strip().lower()
    if configured_email and email != configured_email:
        raise SystemExit("Email must match SINGLE_USER_EMAIL")

    password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("Password: ")
    if len(password) < 8:
        raise SystemExit("Password must contain at least 8 characters")

    init_db()
    db = get_session()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, password_hash="", token=new_api_token())
            db.add(user)
        user.password_hash = hash_password(password)
        user.token = new_api_token()
        user.is_active = True
        user.email_verified_at = datetime.now(timezone.utc)
        user.verification_token_hash = None
        user.verification_token_expires = None
        user.reset_token = None
        user.reset_token_expires = None
        db.commit()
        print(f"Provisioned verified user: {email}")
        return 0
    finally:
        db.close()


def cmd_analyze(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    init_db()
    db = get_session()
    try:
        source = Source(
            source_type="youtube",
            title="YouTube video",
            url=args.url,
            language=args.language,
            status="pending",
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        print(f"Created source id={source.id}", flush=True)
        process_youtube_source(db, source.id, auto_summarize=False)
        db.refresh(source)
        if source.status == "failed":
            raise RuntimeError(source.error or "Processing failed")
        segments = [(s.start, s.end, s.text) for s in source.segments]
        transcript = segments_to_transcript(segments)

        summary_text = ""
        if args.summarize:
            llm_settings = apply_llm_overrides(settings)
            if not has_llm_credentials(llm_settings):
                print("LLM key missing; using extractive summary fallback", file=sys.stderr)
            summary_text = summarize_segments(segments, title=source.title, kind="briefing")
            db.add(Summary(source_id=source.id, kind="briefing", content=summary_text))
            db.commit()

        answer_text = ""
        citations = []
        if args.ask:
            llm_settings = apply_llm_overrides(settings)
            if not has_llm_credentials(llm_settings):
                print("LLM key missing; using extractive Q&A fallback", file=sys.stderr)
            answer_text, citations = answer_question(args.ask, segments, title=source.title)

        out = {
            "source_id": source.id,
            "title": source.title,
            "url": source.url,
            "transcript_method": source.transcript_method,
            "duration_seconds": source.duration_seconds,
            "segment_count": len(segments),
            "transcript_preview": "\n".join(transcript.splitlines()[:40]),
            "summary": summary_text,
            "answer": answer_text,
            "citations": [c.model_dump() for c in citations],
        }

        if args.output:
            Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(json.dumps(out, ensure_ascii=False, indent=2))

        if args.save_transcript:
            Path(args.save_transcript).write_text(transcript + "\n", encoding="utf-8")
            print(f"Wrote transcript {args.save_transcript}")
        return 0
    finally:
        db.close()


def cmd_list_subs(args: argparse.Namespace) -> int:
    from app.ingest.youtube import list_subs

    info = list_subs(args.url)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_analyze_audio(args: argparse.Namespace) -> int:
    from app.asr.whisper import transcribe_audio
    from app.chunking import segments_to_transcript
    from app.llm.qa import answer_question
    from app.llm.summarize import summarize_segments

    settings = get_settings()
    settings.ensure_dirs()
    audio_path = Path(args.audio)
    if not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")

    print(f"Transcribing {audio_path} with Whisper ({settings.whisper_model})...", flush=True)
    asr = transcribe_audio(audio_path, language=args.language, settings=settings)
    segments = [(s.start, s.end, s.text) for s in asr]
    transcript = segments_to_transcript(segments)
    summary = summarize_segments(segments, title=args.title, kind="briefing", settings=settings) if args.summarize else ""
    answer = ""
    citations = []
    if args.ask:
        answer, citations = answer_question(args.ask, segments, title=args.title, settings=settings)

    out = {
        "title": args.title,
        "audio": str(audio_path),
        "transcript_method": "whisper",
        "segment_count": len(segments),
        "transcript": transcript,
        "summary": summary,
        "answer": answer,
        "citations": [c.model_dump() for c in citations],
        "note": (
            "Pilot audio path used when YouTube download is blocked by bot-check. "
            "For real YouTube videos set YTDLP_COOKIES to a Netscape cookies.txt export."
        ),
    }
    if args.output:
        Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.save_transcript:
        Path(args.save_transcript).write_text(transcript + "\n", encoding="utf-8")
        print(f"Wrote transcript {args.save_transcript}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="video-analizier")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze a YouTube URL end-to-end")
    analyze.add_argument("url")
    analyze.add_argument("--language", default="pl")
    analyze.add_argument("--summarize", action="store_true")
    analyze.add_argument("--ask", default="")
    analyze.add_argument("--output", default="")
    analyze.add_argument("--save-transcript", default="")
    analyze.set_defaults(func=cmd_analyze)

    audio = sub.add_parser("analyze-audio", help="Analyze a local audio file (ASR + summary)")
    audio.add_argument("audio")
    audio.add_argument("--title", default="Pilot audio")
    audio.add_argument("--language", default="pl")
    audio.add_argument("--summarize", action="store_true")
    audio.add_argument("--ask", default="")
    audio.add_argument("--output", default="")
    audio.add_argument("--save-transcript", default="")
    audio.set_defaults(func=cmd_analyze_audio)

    subs = sub.add_parser("list-subs", help="List available YouTube captions")
    subs.add_argument("url")
    subs.set_defaults(func=cmd_list_subs)

    provision = sub.add_parser("provision-user", help="Create or reset the single verified user")
    provision.add_argument("--email", default="", help="Defaults to SINGLE_USER_EMAIL")
    provision.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read one password line from stdin instead of prompting",
    )
    provision.set_defaults(func=cmd_provision_user)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
