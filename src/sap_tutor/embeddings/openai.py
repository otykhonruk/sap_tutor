import os

from openai import OpenAI


DEFAULT_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")


def get_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")

    # If base_url is set (e.g. for local Ollama), API key might not be strictly needed,
    # but the OpenAI client requires it to be non-empty.
    if not api_key:
        if base_url:
            api_key = "local"
        else:
            raise SystemExit("OPENAI_API_KEY is not set")

    return OpenAI(api_key=api_key, base_url=base_url)


def embed_documents(texts, model=DEFAULT_MODEL):
    client = get_client()
    response = client.embeddings.create(
        model=model,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_query(text, model=DEFAULT_MODEL):
    return embed_documents([text], model=model)[0]
