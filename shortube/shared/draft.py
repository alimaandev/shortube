from __future__ import annotations

import json
from pathlib import Path


def slugify(topic: str, max_len: int = 40) -> str:
    return topic.lower().replace(" ", "_")[:max_len]


def used_topics_path(assets_dir: Path) -> Path:
    return assets_dir / "used_topics.json"


def get_used_topics(assets_dir: Path) -> set[str]:
    path = used_topics_path(assets_dir)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("used", []))
    except (json.JSONDecodeError, OSError):
        return set()


def mark_topic_used(assets_dir: Path, topic: str) -> None:
    path = used_topics_path(assets_dir)
    used = get_used_topics(assets_dir)
    used.add(slugify(topic))
    path.write_text(
        json.dumps({"used": list(sorted(used))}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def is_topic_used(assets_dir: Path, topic: str) -> bool:
    return slugify(topic) in get_used_topics(assets_dir)


def clear_used_topics(assets_dir: Path) -> None:
    path = used_topics_path(assets_dir)
    if path.exists():
        path.unlink()


def save_draft(topic: str, data: dict, draft_dir: Path | str) -> str:
    draft_dir = Path(draft_dir)
    draft_dir.mkdir(parents=True, exist_ok=True)
    path = draft_dir / f"{slugify(topic)}_draft.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"topic": topic, **data}, f, indent=2, ensure_ascii=False)
    return str(path)


def load_draft(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
