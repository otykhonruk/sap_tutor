from importlib import import_module


def get_storage(name):
    try:
        return import_module(f"sap_tutor.storages.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"sap_tutor.storages.{name}":
            raise SystemExit(f"Unknown storage: {name}") from exc
        raise
