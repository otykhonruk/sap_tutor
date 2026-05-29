from openai import OpenAI

from sap_tutor.storages import get_storage


DEFAULT_MODEL = "gpt-4.1-mini"


def answer(query, model=DEFAULT_MODEL, storage=None, limit=5, embedding=None, embedding_model=None):
    client = OpenAI()
    storage_name = storage or "openai_vector_store"

    if storage_name == "openai_vector_store":
        storage_module = get_storage(storage_name)
        vector_store_id = storage_module.get_vector_store_id()
        if not vector_store_id:
            raise SystemExit("OpenAI vector store is not configured. Run sync first.")

        response = client.responses.create(
            model=model,
            input=query,
            instructions=(
                "Ти відповідаєш на запит користувача лише на основі документів з file_search. "
                "Якщо даних недостатньо, так і скажи. Відповідай українською."
            ),
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [vector_store_id],
                }
            ],
            include=["file_search_call.results"],
        )

        sources = []
        for output in response.output or []:
            if output.type != "file_search_call":
                continue
            for result in output.results or []:
                attributes = getattr(result, "attributes", None) or {}
                source = attributes.get("relative_path") or getattr(result, "filename", None) or "unknown"
                if source not in sources:
                    sources.append(source)

        return {
            "text": response.output_text or "Не вдалося сформувати відповідь.",
            "sources": sources,
            "store": vector_store_id,
            "model": model,
            "provider": "openai",
            "storage": storage_name,
        }

    if storage_name == "chroma":
        storage_module = get_storage(storage_name)
        result = storage_module.retrieve(query, limit=limit, embedding=embedding or "openai", embedding_model=embedding_model)
        context = "\n\n---\n\n".join(
            f"[{item['path']}]\n{item['document']}" for item in result["results"]
        )
        response = client.responses.create(
            model=model,
            input=f"Запит користувача:\n{query}\n\nКонтекст:\n\n{context}",
            instructions=(
                "Ти відповідаєш на запит користувача лише на основі наданого контексту. "
                "Якщо даних недостатньо, так і скажи. Відповідай українською."
            ),
        )

        return {
            "text": response.output_text or "Не вдалося сформувати відповідь.",
            "sources": [item["path"] for item in result["results"]],
            "store": result["store"],
            "model": model,
            "provider": "openai",
            "storage": storage_name,
            "embedding": result["embedding"],
        }

    raise SystemExit(f"Storage '{storage_name}' is not supported by provider 'openai'.")
