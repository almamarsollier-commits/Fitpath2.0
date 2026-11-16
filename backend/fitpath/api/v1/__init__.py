"""Registro explícito de APIs versionadas."""


def init_api_v1(app):
    from .assistant import assistant_api_blueprint
    from .payments import payments_api_blueprint
    from .profile import profile_api_blueprint

    app.register_blueprint(assistant_api_blueprint)
    app.register_blueprint(payments_api_blueprint)
    app.register_blueprint(profile_api_blueprint)
