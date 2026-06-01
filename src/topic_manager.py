import yaml
from pathlib import Path


_TOPICS_PATH = Path(__file__).parent.parent / "config" / "topics.yaml"
_topics_cache: list[dict] | None = None


def load_topics() -> list[dict]:
    global _topics_cache
    if _topics_cache is None:
        with open(_TOPICS_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _topics_cache = data.get("topics", [])
    return _topics_cache


def get_topic_labels() -> list[str]:
    return [t["label"] for t in load_topics()]


def get_selected_topics(labels: list[str]) -> list[dict]:
    return [t for t in load_topics() if t["label"] in labels]


def format_topics_for_prompt(labels: list[str]) -> str:
    selected = get_selected_topics(labels)
    if not selected:
        return "없음"
    lines = [f"- {t['label']}: {t['description']}" for t in selected]
    return "\n".join(lines)
