"""Corpus manifest loader, validator, and provenance resolver for public instructional sources."""
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from config import CONFIG
from ingestion.versioning import SourceVersion


VALID_MODALITIES = {"video", "audio", "visual", "multimodal", "text"}
PLACEHOLDER_PATTERN = re.compile(r"^<(?:URL|url|TBD|tbd)>$|^(?:TBD|tbd|example\.com)$", re.IGNORECASE)


class ManifestValidationError(ValueError):
    """Raised when source manifest data is malformed or invalid."""
    pass


@dataclass
class SourceAssetRecord:
    source_id: str
    edition_id: str
    asset_id: str
    title: str
    source_url: str
    original_asset_url: str
    modality: str
    duration_sec: Optional[float] = None
    transcript_available: bool = False
    transcript_url: Optional[str] = None
    subtitles_url: Optional[str] = None
    visual_available: bool = False
    slides_url: Optional[str] = None
    code_available: bool = False
    code_url: Optional[str] = None
    license: str = "unknown"
    license_url: Optional[str] = None
    attribution: str = "unknown"
    provenance_notes: str = ""
    content_hash: Optional[str] = None
    ingestion_status: str = "cataloged"
    download_asset_url: Optional[str] = None

    @property
    def duration(self) -> Optional[int]:
        return int(self.duration_sec) if self.duration_sec is not None else None

    @property
    def licence_info(self) -> Dict[str, Any]:
        return {"name": self.license, "url": self.license_url}

    @property
    def license_info(self) -> Dict[str, Any]:
        return self.licence_info

    @property
    def attribution_info(self) -> Dict[str, Any]:
        return {"author": self.attribution, "institution": "Harvard University"}

    @property
    def notes(self) -> str:
        return self.provenance_notes

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate_manifest(data: Any) -> List[SourceAssetRecord]:
    """Validates raw manifest dictionary or list and returns parsed SourceAssetRecords.
    
    Enforces:
    - required fields
    - unique source/version/asset identity
    - valid modality values
    - non-empty and non-placeholder URLs for public sources
    - non-empty version identity
    - no accidental duplicate assets
    """
    if isinstance(data, list):
        raw_sources = data
    elif isinstance(data, dict):
        raw_sources = data.get("sources")
        if not isinstance(raw_sources, list) or len(raw_sources) == 0:
            raise ManifestValidationError("Manifest must contain a non-empty 'sources' list")
    else:
        raise ManifestValidationError(f"Manifest root must be a dictionary or list, got {type(data).__name__}")

    records: List[SourceAssetRecord] = []
    seen_asset_ids = set()
    seen_composite_keys = set()
    seen_source_edition_keys = set()
    seen_edition_asset_urls = set()

    required_fields = [
        "source_id", "edition_id", "asset_id", "title",
        "source_url", "original_asset_url", "modality",
    ]

    for idx, item in enumerate(raw_sources):
        if not isinstance(item, dict):
            raise ManifestValidationError(f"Source entry at index {idx} must be a dictionary")

        for field in required_fields:
            val = item.get(field)
            if val is None:
                raise ManifestValidationError(f"Source entry {idx} missing required field '{field}'")
            val_str = str(val).strip()
            if not val_str:
                raise ManifestValidationError(f"Source entry {idx} {field} must not be empty (source_url must not be empty)")
            if PLACEHOLDER_PATTERN.match(val_str) or any(p in val_str.lower() for p in ["<url>", "<tbd>", "example.com"]) or val_str.upper() == "TBD":
                raise ManifestValidationError(f"placeholder URL detected in '{field}': '{val_str}'")

        source_id = str(item["source_id"]).strip()
        edition_id = str(item["edition_id"]).strip()
        asset_id = str(item["asset_id"]).strip()
        title = str(item["title"]).strip()
        source_url = str(item["source_url"]).strip()
        original_asset_url = str(item["original_asset_url"]).strip()
        modality = str(item["modality"]).strip().lower()

        # Validate URLs
        for url_name, url_str in [("source_url", source_url), ("original_asset_url", original_asset_url)]:
            if not (url_str.startswith("http://") or url_str.startswith("https://")):
                raise ManifestValidationError(
                    f"Asset '{asset_id}' has invalid URL for '{url_name}': '{url_str}'"
                )
            if "example.com" in url_str.lower() or PLACEHOLDER_PATTERN.match(url_str) or "<url>" in url_str.lower() or url_str.upper() == "TBD":
                raise ManifestValidationError(
                    f"placeholder URL detected for '{url_name}': '{url_str}'"
                )

        # Validate modality
        if modality not in VALID_MODALITIES:
            raise ManifestValidationError(
                f"Asset '{asset_id}' has invalid modality '{modality}'. Allowed: {sorted(VALID_MODALITIES)}"
            )

        # Uniqueness checks
        if asset_id in seen_asset_ids:
            raise ManifestValidationError(f"Duplicate asset_id detected: '{asset_id}'")
        seen_asset_ids.add(asset_id)

        source_edition_key = (source_id, edition_id)
        if source_edition_key in seen_source_edition_keys:
            raise ManifestValidationError(
                f"Duplicate logical source/edition identity: '{source_id}' in edition '{edition_id}'"
            )
        seen_source_edition_keys.add(source_edition_key)

        composite_key = (source_id, edition_id, asset_id)
        if composite_key in seen_composite_keys:
            raise ManifestValidationError(f"Duplicate source/edition/asset identity: {composite_key}")
        seen_composite_keys.add(composite_key)

        edition_asset_key = (edition_id, original_asset_url)
        if edition_asset_key in seen_edition_asset_urls:
            raise ManifestValidationError(
                f"Duplicate asset URL in edition '{edition_id}': '{original_asset_url}'"
            )
        seen_edition_asset_urls.add(edition_asset_key)

        # Validate optional duration_sec
        duration_sec = item.get("duration_sec")
        if duration_sec is not None:
            try:
                duration_sec = float(duration_sec)
                if duration_sec <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ManifestValidationError(f"Asset '{asset_id}' has invalid duration_sec: {duration_sec}")

        record = SourceAssetRecord(
            source_id=source_id,
            edition_id=edition_id,
            asset_id=asset_id,
            title=title,
            source_url=source_url,
            original_asset_url=original_asset_url,
            modality=modality,
            duration_sec=duration_sec,
            transcript_available=bool(item.get("transcript_available", False)),
            transcript_url=item.get("transcript_url"),
            subtitles_url=item.get("subtitles_url"),
            visual_available=bool(item.get("visual_available", False)),
            slides_url=item.get("slides_url"),
            code_available=bool(item.get("code_available", False)),
            code_url=item.get("code_url"),
            license=str(item.get("license", "unknown")),
            license_url=item.get("license_url"),
            attribution=str(item.get("attribution", "unknown")),
            provenance_notes=str(item.get("provenance_notes", "")),
            content_hash=item.get("content_hash"),
            ingestion_status=str(item.get("ingestion_status", "cataloged")),
            download_asset_url=item.get("download_asset_url"),
        )
        records.append(record)

    return records


def load_manifest(path: Optional[str] = None) -> List[SourceAssetRecord]:
    """Loads and validates the corpus manifest from path (JSON or YAML)."""
    manifest_path = path or getattr(CONFIG, "manifest_path", "data/source_manifest.json")
    if not os.path.exists(manifest_path):
        # Look in workspace root data/ directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alt_paths = [
            os.path.join(base_dir, "data", "source_manifest.json"),
            os.path.join(base_dir, "data", "source_manifest.yaml"),
            os.path.join("data", "source_manifest.json"),
            os.path.join("data", "source_manifest.yaml"),
        ]
        for alt in alt_paths:
            if os.path.exists(alt):
                manifest_path = alt
                break

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Source manifest not found at: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        if manifest_path.endswith((".yaml", ".yml")):
            try:
                import yaml
                data = yaml.safe_load(f)
            except ImportError:
                f.seek(0)
                try:
                    data = json.load(f)
                except Exception as exc:
                    raise ManifestValidationError(
                        f"PyYAML is not installed and file is not JSON-formatted: {manifest_path} ({exc})"
                    )
        else:
            data = json.load(f)

    return validate_manifest(data)


def get_manifest_asset(asset_id: str, manifest_path: Optional[str] = None) -> Optional[SourceAssetRecord]:
    """Finds a specific manifest record by its unique asset_id."""
    records = load_manifest(manifest_path)
    for r in records:
        if r.asset_id == asset_id:
            return r
    return None


def get_manifest_source(
    source_id: str,
    edition_id: Optional[str] = None,
    manifest_path: Optional[str] = None,
) -> Optional[SourceAssetRecord]:
    """Finds a manifest record by logical source_id and optional edition_id."""
    records = load_manifest(manifest_path)
    for r in records:
        if r.source_id == source_id:
            if edition_id is None or r.edition_id == edition_id:
                return r
    return None


def build_source_version_from_manifest(
    record: SourceAssetRecord,
    content_hash: str,
) -> SourceVersion:
    """Builds a SourceVersion instance linked to the manifest record's provenance."""
    return SourceVersion(
        source_id=record.source_id,
        content_hash=content_hash,
        course_edition=record.edition_id,
        title=record.title,
        asset_id=record.asset_id,
        source_url=record.source_url,
    )
