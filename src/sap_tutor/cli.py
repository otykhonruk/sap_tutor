import os

from cyclopts import App

from sap_tutor.files import DEFAULT_DOCS_DIR
from sap_tutor.history import MessageHistory
from sap_tutor.providers import get_provider
from sap_tutor.signal_bot import DEFAULT_SIGNAL_API_URL, run as run_signal_bot
from sap_tutor.storages import get_storage


app = App(help="FAQ bot CLI with pluggable providers, storages, and Signal transport.")


@app.default
@app.command
def sync(
    storage="gemini_file_search",
    docs_dir=DEFAULT_DOCS_DIR,
    embedding=None,
    embedding_model=None,
):
    kwargs = {}
    if embedding:
        kwargs["embedding"] = embedding
    if embedding_model:
        kwargs["embedding_model"] = embedding_model

    result = get_storage(storage).sync(docs_dir, **kwargs)
    print(f"Storage: {storage}")
    print(f"Synced {result['files']} markdown documents.")
    print(f"Docs directory: {result['docs_dir']}")
    print(f"Store: {result['store']}")
    if result.get("embedding"):
        print(f"Embedding: {result['embedding']}")


@app.command
def answer(
    query,
    provider="gemini",
    storage=None,
    model=None,
    limit=5,
    embedding=None,
    embedding_model=None,
):
    provider_module = get_provider(provider)
    kwargs = {"limit": limit}
    if model:
        kwargs["model"] = model
    if storage:
        kwargs["storage"] = storage
    if embedding:
        kwargs["embedding"] = embedding
    if embedding_model:
        kwargs["embedding_model"] = embedding_model

    result = provider_module.answer(query, **kwargs)
    print(result["text"])
    if result["sources"]:
        print()
        print("Джерела:")
        for source in result["sources"]:
            print(source)

    print()
    print(f"Provider: {result['provider']}")
    print(f"Storage: {result['storage']}")
    print(f"Store: {result['store']}")
    print(f"Model: {result['model']}")
    if result.get("embedding"):
        print(f"Embedding: {result['embedding']}")


@app.command
def search(
    query,
    storage="chroma",
    limit=5,
    embedding=None,
    embedding_model=None,
):
    storage_module = get_storage(storage)
    if not hasattr(storage_module, "search"):
        raise SystemExit(f"Storage '{storage}' does not support search.")

    kwargs = {"limit": limit}
    if embedding:
        kwargs["embedding"] = embedding
    if embedding_model:
        kwargs["embedding_model"] = embedding_model

    result = storage_module.search(query, **kwargs)
    print(f"Query: {result['query']}")
    print(f"Storage: {result['storage']}")
    print(f"Store: {result['store']}")
    print(f"Results: {len(result['results'])}")
    if result.get("embedding"):
        print(f"Embedding: {result['embedding']}")

    for index, item in enumerate(result["results"], start=1):
        print()
        print(f"{index}. {item['path']}")
        print(f"   distance: {item['distance']:.4f}")
        print(f"   preview: {item['preview']}")


@app.command
def signal_bot(
    provider="gemini",
    storage=None,
    model=None,
    embedding=None,
    embedding_model=None,
    api_url=os.environ.get("SIGNAL_API_URL", DEFAULT_SIGNAL_API_URL),
    poll_interval=2.0,
    test_mode=False,
    multi_account=False,
    account=os.environ.get("SIGNAL_ACCOUNT"),
    db_path=os.environ.get("SIGNAL_BOT_DB_PATH"),
):
    provider_module = get_provider(provider)

    def answer_fn(query):
        kwargs = {}
        if model:
            kwargs["model"] = model
        if storage:
            kwargs["storage"] = storage
        if embedding:
            kwargs["embedding"] = embedding
        if embedding_model:
            kwargs["embedding_model"] = embedding_model
        return provider_module.answer(query, **kwargs)

    run_signal_bot(
        answer_fn=answer_fn,
        api_url=api_url,
        poll_interval=poll_interval,
        test_mode=test_mode,
        multi_account=multi_account,
        account=account,
        db_path=db_path,
    )


@app.command
def dump_chat(
    group_id: str = "all",
    output_dir: str = "data/chats",
    db_path: str = os.environ.get("SIGNAL_BOT_DB_PATH"),
    output_format: str = "markdown",
):
    from pathlib import Path
    from datetime import datetime, timezone
    import json

    output_format = output_format.lower()
    if output_format not in ("markdown", "jsonl"):
        raise SystemExit("Unsupported format. Please choose 'markdown' or 'jsonl'.")

    history = MessageHistory(db_path=db_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if group_id == "all":
        groups = history.get_unique_groups()
    else:
        # None/none represents private chats (no group)
        groups = [None if group_id.lower() == "none" else group_id]

    print(f"Exporting to directory: {output_path.resolve()}")
    print(f"Format: {output_format}")

    exported_files = []
    for g_id in groups:
        messages = history.get_messages(group_id=g_id)
        if not messages:
            if group_id != "all":
                print(f"No messages found for group: {g_id}")
            continue

        filename_suffix = g_id if g_id is not None else "private"
        # Sanitize filename: keep only alphanumeric characters, dashes, and underscores
        filename_suffix = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in filename_suffix
        )

        ext = "md" if output_format == "markdown" else "jsonl"
        file_path = output_path / f"chat_{filename_suffix}.{ext}"

        if output_format == "markdown":
            content_lines = [
                "---",
                f"group_id: {g_id or 'private'}",
                f"exported_at: {datetime.now(timezone.utc).isoformat()}",
                "---",
                "",
                f"# Історія чату: {g_id or 'Приватні діалоги'}",
                "",
            ]
            for msg in messages:
                try:
                    dt = datetime.fromtimestamp(
                        msg["timestamp"] / 1000.0, timezone.utc
                    ).isoformat()
                except Exception:
                    dt = "unknown"

                content_lines.extend(
                    [
                        f"## [{dt}] Повідомлення від {msg['source']} (ID: {msg['id']})",
                        f"- **Відправник:** {msg['source']}",
                        f"- **Таймстамп:** {msg['timestamp']}",
                        f"- **Це FAQ:** {'Так' if msg['is_faq'] else 'Ні'}",
                    ]
                )
                if msg["query"]:
                    content_lines.append(f"- **Запит:** {msg['query']}")
                if msg["reply"]:
                    reply_indented = msg["reply"].replace("\n", "\n  ")
                    content_lines.append(f"- **Відповідь:** {reply_indented}")

                content_lines.extend(
                    [
                        "",
                        "### Текст повідомлення",
                        msg["body"],
                        "",
                        "---",
                        "",
                    ]
                )
            file_path.write_text("\n".join(content_lines), encoding="utf-8")
        else:
            # JSONL format
            with open(file_path, "w", encoding="utf-8") as f:
                for msg in messages:
                    d = dict(msg)
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")

        print(f"Exported {len(messages)} messages -> {file_path.name}")
        exported_files.append(file_path)

    history.close()
    print(f"Done. Exported {len(exported_files)} chat files.")
