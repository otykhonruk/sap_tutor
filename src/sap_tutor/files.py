import json
from pathlib import Path


DEFAULT_DOCS_DIR = Path("data")
SEEN_MESSAGES_FILE = Path(".signal-bot-seen.json")


def collect_markdown_files(docs_dir):
    return sorted(
        path for path in docs_dir.rglob("*.md")
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(docs_dir).parts)
    )


def resolve_docs_dir(docs_dir):
    docs_dir = docs_dir.resolve()
    if not docs_dir.exists() or not docs_dir.is_dir():
        raise SystemExit(f"Markdown directory not found: {docs_dir}")
    return docs_dir


def read_state_file(path):
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def write_state_file(path, value):
    path.write_text(value + "\n", encoding="utf-8")


def read_seen_messages():
    if not SEEN_MESSAGES_FILE.exists():
        return []
    try:
        return json.loads(SEEN_MESSAGES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def write_seen_messages(seen_messages):
    SEEN_MESSAGES_FILE.write_text(
        json.dumps(seen_messages[-1000:], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
