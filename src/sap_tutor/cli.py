import os

from cyclopts import App

from sap_tutor.files import DEFAULT_DOCS_DIR
from sap_tutor.providers import get_provider
from sap_tutor.signal_bot import DEFAULT_SIGNAL_RPC_URL, run as run_signal_bot
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
    rpc_url=os.environ.get("SIGNAL_RPC_URL", DEFAULT_SIGNAL_RPC_URL),
    poll_interval=2.0,
    test_mode=False,
    multi_account=False,
    account=os.environ.get("SIGNAL_ACCOUNT"),
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
        rpc_url=rpc_url,
        poll_interval=poll_interval,
        test_mode=test_mode,
        multi_account=multi_account,
        account=account,
    )
