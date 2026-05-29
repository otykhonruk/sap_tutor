from google import genai
from google.genai import types

from sap_tutor.storages import get_storage


DEFAULT_MODEL = "gemini-2.5-flash"


def answer(query, model=DEFAULT_MODEL, storage=None, limit=5, embedding=None, embedding_model=None):
    client = genai.Client()
    storage_name = storage or "gemini_file_search"

    if storage_name == "gemini_file_search":
        storage_module = get_storage(storage_name)
        store_name = storage_module.get_store_name()
        if not store_name:
            raise SystemExit("Gemini File Search store is not configured. Run sync first.")

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
                source = relative_path or context.title or "unknown"
                if source not in sources:
                    sources.append(source)

        return {
            "text": response.text or "Не вдалося сформувати відповідь.",
            "sources": sources,
            "store": store_name,
            "model": model,
            "provider": "gemini",
            "storage": storage_name,
        }

    if storage_name == "chroma":
        storage_module = get_storage(storage_name)
        result = storage_module.retrieve(query, limit=limit, embedding=embedding or "openai", embedding_model=embedding_model)
        context = "\n\n---\n\n".join(
            f"[{item['path']}]\n{item['document']}" for item in result["results"]
        )
        response = client.models.generate_content(
            model=model,
            contents=f"Запит користувача:\n{query}\n\nКонтекст:\n\n{context}",
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Ти відповідаєш на запит користувача лише на основі наданого контексту. "
                    "Якщо даних недостатньо, так і скажи. Відповідай українською."
                ),
                temperature=0.2,
            ),
        )

        return {
            "text": response.text or "Не вдалося сформувати відповідь.",
            "sources": [item["path"] for item in result["results"]],
            "store": result["store"],
            "model": model,
            "provider": "gemini",
            "storage": storage_name,
            "embedding": result["embedding"],
        }

    raise SystemExit(f"Storage '{storage_name}' is not supported by provider 'gemini'.")
