import os

from openai import OpenAI


DEFAULT_MODEL = "text-embedding-3-small"


def get_client():
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set")
    return OpenAI()


def embed_documents(texts, model=DEFAULT_MODEL):
    client = get_client()
    response = client.embeddings.create(
        model=model,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_query(text, model=DEFAULT_MODEL):
    return embed_documents([text], model=model)[0]
