import os
from pathlib import Path

from openai import OpenAI

from sap_tutor.files import collect_markdown_files, read_state_file, resolve_docs_dir, write_state_file


VECTOR_STORE_FILE = Path(".openai-vector-store")
VECTOR_STORE_NAME = "sap-tutor-docs"


def get_client():
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set")
    return OpenAI()


def get_vector_store_id():
    return read_state_file(VECTOR_STORE_FILE)


def recreate_vector_store(client):
    vector_store_id = get_vector_store_id()
    if vector_store_id:
        try:
            client.vector_stores.delete(vector_store_id)
        except Exception:
            pass

    vector_store = client.vector_stores.create(name=VECTOR_STORE_NAME)
    write_state_file(VECTOR_STORE_FILE, vector_store.id)
    return vector_store


def sync(docs_dir):
    client = get_client()
    docs_dir = resolve_docs_dir(docs_dir)
    files = collect_markdown_files(docs_dir)
    if not files:
        raise SystemExit(f"No markdown files found in: {docs_dir}")

    vector_store = recreate_vector_store(client)

    total = len(files)

    for index, path in enumerate(files, start=1):
        relative_path = str(path.relative_to(docs_dir))
        print(f"[{index}/{total}] uploading {relative_path}")
        with path.open("rb") as file_handle:
            uploaded_file = client.files.create(
                file=file_handle,
                purpose="assistants",
            )

        print(f"[{index}/{total}] indexing {relative_path}")
        client.vector_stores.files.create_and_poll(
            vector_store_id=vector_store.id,
            file_id=uploaded_file.id,
            attributes={"relative_path": relative_path},
        )
        print(f"[{index}/{total}] done {relative_path}")

    return {
        "docs_dir": str(docs_dir),
        "store": vector_store.id,
        "files": len(files),
        "storage": "openai_vector_store",
    }
