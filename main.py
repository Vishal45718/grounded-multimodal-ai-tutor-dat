"""CLI entry point for M1: ingest one lecture video into the versioned
evidence corpus.

    python main.py ingest --video lecture03.mp4 --title "Lecture 3: Hybrid Search" \\
        --course-edition Fall2026 --source-id cs5903-lec03

    python main.py deprecate --course-edition Fall2025
"""
import argparse

from ingestion.chunker import build_chunks
from ingestion.manifest import get_manifest_asset, get_manifest_source
from ingestion.ocr import ocr_keyframes
from ingestion.transcriber import transcribe
from ingestion.versioning import SourceVersion, file_content_hash
from ingestion.video_processor import extract_audio, extract_keyframes
from storage.corpus_store import deprecate_edition, init_db, insert_chunks, is_source_active, upsert_source


def ingest(args):
    init_db()

    asset_id = getattr(args, "asset_id", None)
    manifest_record = None
    if asset_id:
        manifest_record = get_manifest_asset(asset_id, manifest_path=getattr(args, "manifest", None))
        if not manifest_record:
            raise ValueError(f"Asset ID '{asset_id}' not found in manifest")

    source_id = getattr(args, "source_id", None) or (manifest_record.source_id if manifest_record else None)
    course_edition = getattr(args, "course_edition", None) or (manifest_record.edition_id if manifest_record else None)
    title = getattr(args, "title", None) or (manifest_record.title if manifest_record else None)
    source_url = manifest_record.source_url if manifest_record else None

    if not source_id or not course_edition or not title:
        raise ValueError("Missing required metadata: source_id, course_edition, or title. Specify them or pass --asset-id.")

    if not manifest_record:
        manifest_record = get_manifest_source(
            source_id,
            edition_id=course_edition,
            manifest_path=getattr(args, "manifest", None),
        )
        if manifest_record:
            asset_id = manifest_record.asset_id
            source_url = manifest_record.source_url

    content_hash = file_content_hash(args.video)
    if is_source_active(source_id, content_hash):
        print(f"[skip] {source_id} already indexed at hash {content_hash} -- nothing changed.")
        return

    print(f"[1/4] extracting audio from {args.video}")
    audio_path = extract_audio(args.video, source_id=source_id, content_hash=content_hash)

    print("[2/4] transcribing")
    transcript = transcribe(audio_path)

    print("[3/4] extracting + OCR'ing keyframes")
    keyframes = extract_keyframes(args.video, source_id=source_id, content_hash=content_hash)
    ocr_results = ocr_keyframes(keyframes)

    print("[4/4] building + storing evidence chunks")
    chunks = build_chunks(
        source_id,
        content_hash,
        transcript,
        ocr_results,
        asset_id=asset_id,
        source_url=source_url,
    )
    
    version = SourceVersion(
        source_id=source_id,
        content_hash=content_hash,
        course_edition=course_edition,
        title=title,
        asset_id=asset_id,
        source_url=source_url,
    )
    insert_chunks(chunks)
    upsert_source(version)

    n_audio = sum(1 for c in chunks if c.modality == "audio")
    n_visual = sum(1 for c in chunks if c.modality == "visual")
    print(f"done: {len(chunks)} chunks ({n_audio} audio, {n_visual} visual) for {source_id}")


def deprecate(args):
    init_db()
    deprecate_edition(args.course_edition)
    print(f"marked course edition '{args.course_edition}' as deprecated; its chunks are now stale.")


def resolve_citation(args):
    init_db()
    print(f"Resolving citation for chunk {args.chunk_id}...")
    # Basic skeleton for resolving citations directly
    pass

def ask_tutor(args):
    init_db()
    from retrieval.retriever import TutorRetriever
    from generation.answer import generate_grounded_answer
    
    print("Loading active chunks and building indices (M2)...")
    retriever = TutorRetriever(use_dense=True, use_sparse=True)
    
    print("Retrieving evidence and generating grounded answer (M3)...")
    answer, citations = generate_grounded_answer(args.query, retriever)

    print("\n--- Answer ---")
    print(answer)
    print("\n--- Citations ---")
    for c in citations:
        if c['citation_label'] in answer:
            print(f"{c['citation_label']}: Source {c['source_id']} @ {c['start_sec']}s - {c['end_sec']}s ({c['modality']})")

def main():
    parser = argparse.ArgumentParser(description="M1 evidence-corpus ingestion CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest one lecture video")
    p_ingest.add_argument("--video", required=False, help="Local video file path")
    p_ingest.add_argument("--use-official", action="store_true", help="Download and use official transcript/slides from manifest instead of ASR/OCR")
    p_ingest.add_argument("--source-id", default=None, help="stable logical id, e.g. cs50-lec00")
    p_ingest.add_argument("--title", default=None)
    p_ingest.add_argument("--course-edition", default=None)
    p_ingest.add_argument("--asset-id", default=None, help="Manifest asset ID (e.g. cs50-2024-w0)")
    p_ingest.add_argument("--manifest", default=None, help="Path to source manifest (defaults to CONFIG.manifest_path)")
    p_ingest.set_defaults(func=ingest)

    p_dep = sub.add_parser("deprecate", help="Deprecate a whole course edition")
    p_dep.add_argument("--course-edition", required=True)
    p_dep.set_defaults(func=deprecate)

    p_resolve = sub.add_parser("resolve-citation", help="Resolve an evidence chunk ID to an actionable citation")
    p_resolve.add_argument("--chunk-id", required=True)
    p_resolve.set_defaults(func=resolve_citation)

    p_query = sub.add_parser("query", help="Ask the tutor a question (M2 & M3)")
    p_query.add_argument("--query", required=True, help="Question to ask")
    p_query.set_defaults(func=ask_tutor)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
