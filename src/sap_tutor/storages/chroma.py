from pathlib import Path

import chromadb

from sap_tutor.embeddings import get_embedding
from sap_tutor.files import collect_markdown_files, resolve_docs_dir


CHROMA_DIR = Path(".chroma")
COLLECTION_NAME = "sap_tutor_docs"


def get_client():
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def sync(docs_dir, embedding="openai", embedding_model=None):
    client = get_client()
    docs_dir = resolve_docs_dir(docs_dir)
    files = collect_markdown_files(docs_dir)
    if not files:
        raise SystemExit(f"No markdown files found in: {docs_dir}")
    embedding_backend = get_embedding(embedding)

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    ids = []
    documents = []
    metadatas = []

    total = len(files)

    for index, path in enumerate(files, start=1):
        relative_path = str(path.relative_to(docs_dir))
        print(f"[{index}/{total}] embedding {relative_path}")
        document = path.read_text(encoding="utf-8")

        ids.append(relative_path)
        documents.append(document)
        metadatas.append({"relative_path": relative_path})

    embeddings = embedding_backend.embed_documents(documents, model=embedding_model or embedding_backend.DEFAULT_MODEL)

    print(f"[{total}/{total}] writing collection")
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )

    return {
        "docs_dir": str(docs_dir),
        "store": str(CHROMA_DIR / COLLECTION_NAME),
        "files": len(files),
        "storage": "chroma",
        "embedding": embedding,
    }


def retrieve(query, limit=5, embedding="openai", embedding_model=None):
    if limit < 1:
        raise SystemExit("limit must be >= 1")

    client = get_client()
    collection = client.get_collection(COLLECTION_NAME)
    embedding_backend = get_embedding(embedding)
    results = collection.query(
        query_embeddings=[embedding_backend.embed_query(query, model=embedding_model or embedding_backend.DEFAULT_MODEL)],
        n_results=limit,
        include=["documents", "metadatas", "distances"],
    )

    items = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for document, metadata, distance in zip(documents, metadatas, distances):
        preview = " ".join(document.split())
        if len(preview) > 280:
            preview = preview[:277] + "..."

        items.append(
            {
                "path": metadata["relative_path"],
                "distance": distance,
                "preview": preview,
                "document": document,
            }
        )

    return {
        "query": query,
        "results": items,
        "store": str(CHROMA_DIR / COLLECTION_NAME),
        "storage": "chroma",
        "embedding": embedding,
    }


def search(query, limit=5, embedding="openai", embedding_model=None):
    result = retrieve(query, limit=limit, embedding=embedding, embedding_model=embedding_model)
    for item in result["results"]:
        item.pop("document", None)
    return result
