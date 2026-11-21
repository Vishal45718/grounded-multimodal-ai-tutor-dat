"""CLI entry point for Grounded Multimodal AI Tutor (M1 - M8).

Supports:
- Ingestion of lecture videos and official assets into evidence corpus (M1).
- Version deprecation and chunk citation resolution (M1).
- Grounded query answering with multimodal evidence and pedagogical styling (M2, M3, M4, M5).
- Learner memory management: list, write, correct, delete, purge (M5).
- Automated evaluation and adversarial red team harness (M7).
- Performance characterization across retrieval architectures (M8).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

from config import CONFIG
from ingestion.chunker import build_chunks
from ingestion.manifest import get_manifest_asset, get_manifest_source
from ingestion.ocr import ocr_keyframes
from ingestion.transcriber import transcribe
from ingestion.versioning import SourceVersion, file_content_hash
from ingestion.video_processor import extract_audio, extract_keyframes
from storage.corpus_store import deprecate_edition, init_db, insert_chunks, is_source_active, upsert_source


_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_CASES_PATH = str(_PROJECT_ROOT / "benchmark" / "cases_60.jsonl")
_DEFAULT_EVAL_OUTPUT = str(_PROJECT_ROOT / "benchmark" / "results" / "evaluation_report.json")
_DEFAULT_PERF_OUTPUT = str(_PROJECT_ROOT / "benchmark" / "results" / "performance_characterization.json")


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
    # Ensure database schema is initialized before resolving
    init_db()
    from scripts.ingest_official import resolve_citation as _resolve
    _resolve(args.chunk_id)


def ask_tutor(args):
    init_db()
    from retrieval.retriever import TutorRetriever
    from generation.answer import generate_grounded_answer
    from memory.store import LearnerMemoryStore

    rerank_enabled = bool(getattr(args, "rerank", False))
    require_vis = bool(getattr(args, "require_visual", False))
    learner_id = getattr(args, "learner_id", None)
    no_cache = bool(getattr(args, "no_cache", False))

    print(f"Loading active chunks and building indices (M2, rerank={rerank_enabled})...")
    retriever = TutorRetriever(use_dense=True, use_sparse=True, use_reranker=rerank_enabled)

    # Optional persistent memory store wiring for pedagogical context
    memory_store = None
    if learner_id:
        db_path = getattr(args, "db", None) or CONFIG.memory_db_path
        memory_store = LearnerMemoryStore(db_path=db_path)

    print("Retrieving evidence and generating grounded answer (M3)...")
    answer, citations = generate_grounded_answer(
        args.query,
        retriever,
        require_visual=require_vis,
        use_cache=not no_cache,
        learner_id=learner_id,
        memory_store=memory_store,
    )

    if memory_store is not None:
        memory_store.close()

    print("\n--- Answer ---")
    print(answer)
    print("\n--- Citations ---")
    for c in citations:
        if c.get("citation_label", "") in answer:
            time_str = (
                f"{c['start_sec']}s - {c['end_sec']}s"
                if c.get("start_sec") is not None
                else f"Slide Page {c.get('page_number', 'N/A')}"
            )
            print(f"{c['citation_label']}: Source {c['source_id']} @ {time_str} ({c['modality']})")


def manage_memory(args):
    from memory.models import MemoryEntry, _normalize_memory_type, compute_memory_id
    from memory.store import LearnerMemoryStore

    db_path = getattr(args, "db", None) or CONFIG.memory_db_path
    store = LearnerMemoryStore(db_path=db_path)
    action = args.action.lower()

    try:
        if action == "list":
            if not args.learner_id:
                print("Error: --learner-id is required to list memories.")
                return
            mems = store.get_memories(args.learner_id)
            print(f"\nActive memories for learner '{args.learner_id}' ({len(mems)}):")
            for m in mems:
                m_type = m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type)
                print(f"  [{m.memory_id}] Type: {m_type} | Topic: {m.topic} | Conf: {m.confidence:.2f}")
                print(f"    Content: {m.content}")

        elif action == "write":
            if not args.learner_id or not args.topic or not args.content:
                print("Error: --learner-id, --topic, and --content are required to write memory.")
                return

            raw_type = getattr(args, "type", "goal") or "goal"
            norm_type = _normalize_memory_type(raw_type)

            mem_id = getattr(args, "item_id", None) or compute_memory_id(
                args.learner_id, norm_type, args.topic, args.content
            )

            entry = MemoryEntry(
                memory_id=mem_id,
                learner_id=args.learner_id,
                memory_type=norm_type,
                topic=args.topic,
                content=args.content,
                confidence=float(getattr(args, "confidence", 1.0) or 1.0),
                source={"cli_provenance": f"cli_{int(time.time())}"},
            )
            stored = store.add_memory(entry)
            print(f"Write memory: Successfully committed to durable memory. (ID: {stored.memory_id})")

        elif action == "correct":
            if not args.item_id or not args.content:
                print("Error: --item-id and --content are required to correct memory.")
                return
            updated = store.correct_memory(
                args.item_id, args.content, reason=getattr(args, "reason", "Learner correction")
            )
            if updated:
                rev_count = len(getattr(updated, "history", []))
                print(f"Corrected memory [{args.item_id}]: New content: '{updated.content}' (Revisions: {rev_count})")
            else:
                print(f"Error: Memory item [{args.item_id}] not found.")

        elif action == "delete":
            if not args.item_id:
                print("Error: --item-id is required to delete memory.")
                return
            # Delete by ID (matches legacy and store interfaces)
            success = store.delete_memory(getattr(args, "learner_id", "") or "", args.item_id)
            if not success:
                # Fallback to direct ID match if learner_id not specified
                with store._connect() as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM memory_entries WHERE memory_id = ?", (args.item_id,))
                    success = cur.rowcount > 0
            if success:
                print(f"Deleted memory [{args.item_id}] immediately.")
            else:
                print(f"Error: Memory item [{args.item_id}] not found.")

        elif action == "purge":
            if not args.learner_id:
                print("Error: --learner-id is required to purge learner.")
                return
            count = store.purge_learner(args.learner_id)
            print(f"Purged all {count} memory records for learner '{args.learner_id}'.")
    finally:
        store.close()


def run_eval_cli(args):
    from benchmark.run_eval import print_scorecard, run_benchmark

    cases_path = getattr(args, "cases", None) or _DEFAULT_CASES_PATH
    output_path = getattr(args, "output", None) or _DEFAULT_EVAL_OUTPUT

    results = run_benchmark(
        cases_path=cases_path,
        mode=args.mode,
        output_path=output_path,
        top_k=args.top_k,
        use_reranker=args.rerank,
    )
    print_scorecard(results)


def run_characterization_cli(args):
    from benchmark.characterize_performance import run_characterization

    cases_path = getattr(args, "cases", None) or _DEFAULT_CASES_PATH
    output_path = getattr(args, "output", None) or _DEFAULT_PERF_OUTPUT

    run_characterization(
        cases_path=cases_path,
        output_path=output_path,
        top_k=args.top_k,
    )


def main():
    parser = argparse.ArgumentParser(description="Grounded Multimodal AI Tutor CLI (M1 - M8)")
    sub = parser.add_subparsers(dest="command", required=True)

    # 1. Ingest
    p_ingest = sub.add_parser("ingest", help="Ingest one lecture video")
    p_ingest.add_argument("--video", required=False, help="Local video file path")
    p_ingest.add_argument("--use-official", action="store_true", help="Download and use official transcript/slides from manifest instead of ASR/OCR")
    p_ingest.add_argument("--source-id", default=None, help="stable logical id, e.g. cs50-lec00")
    p_ingest.add_argument("--title", default=None)
    p_ingest.add_argument("--course-edition", default=None)
    p_ingest.add_argument("--asset-id", default=None, help="Manifest asset ID (e.g. cs50-2024-w0)")
    p_ingest.add_argument("--manifest", default=None, help="Path to source manifest (defaults to CONFIG.manifest_path)")
    p_ingest.set_defaults(func=ingest)

    # 2. Deprecate
    p_dep = sub.add_parser("deprecate", help="Deprecate a whole course edition")
    p_dep.add_argument("--course-edition", required=True)
    p_dep.set_defaults(func=deprecate)

    # 3. Resolve Citation
    p_resolve = sub.add_parser("resolve-citation", help="Resolve an evidence chunk ID to an actionable citation")
    p_resolve.add_argument("--chunk-id", required=True)
    p_resolve.set_defaults(func=resolve_citation)

    # 4. Query
    p_query = sub.add_parser("query", help="Ask the tutor a question (M2 & M3)")
    p_query.add_argument("--query", required=True, help="Question to ask")
    p_query.add_argument("--learner-id", default=None, help="Learner ID for isolated pedagogical styling (M5)")
    p_query.add_argument("--require-visual", action="store_true", help="Explicitly require visual evidence (M4)")
    p_query.add_argument("--rerank", action="store_true", help="Apply neural/lexical reranking layer (M8)")
    p_query.add_argument("--no-cache", action="store_true", help="Bypass response cache")
    p_query.add_argument("--db", default=None, help="Path to learner memory DB override")
    p_query.set_defaults(func=ask_tutor)

    # 5. Memory
    p_mem = sub.add_parser("memory", help="Inspect, correct, or delete learner memory (M5)")
    p_mem.add_argument("--action", required=True, choices=["list", "write", "correct", "delete", "purge"])
    p_mem.add_argument("--learner-id", default=None, help="Learner ID")
    p_mem.add_argument("--item-id", default=None, help="Memory Item ID")
    p_mem.add_argument("--type", default="goal", choices=["goal", "mastery", "misconception", "preference"])
    p_mem.add_argument("--topic", default=None, help="Memory topic")
    p_mem.add_argument("--content", default=None, help="Memory content")
    p_mem.add_argument("--confidence", type=float, default=1.0)
    p_mem.add_argument("--reason", default="Learner correction")
    p_mem.add_argument("--db", default=None, help="Path to learner memory DB override")
    p_mem.set_defaults(func=manage_memory)

    # 6. Eval
    p_eval = sub.add_parser("eval", help="Run automated evaluation and adversarial red team harness (M7)")
    p_eval.add_argument("--cases", default=_DEFAULT_CASES_PATH, help="Benchmark cases file")
    p_eval.add_argument("--mode", default="mock", choices=["mock", "live"], help="Execution mode")
    p_eval.add_argument("--output", default=_DEFAULT_EVAL_OUTPUT, help="Output report path")
    p_eval.add_argument("--top-k", type=int, default=5, help="Retrieval depth")
    p_eval.add_argument("--rerank", action="store_true", help="Enable reranker")
    p_eval.set_defaults(func=run_eval_cli)

    # 7. Characterize
    p_char = sub.add_parser("characterize", help="Run performance characterization across configurations (M8)")
    p_char.add_argument("--cases", default=_DEFAULT_CASES_PATH, help="Benchmark cases file")
    p_char.add_argument("--output", default=_DEFAULT_PERF_OUTPUT, help="Output path")
    p_char.add_argument("--top-k", type=int, default=5, help="Retrieval depth")
    p_char.set_defaults(func=run_characterization_cli)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
