# Real Public Lecture to Evidence Path

This document demonstrates the full path from a real public lecture source to navigable evidence using the official CS50 materials.

## 1. Selected Lecture
- **Source ID**: `cs50-lec01`
- **Asset ID**: `cs50-2024-lec01-video`
- **Edition**: `2024`
- **Title**: Lecture 1: C

## 2. Source/Provenance
- **Original Asset URL**: `https://youtu.be/cwtpLIWylAw`
- **Download URL**: `https://cdn.cs50.net/2023/fall/lectures/1/lecture1-720p.mp4`
- **Transcript/Captions**: `https://cdn.cs50.net/2023/fall/lectures/1/lang/en/lecture1.srt`
- **Slides**: `https://cdn.cs50.net/2023/fall/lectures/1/lecture1.pdf`

The ingestion uses the official supplied material (SRT captions and PDF slides) to avoid running unnecessary ASR/OCR, preserving the exact authoritative content.

## 3. Ingestion Command
To reproduce the ingestion of this lecture using the official material, run the following command:

```bash
python scripts/ingest_official.py ingest --asset-id cs50-2024-lec01-video
```

*Note: This script bypasses heavy dependencies like whisper and tesseract by reading the official SRT and PDF files directly. It downloads these directly into memory/temp storage and processes them into chunks.*

## 4. Evidence Storage
The produced evidence chunks are stored in the main SQLite database (`data/corpus.db`) under the `chunks` table. They preserve:
- `source_id`: `cs50-lec01`
- `asset_id`: `cs50-2024-lec01-video`
- `content_hash`: deterministic SHA-256 hash of the downloaded input bytes (the exact `.srt` and `.pdf` files).
- `timestamp_start` and `timestamp_end` bounds:
  - For audio (SRT) chunks: real timing data directly from the official transcript.
  - For visual (PDF) chunks: marked as `Unknown` (`null`) since trustworthy slide-to-video alignment is not currently available. We explicitly avoid hallucinating synthetic timestamps like `10.0s`.
- `modality` (`audio` or `visual`)

## 5. One Real Evidence Record
Example generated Audio Chunk:

```json
{
  "chunk_id": "0cccc2af36c1280534e9c3d48885af73",
  "source_id": "cs50-lec01",
  "modality": "audio",
  "start_sec": 584.71,
  "end_sec": 613.71,
  "text": "on the interesting parts for now. So how do I go about actually writing and compiling and running some code? Well, the teaser is going to be these three steps. One of these is a command called, aptly, Code. And Code is just going to let me to open or create a new file, like a file called \"hello.c.\" Make is going to be, for now, my compiler that allows me to make the program, that is convert source code into machine code, so from C to zeros and ones.",
  "asset_id": "cs50-2024-lec01-video"
}
```
*(This is an exact chunk produced by parsing `lecture1.srt`)*

## 6. One Real Citation
Citation ID: `0cccc2af36c1280534e9c3d48885af73`

You can resolve this citation locally by running:
```bash
python scripts/ingest_official.py resolve --chunk-id 0cccc2af36c1280534e9c3d48885af73
```

## 7. How an Evaluator Navigates to It
Running the resolve command above yields:

```
--- RESOLVED CITATION ---
Source ID:   cs50-lec01
Modality:    audio
Time Bounds: 584.71s - 613.71s
Content:     on the interesting parts for now. So how do I go about actually writing and compiling and running some code? Well, the teaser is going to be these three steps. One of these is a command called, aptly, Code. And Code is just going to let me to open or create a new file, like a file called "hello.c." Make is going to be, for now, my compiler that allows me to make the program, that is convert source code into machine code, so from C to zeros and ones.
Video Nav:   https://cs50.harvard.edu/x/2024/weeks/1/&t=584s
-------------------------
```

The evaluator can copy the `Video Nav` link (`https://cs50.harvard.edu/x/2024/weeks/1/&t=584s`) to jump directly to the cited moment in the official lecture material online.

## 8. How to Reproduce
1. Ensure the database is initialized: `python main.py ingest --help` (just to load modules) or ensure `data/corpus.db` is writable.
2. Ensure you have `pyyaml` and `PyMuPDF` installed (for testing official parsing script).
3. Run `python scripts/ingest_official.py ingest --asset-id cs50-2024-lec01-video`
4. Resolve the sample chunk ID printed at the end of the script using the `resolve` command above.

## Verification
- We verified that the ingestion script downloads the SRT and PDF.
- The **content hash** is generated directly by hashing the actual `.srt` and `.pdf` files downloaded from the official sources, rather than a hardcoded placeholder.
- **Audio timestamps** reflect the exact timestamps in the official captions.
- **Visual timestamps** are correctly recorded as `Unknown` since no accurate source mapping exists. The citation resolver accurately reports this and does not append fake `&t=` tags to the URLs.
- The actual ingestion was executed and validated locally. Full multimodal answering and retrieval pipeline is not yet complete.
