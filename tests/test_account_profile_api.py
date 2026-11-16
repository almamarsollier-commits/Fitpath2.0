import json
import tempfile
import unittest
from pathlib import Path

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import seed_initial_roles


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"
MIGRATION_VERSIONS = tuple(range(1, 13))


class AccountProfileApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database_path = Path(self.temporary.name) / "profile.sqlite3"
        self.app = create_app(
            "testing",
            {
                "DATABASE": str(self.database_path),
                "MIGRATIONS_DIR": str(MIGRATIONS_DIR),
                "SECRET_KEY": "profile-test-secret",
            },
        )
        self.client = self.app.test_client()
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        self.assertEqual(
            apply_migrations(self.db, MIGRATIONS_DIR), MIGRATION_VERSIONS
        )
        seed_initial_roles(self.db)
        self.client_role_id = self._role_id("Cliente")
        self.admin_role_id = self._role_id("Administrador")
        self.user_id = self._create_user(
            "Ana", "Pérez", "ana.fit", "ana@example.test", self.client_role_id
        )
        self.other_user_id = self._create_user(
            "Otra", "Persona", "ocupado", "otra@example.test", self.client_role_id
        )
        self.admin_id = self._create_user(
            "Ada", "Admin", "ada.admin", "admin@example.test", self.admin_role_id
        )
        self.client_profile_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.user_id,)
        ).lastrowid
        self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.other_user_id,)
        )
        type_id = self.db.execute(
            "INSERT INTO tipos_objetivo (nombre) VALUES ('Condición física')"
        ).lastrowid
        self.goal_ids = [
            self.db.execute(
                "INSERT INTO objetivos (tipo_objetivo_id, nombre, descripcion) VALUES (?, ?, ?)",
                (type_id, name, description),
            ).lastrowid
            for name, description in (
                ("Ganar fuerza", "Aumentar fuerza de forma progresiva."),
                ("Mejorar resistencia", "Sostener esfuerzos durante más tiempo."),
            )
        ]
        self.db.commit()

    def _role_id(self, name):
        return self.db.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?", (name,)
        ).fetchone()[0]

    def _create_user(self, first_name, last_name, username, email, role_id):
        return self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (first_name, last_name, username, email, role_id),
        ).lastrowid

    def _login(self, user_id=None, csrf="profile-csrf"):
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = user_id or self.user_id
            session["csrf_token"] = csrf

    def _patch(self, payload, csrf="profile-csrf"):
        return self.client.patch(
            "/api/v1/me/profile",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )

    def test_profile_requires_authentication_and_csrf(self):
        self.assertEqual(self.client.get("/api/v1/me/profile").status_code, 401)
        self._login()
        self.assertEqual(self._patch({"nombre": "Inés"}, csrf="wrong").status_code, 400)
        self.assertEqual(
            self.db.execute(
                "SELECT nombre FROM usuarios WHERE id_usuario = ?", (self.user_id,)
            ).fetchone()[0],
            "Ana",
        )

    def test_get_returns_only_the_authenticated_profile_and_read_only_fields(self):
        self._login()
        response = self.client.get("/api/v1/me/profile")
        self.assertEqual(response.status_code, 200)
        profile = response.json["profile"]
        self.assertEqual(profile["id"], self.user_id)
        self.assertEqual(profile["email"], "ana@example.test")
        self.assertEqual(profile["rol"], "Cliente")
        self.assertEqual(profile["preferencias"]["tema"], "sistema")
        self.assertEqual(
            {item["id"] for item in profile["catalogo_objetivos"]},
            set(self.goal_ids),
        )
        self.assertNotIn("activo", profile)
        self.assertNotIn("rol_id", profile)

    def test_client_can_update_allowed_fields_preferences_and_goals(self):
        self._login()
        response = self._patch(
            {
                "nombre": "  Inés  ",
                "apellido": "O'Connor",
                "nombre_usuario": "ines.fit",
                "telefono": "+54 11 5555-1212",
                "biografia": "Entreno con constancia y objetivos sostenibles.",
                "preferencias": {
                    "tema": "oscuro",
                    "movimiento_reducido": True,
                    "recordatorios_clase": False,
                },
                "objetivos": self.goal_ids,
            }
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        profile = response.json["profile"]
        self.assertEqual(profile["nombre"], "Inés")
        self.assertEqual(profile["nombre_usuario"], "ines.fit")
        self.assertEqual(profile["objetivos"], self.goal_ids)
        self.assertEqual(profile["preferencias"]["tema"], "oscuro")
        stored = self.db.execute(
            """
            SELECT u.email, u.rol_id, u.activo, p.biografia, p.preferencias_json
            FROM usuarios AS u
            JOIN perfiles_usuario AS p ON p.usuario_id = u.id_usuario
            WHERE u.id_usuario = ?
            """,
            (self.user_id,),
        ).fetchone()
        self.assertEqual(tuple(stored[:3]), ("ana@example.test", self.client_role_id, 1))
        self.assertEqual(stored["biografia"], profile["biografia"])
        self.assertFalse(json.loads(stored["preferencias_json"])["recordatorios_clase"])
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM cliente_objetivo WHERE cliente_id = ?",
                (self.client_profile_id,),
            ).fetchone()[0],
            2,
        )

    def test_username_is_unique_and_failed_update_rolls_back_every_field(self):
        self._login()
        response = self._patch(
            {"nombre": "Nombre cambiado", "nombre_usuario": "OCUPADO"}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"], "username_unavailable")
        row = self.db.execute(
            "SELECT nombre, nombre_usuario FROM usuarios WHERE id_usuario = ?",
            (self.user_id,),
        ).fetchone()
        self.assertEqual(tuple(row), ("Ana", "ana.fit"))

    def test_email_role_state_and_identifiers_cannot_be_changed(self):
        self._login()
        for payload in (
            {"email": "nuevo@example.test"},
            {"rol": "Administrador"},
            {"activo": 0},
            {"google_subject": "otro"},
            {"id_usuario": self.other_user_id},
        ):
            response = self._patch(payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertEqual(response.json["error"], "fields_not_allowed", payload)
        row = self.db.execute(
            "SELECT email, rol_id, activo FROM usuarios WHERE id_usuario = ?",
            (self.user_id,),
        ).fetchone()
        self.assertEqual(tuple(row), ("ana@example.test", self.client_role_id, 1))

    def test_validation_rejects_invalid_values_and_unknown_goals(self):
        self._login()
        invalid_payloads = (
            {"nombre": "123"},
            {"nombre_usuario": "dos" + "!"},
            {"telefono": "abc"},
            {"biografia": "x" * 501},
            {"preferencias": {"tema": "neón"}},
            {"preferencias": {"dato_privado": True}},
            {"objetivos": [999999]},
        )
        for payload in invalid_payloads:
            response = self._patch(payload)
            self.assertEqual(response.status_code, 400, payload)
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM cliente_objetivo WHERE cliente_id = ?",
                (self.client_profile_id,),
            ).fetchone()[0],
            0,
        )

    def test_non_client_can_edit_own_profile_but_not_training_goals(self):
        self._login(self.admin_id)
        edited = self._patch({"biografia": "Administración de la red de sedes."})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json["profile"]["rol"], "Administrador")
        rejected = self._patch({"objetivos": self.goal_ids})
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.json["error"], "field_not_applicable")


if __name__ == "__main__":
    unittest.main()
