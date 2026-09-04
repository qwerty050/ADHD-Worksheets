import hashlib
import json
from pathlib import Path

CACHE_VERSION = 3  # bump to invalidate every existing cache file (v3: Typst output)


class PipelineCache:
    """
    File-backed cache for pipeline progress.

    Cache files are keyed by input filename + content hash + kb/lecture suffix
    + cache version, so changed inputs or pipeline upgrades never serve stale
    results. Pass fresh=True to ignore any existing cache for this run.
    """

    def __init__(self, input_file_path: Path, kb_id: str = None, lecture_id: str = None, fresh: bool = False):
        self.cache_dir = Path(".pipeline_cache")
        self.cache_dir.mkdir(exist_ok=True)

        suffix = ""
        if kb_id:
            suffix += f"_kb-{Path(kb_id).stem}"
        if lecture_id:
            suffix += f"_lec-{lecture_id}"

        content_hash = "nohash"
        try:
            content_hash = hashlib.sha1(Path(input_file_path).read_bytes()).hexdigest()[:8]
        except OSError:
            pass

        self.cache_file = (
            self.cache_dir
            / f"{Path(input_file_path).name}_{content_hash}{suffix}_v{CACHE_VERSION}.cache.json"
        )

        if self.cache_file.exists() and not fresh:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            self.data.setdefault("sections", {})
        else:
            self.data = {"extraction": None, "sections": {}}

    def save(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    # --- Stage 1: section map ---
    def get_extraction(self):
        return self.data.get("extraction")

    def set_extraction(self, data):
        self.data["extraction"] = data
        self.save()

    # --- Per-section steps: annotate / writer / questions / compiled / memory_updated ---
    def get_section_step(self, section_idx: int, step: str):
        sec_idx_str = str(section_idx)
        if sec_idx_str in self.data["sections"]:
            return self.data["sections"][sec_idx_str].get(step)
        return None

    def set_section_step(self, section_idx: int, step: str, content):
        sec_idx_str = str(section_idx)
        if sec_idx_str not in self.data["sections"]:
            self.data["sections"][sec_idx_str] = {}
        self.data["sections"][sec_idx_str][step] = content
        self.save()
