import json
from pathlib import Path
from typing import Dict, List, Optional

from .config import STORE_PATH


class JobStore:
    def __init__(self, path: Path = STORE_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            self._jobs = data

    def _save(self) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self._jobs, fh, ensure_ascii=False, indent=2)

    def upsert(self, job: dict) -> None:
        self._jobs[job["job_id"]] = job
        self._save()

    def get(self, job_id: str) -> Optional[dict]:
        return self._jobs.get(job_id)

    def list(self) -> List[dict]:
        return sorted(self._jobs.values(), key=lambda item: item["created_at"], reverse=True)
