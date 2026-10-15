import argparse
import sys
from scripts.ingest_official import ingest_official, resolve_citation

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-id", default=None)
    parser.add_argument("--source-id", default=None)
    parser.add_argument("--course-edition", default=None)
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args()
    if not args.asset_id and not args.source_id:
        parser.error("Either --asset-id or --source-id is required.")
    ingest_official(args)

