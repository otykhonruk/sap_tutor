import os
import time
from pathlib import Path

from cyclopts import App
from google import genai
from google.genai import types


DEFAULT_DOCS_DIR = Path("data")
DEFAULT_MODEL = "gemini-2.5-flash"
STORE_NAME_FILE = Path(".gemini-file-search-store")
STORE_DISPLAY_NAME = "sap-tutor-docs"

app = App(help="Gemini File Search CLI for FAQ documents.")


def require_api_key():
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is not set")


def get_client():
    require_api_key()
    return genai.Client()


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


def read_store_name():
    if not STORE_NAME_FILE.exists():
        return None
    store_name = STORE_NAME_FILE.read_text(encoding="utf-8").strip()
    return store_name or None


def write_store_name(store_name):
    STORE_NAME_FILE.write_text(store_name + "\n", encoding="utf-8")


def get_or_create_store(client):
    store_name = read_store_name()
    if store_name:
        try:
            store = client.file_search_stores.get(name=store_name)
            return store
        except Exception:
            pass

    store = client.file_search_stores.create(
        config={
            "display_name": STORE_DISPLAY_NAME,
        }
    )
    write_store_name(store.name)
    return store


def wait_for_operation(client, operation):
    while not operation.done:
        time.sleep(2)
        operation = client.operations.get(operation)
    return operation


def clear_store(client, store_name):
    documents = list(client.file_search_stores.documents.list(parent=store_name))
    for document in documents:
        client.file_search_stores.documents.delete(name=document.name)


def upload_documents(client, store_name, docs_dir):
    files = collect_markdown_files(docs_dir)
    if not files:
        raise SystemExit(f"No markdown files found in: {docs_dir}")

    for path in files:
        operation = client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store_name,
            file=path,
            config={
                "mime_type": "text/markdown",
                "display_name": str(path.relative_to(docs_dir)),
                "custom_metadata": [
                    {
                        "key": "relative_path",
                        "string_value": str(path.relative_to(docs_dir)),
                    }
                ],
            },
        )
        wait_for_operation(client, operation)

    return files


def extract_sources(response):
    sources = []
    candidates = response.candidates or []
    for candidate in candidates:
        metadata = getattr(candidate, "grounding_metadata", None)
        if not metadata:
            continue
        for chunk in metadata.grounding_chunks or []:
            context = getattr(chunk, "retrieved_context", None)
            if not context:
                continue
            relative_path = None
            for item in context.custom_metadata or []:
                if item.key == "relative_path":
                    relative_path = item.string_value
                    break
            sources.append(relative_path or context.title or "unknown")

    seen = []
    for source in sources:
        if source not in seen:
            seen.append(source)
    return seen


@app.default
@app.command
def sync(docs_dir=DEFAULT_DOCS_DIR):
    client = get_client()
    docs_dir = resolve_docs_dir(docs_dir)
    store = get_or_create_store(client)

    clear_store(client, store.name)
    files = upload_documents(client, store.name, docs_dir)

    print(f"Synced {len(files)} markdown documents.")
    print(f"Docs directory: {docs_dir}")
    print(f"Store: {store.name}")


@app.command
def answer(
    query,
    model=DEFAULT_MODEL,
):
    client = get_client()
    store_name = read_store_name()
    if not store_name:
        raise SystemExit("File Search store is not configured. Run: python main.py sync")

    response = client.models.generate_content(
        model=model,
        contents=query,
        config=types.GenerateContentConfig(
            system_instruction=(
                "Ти відповідаєш на запит користувача лише на основі документів з File Search. "
                "Якщо даних недостатньо, так і скажи. Відповідай українською."
            ),
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store_name],
                    )
                )
            ],
            temperature=0.2,
        ),
    )

    print(response.text)

    sources = extract_sources(response)
    if sources:
        print()
        print("Джерела:")
        for source in sources:
            print(source)

    print()
    print(f"Store: {store_name}")
    print(f"Model: {model}")


if __name__ == "__main__":
    app()
