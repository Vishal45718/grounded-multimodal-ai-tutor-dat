import argparse
import os
import urllib.request
import tempfile
import fitz  # PyMuPDF, if needed for PDF
from ingestion.manifest import get_manifest_asset, get_manifest_source
from ingestion.transcriber import parse_srt
from ingestion.chunker import build_chunks
from ingestion.versioning import SourceVersion
from storage.corpus_store import init_db, insert_chunks, upsert_source, is_source_active
from ingestion.ocr import OcrResult

def download_file(url, local_path):
    print(f"Downloading {url} to {local_path}...")
    urllib.request.urlretrieve(url, local_path)

def ingest_official(args):
    init_db()
    manifest_record = get_manifest_asset(args.asset_id, manifest_path=args.manifest)
    if not manifest_record:
        manifest_record = get_manifest_source(args.source_id, edition_id=args.course_edition, manifest_path=args.manifest)
    
    if not manifest_record:
        raise ValueError("Asset not found in manifest.")
        
    source_id = manifest_record.source_id
    course_edition = manifest_record.edition_id
    asset_id = manifest_record.asset_id
    source_url = manifest_record.source_url
    content_hash = "official_content_hash" # placeholder or hash the srt
    
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = os.path.join(tmpdir, "subs.srt")
        download_file(manifest_record.subtitles_url, srt_path)
        transcript = parse_srt(srt_path)
        
        ocr_results = []
        if manifest_record.slides_url:
            pdf_path = os.path.join(tmpdir, "slides.pdf")
            download_file(manifest_record.slides_url, pdf_path)
            # pseudo-OCR from PDF
            try:
                import fitz
                doc = fitz.open(pdf_path)
                for i, page in enumerate(doc):
                    text = page.get_text().strip()
                    if text:
                        ocr_results.append(OcrResult(timestamp_sec=i*10.0, image_path=f"slide_{i}.pdf", text=text, status="success"))
            except ImportError:
                print("PyMuPDF (fitz) not installed, skipping PDF text extraction.")

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
        print(f"Ingested {len(chunks)} chunks.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--manifest", default="data/source_manifest.yaml")
    args = parser.parse_args()
    ingest_official(args)
