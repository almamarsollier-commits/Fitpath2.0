"""Ayudas de prueba para artefactos locales opcionales."""


def snapshot_optional_file(path):
    """Devuelve metadatos estables o ``None`` cuando el archivo no existe."""
    if not path.exists():
        return None
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def assert_optional_file_unchanged(test_case, path, before):
    """Comprueba que un archivo existente no cambie o que siga ausente."""
    test_case.assertEqual(snapshot_optional_file(path), before)
