"""Permite invocar la herramienta local como módulo."""

from .provision import main


if __name__ == "__main__":
    raise SystemExit(main())
