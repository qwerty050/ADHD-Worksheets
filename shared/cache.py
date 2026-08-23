import json
from pathlib import Path


class PipelineCache:
    """File-backed cache for pipeline progress."""

    def __init__(self, input_file_path: Path):
        self.cache_dir = Path(".pipeline_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / f"{input_file_path.name}.cache.json"

        if self.cache_file.exists():
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            # Ensure required keys exist (older caches may lack them)
            if "sections" not in self.data:
                self.data["sections"] = {}
            if "finalization" not in self.data:
                self.data["finalization"] = None
        else:
            self.data = {
                "extraction": None,
                "question_extraction": None,
                "pedagogical": None,
                "sections": {},
                "finalization": None,
            }

    def save(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def has_cached_progress(self) -> bool:
        return (
            self.data.get("extraction") is not None
            or self.data.get("question_extraction") is not None
            or self.data.get("pedagogical") is not None
            or len(self.data.get("sections", {})) > 0
            or self.data.get("finalization") is not None
        )

    # --- Stage 1 ---
    def get_extraction(self):
        return self.data.get("extraction")

    def set_extraction(self, data):
        self.data["extraction"] = data
        self.save()

    # --- Stage 1.5a ---
    def get_question_extraction(self):
        return self.data.get("question_extraction")

    def set_question_extraction(self, data):
        self.data["question_extraction"] = data
        self.save()

    # --- Stage 1.5b ---
    def get_pedagogical(self):
        return self.data.get("pedagogical")

    def set_pedagogical(self, data):
        self.data["pedagogical"] = data
        self.save()

    # --- Per-section ---
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

    # --- Finalization ---
    def get_finalization(self):
        return self.data.get("finalization")

    def set_finalization(self, result: dict):
        self.data["finalization"] = result
        self.save()

    def clear(self):
        if self.cache_file.exists():
            self.cache_file.unlink()
        self.data = {
            "extraction": None,
            "question_extraction": None,
            "pedagogical": None,
            "sections": {},
            "finalization": None,
        }
