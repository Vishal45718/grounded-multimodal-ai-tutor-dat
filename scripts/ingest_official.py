import argparse
import os
import sys

# Ensure repository root is in sys.path when script is executed directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib.request
import tempfile
import sqlite3

from typing import List

from ingestion.manifest import get_manifest_asset, get_manifest_source
from ingestion.transcriber import parse_srt, TranscriptSegment
from ingestion.chunker import build_chunks
from ingestion.versioning import SourceVersion, file_content_hash
from storage.corpus_store import init_db, insert_chunks, upsert_source, is_source_active
from ingestion.ocr import OcrResult, extract_pdf_slides
import hashlib
from config import CONFIG

def resolve_citation(chunk_id: str):
    init_db()
    with sqlite3.connect(CONFIG.corpus_db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,))
        chunk = cur.fetchone()
        if not chunk:
            print(f"Error: Unknown evidence ID '{chunk_id}' rejected.")
            return

        print("\n--- RESOLVED CITATION ---")
        print(f"Source ID:   {chunk['source_id']}")
        print(f"Modality:    {chunk['modality']}")
        if chunk['start_sec'] is not None and chunk['end_sec'] is not None:
            print(f"Time Bounds: {chunk['start_sec']}s - {chunk['end_sec']}s")
        else:
            print(f"Time Bounds: Unknown")
        print(f"Content:     {chunk['text']}")
        if chunk['start_sec'] is not None:
            print(f"Video Nav:   {chunk['source_url']}&t={int(chunk['start_sec'])}s")
        if chunk['image_path']:
            print(f"Visual Nav:  {chunk['image_path']}")
        print("-------------------------\n")


def ingest_official(args):
    init_db()
    manifest_path = getattr(args, "manifest", None) or CONFIG.manifest_path
    asset_id = getattr(args, "asset_id", None)
    manifest_record = None
    if asset_id:
        manifest_record = get_manifest_asset(asset_id, manifest_path=manifest_path)
    if not manifest_record:
        source_id = getattr(args, "source_id", None)
        course_edition = getattr(args, "course_edition", None)
        if source_id:
            manifest_record = get_manifest_source(source_id, edition_id=course_edition, manifest_path=manifest_path)
    
    if not manifest_record:
        raise ValueError("Asset not found in manifest")
        
    source_id = manifest_record.source_id
    course_edition = manifest_record.edition_id
    asset_id = manifest_record.asset_id
    source_url = manifest_record.source_url
    
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = None
        transcript = []
        subtitles_url = manifest_record.subtitles_url or manifest_record.transcript_url
        if subtitles_url:
            srt_path = os.path.join(tmpdir, "subs.srt")
            print(f"Downloading official transcript for {asset_id}...")
            urllib.request.urlretrieve(subtitles_url, srt_path)
            transcript = parse_srt(srt_path)
        
        pdf_path = None
        if manifest_record.slides_url:
            print(f"Downloading official slides for {asset_id}...")
            pdf_path = os.path.join(tmpdir, "slides.pdf")
            urllib.request.urlretrieve(manifest_record.slides_url, pdf_path)

        # Generate deterministic content_hash from downloaded inputs
        hash_parts = []
        if srt_path and os.path.exists(srt_path):
            hash_parts.append(file_content_hash(srt_path))
        if pdf_path and os.path.exists(pdf_path):
            hash_parts.append(file_content_hash(pdf_path))
        content_hash = hashlib.sha256("".join(hash_parts).encode("utf-8")).hexdigest()[:16]

        ocr_results = []
        if pdf_path and os.path.exists(pdf_path):
            print(f"Rendering slides and extracting text for {asset_id}...")
            ocr_results = extract_pdf_slides(
                pdf_path=pdf_path,
                source_id=source_id,
                content_hash=content_hash,
            )

        print(f"Building chunks...")
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
            title=manifest_record.title,
            asset_id=asset_id,
            source_url=source_url,
        )
        insert_chunks(chunks)
        upsert_source(version)
        print(f"Ingested {len(chunks)} chunks using official materials.")
        
        sample_audio = next((c for c in chunks if c.modality == "audio"), None)
        if sample_audio:
            print(f"\nCreated real audio evidence example ID: {sample_audio.chunk_id}")
            print(f"Try running: python scripts/ingest_official.py resolve --chunk-id {sample_audio.chunk_id}")
        sample_visual = next((c for c in chunks if c.modality == "visual"), None)
        if sample_visual:
            print(f"\nCreated real visual evidence example ID: {sample_visual.chunk_id}")
            print(f"Try running: python scripts/ingest_official.py resolve --chunk-id {sample_visual.chunk_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    p_ingest = subparsers.add_parser("ingest")
    p_ingest.add_argument("--asset-id", default=None)
    p_ingest.add_argument("--source-id", default=None)
    p_ingest.add_argument("--course-edition", default=None)
    p_ingest.add_argument("--manifest", default=CONFIG.manifest_path)
    
    p_resolve = subparsers.add_parser("resolve")
    p_resolve.add_argument("--chunk-id", required=True)
    
    args = parser.parse_args()
    if args.command == "ingest":
        if not args.asset_id and not args.source_id:
            parser.error("Either --asset-id or --source-id is required for ingestion.")
        ingest_official(args)
    elif args.command == "resolve":
        resolve_citation(args.chunk_id)

