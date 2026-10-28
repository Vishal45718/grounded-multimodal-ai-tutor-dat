import sys
from scripts.ingest_official import ingest_official, resolve_citation

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Official material ingestion helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    p_ingest = subparsers.add_parser("ingest")
    p_ingest.add_argument("--asset-id", required=True)
    p_ingest.add_argument("--manifest", default="data/source_manifest.yaml")
    
    p_resolve = subparsers.add_parser("resolve")
    p_resolve.add_argument("--chunk-id", required=True)
    
    args = parser.parse_args()
    if args.command == "ingest":
        ingest_official(args)
    elif args.command == "resolve":
        resolve_citation(args.chunk_id)

