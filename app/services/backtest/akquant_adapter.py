"""AKQuant adapter boundary.

The project keeps AKQuant behind this adapter. When the package is not
available or lacks the required public API, the engine returns an explicit
limitation and uses the local deterministic compatibility runner.
"""
from __future__ import annotations


def akquant_status() -> dict:
    try:
        import akquant  # type: ignore

        return {"available": True, "module": getattr(akquant, "__name__", "akquant"), "version": getattr(akquant, "__version__", "unknown")}
    except Exception as exc:
        return {"available": False, "error": str(exc)}

