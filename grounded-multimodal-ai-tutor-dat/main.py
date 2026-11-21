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

    if getattr(args, "use_official", False):
        from scripts.ingest_official import ingest_official
        return ingest_official(args)

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
    from scripts.ingest_official import resolve_citation as _resolve
    _resolve(args.chunk_id)

def ask_tutor(args):
    init_db()
    from retrieval.retriever import TutorRetriever
    from generation.answer import generate_grounded_answer
    
    use_rerank = getattr(args, "rerank", False)
    require_vis = getattr(args, "require_visual", False)
    print(f"Loading active chunks and building indices (M2, rerank={use_rerank})...")
    retriever = TutorRetriever(use_dense=True, use_sparse=True, use_reranker=use_rerank)
    
    print("Retrieving evidence and generating grounded answer (M3, M4, M6)...")
    answer, citations = generate_grounded_answer(
        args.query,
        retriever,
        require_visual=require_vis,
        use_cache=not getattr(args, "no_cache", False),
    )

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


def run_eval_cli(args):
    from benchmark.run_eval import run_benchmark, print_scorecard
    results = run_benchmark(
        cases_path=args.cases,
        mode=args.mode,
        output_path=args.output,
        top_k=args.top_k,
        use_reranker=args.rerank,
    )
    print_scorecard(results)


def run_characterization_cli(args):
    from benchmark.characterize_performance import run_characterization
    run_characterization(
        cases_path=args.cases,
        output_path=args.output,
        top_k=args.top_k,
    )


def manage_memory(args):
    from memory.store import LearnerMemoryStore
    from memory.models import LearnerMemoryItem
    from config import CONFIG
    import time
    
    store = LearnerMemoryStore(db_path=CONFIG.memory_db_path)
    action = args.action.lower()

    if action == "list":
        if not args.learner_id:
            print("Error: --learner-id is required to list memories.")
            return
        mems = store.get_active_memories(args.learner_id)
        print(f"\nActive memories for learner '{args.learner_id}' ({len(mems)}):")
        for m in mems:
            print(f"  [{m.item_id}] Type: {m.memory_type} | Topic: {m.topic} | Conf: {m.confidence:.2f}")
            print(f"    Content: {m.content}")
            if m.history:
                print(f"    History: {len(m.history)} revisions")

    elif action == "write":
        if not args.learner_id or not args.topic or not args.content:
            print("Error: --learner-id, --topic, and --content are required to write memory.")
            return
        item = LearnerMemoryItem(
            item_id=f"mem_{int(time.time()*1000)}",
            learner_id=args.learner_id,
            memory_type=getattr(args, "type", "goal") or "goal",
            topic=args.topic,
            content=args.content,
            confidence=float(getattr(args, "confidence", 1.0) or 1.0),
            is_confirmed=True,
            status="active",
            provenance_turn_id=f"cli_{int(time.time())}",
            created_at=time.time(),
            updated_at=time.time(),
        )
        success, committed, msg = store.write_memory(item, force=True)
        print(f"Write memory: {msg} (ID: {committed.item_id if committed else 'N/A'})")

    elif action == "correct":
        if not args.item_id or not args.content:
            print("Error: --item-id and --content are required to correct memory.")
            return
        updated = store.correct_memory(args.item_id, args.content, reason=getattr(args, "reason", "Learner correction"))
        if updated:
            print(f"Corrected memory [{args.item_id}]: New content: '{updated.content}' (Revisions: {len(updated.history)})")
        else:
            print(f"Error: Memory item [{args.item_id}] not found.")

    elif action == "delete":
        if not args.item_id:
            print("Error: --item-id is required to delete memory.")
            return
        success = store.delete_memory(args.item_id)
        if success:
            print(f"Deleted memory [{args.item_id}] immediately (status='deleted').")
        else:
            print(f"Error: Memory item [{args.item_id}] not found.")

    elif action == "purge":
        if not args.learner_id:
            print("Error: --learner-id is required to purge learner.")
            return
        count = store.purge_learner(args.learner_id)
        print(f"Purged all {count} memory records for learner '{args.learner_id}'.")


def main():
    parser = argparse.ArgumentParser(description="Grounded Multimodal AI Tutor CLI (M1 - M8)")
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
    p_query.add_argument("--require-visual", action="store_true", help="Explicitly require visual evidence (M4)")
    p_query.add_argument("--rerank", action="store_true", help="Apply neural/lexical reranking layer (M8)")
    p_query.add_argument("--no-cache", action="store_true", help="Bypass response cache")
    p_query.set_defaults(func=ask_tutor)

    p_mem = sub.add_parser("memory", help="Inspect, correct, or delete learner memory (M5)")
    p_mem.add_argument("--action", required=True, choices=["list", "write", "correct", "delete", "purge"])
    p_mem.add_argument("--learner-id", default=None, help="Learner ID")
    p_mem.add_argument("--item-id", default=None, help="Memory Item ID")
    p_mem.add_argument("--type", default="goal", choices=["goal", "mastery", "misconception", "preference"])
    p_mem.add_argument("--topic", default=None, help="Memory topic")
    p_mem.add_argument("--content", default=None, help="Memory content")
    p_mem.add_argument("--confidence", type=float, default=1.0)
    p_mem.add_argument("--reason", default="Learner correction")
    p_mem.set_defaults(func=manage_memory)

    p_eval = sub.add_parser("eval", help="Run automated evaluation and adversarial red team harness (M7)")
    p_eval.add_argument("--cases", default="benchmark/cases_60.jsonl", help="Benchmark cases file")
    p_eval.add_argument("--mode", default="mock", choices=["mock", "live"], help="Execution mode")
    p_eval.add_argument("--output", default="benchmark/results/evaluation_report.json", help="Output report path")
    p_eval.add_argument("--top-k", type=int, default=5, help="Retrieval depth")
    p_eval.add_argument("--rerank", action="store_true", help="Enable reranker")
    p_eval.set_defaults(func=run_eval_cli)

    p_char = sub.add_parser("characterize", help="Run performance characterization across configurations (M8)")
    p_char.add_argument("--cases", default="benchmark/cases_60.jsonl", help="Benchmark cases file")
    p_char.add_argument("--output", default="benchmark/results/performance_characterization.json", help="Output path")
    p_char.add_argument("--top-k", type=int, default=5, help="Retrieval depth")
    p_char.set_defaults(func=run_characterization_cli)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
