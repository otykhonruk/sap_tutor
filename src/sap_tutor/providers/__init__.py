from importlib import import_module


def get_provider(name):
    try:
        return import_module(f"sap_tutor.providers.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"sap_tutor.providers.{name}":
            raise SystemExit(f"Unknown provider: {name}") from exc
        raise
