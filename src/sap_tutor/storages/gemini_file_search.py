import os
import shutil
import tempfile
import time
from pathlib import Path

from google import genai

from sap_tutor.files import collect_markdown_files, read_state_file, resolve_docs_dir, write_state_file


STORE_NAME_FILE = Path(".gemini-file-search-store")
STORE_DISPLAY_NAME = "sap-tutor-docs"


def get_client():
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is not set")
    return genai.Client()


def get_store_name():
    return read_state_file(STORE_NAME_FILE)


def recreate_store(client):
    store_name = get_store_name()
    if store_name:
        try:
            client.file_search_stores.delete(name=store_name)
        except Exception:
            pass

    store = client.file_search_stores.create(
        config={
            "display_name": STORE_DISPLAY_NAME,
        }
    )
    write_state_file(STORE_NAME_FILE, store.name)
    return store


def wait_for_operation(client, operation):
    while not operation.done:
        time.sleep(2)
        operation = client.operations.get(operation)
    return operation


def sync(docs_dir):
    client = get_client()
    docs_dir = resolve_docs_dir(docs_dir)
    files = collect_markdown_files(docs_dir)
    if not files:
        raise SystemExit(f"No markdown files found in: {docs_dir}")

    store = recreate_store(client)
    temp_dir = tempfile.TemporaryDirectory()
    operations = []

    total = len(files)

    for index, path in enumerate(files, start=1):
        relative_path = str(path.relative_to(docs_dir))
        suffix = path.suffix or ".md"
        temp_path = Path(temp_dir.name) / f"file-{len(operations):04d}{suffix}"

        print(f"[{index}/{total}] uploading {relative_path}")
        with path.open("rb") as source_file, temp_path.open("wb") as temp_file:
            shutil.copyfileobj(source_file, temp_file)

        operation = client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store.name,
            file=str(temp_path),
            config={
                "mime_type": "text/markdown",
                "display_name": relative_path,
                "custom_metadata": [
                    {
                        "key": "relative_path",
                        "string_value": relative_path,
                    }
                ],
            },
        )
        operations.append(operation)

    for index, (path, operation) in enumerate(zip(files, operations), start=1):
        relative_path = str(path.relative_to(docs_dir))
        print(f"[{index}/{total}] indexing {relative_path}")
        wait_for_operation(client, operation)
        print(f"[{index}/{total}] done {relative_path}")

    temp_dir.cleanup()

    return {
        "docs_dir": str(docs_dir),
        "store": store.name,
        "files": len(files),
        "storage": "gemini_file_search",
    }
