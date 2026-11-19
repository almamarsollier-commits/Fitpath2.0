import sqlite3
from pathlib import Path

from config import DevelopmentConfig

db = sqlite3.connect(str(DevelopmentConfig.DATABASE))

print("COLUMNAS DE LA TABLA EJERCICIOS:")
columnas = db.execute("PRAGMA table_info(ejercicios)").fetchall()

for columna in columnas:
    print("-", columna[1])

print("\nMIGRACION 0015:")
migracion = db.execute(
    "SELECT version FROM schema_migrations WHERE version = 15"
).fetchall()

print(migracion)

db.close()
