from importlib import import_module


def get_embedding(name):
    try:
        return import_module(f"sap_tutor.embeddings.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"sap_tutor.embeddings.{name}":
            raise SystemExit(f"Unknown embedding backend: {name}") from exc
        raise
