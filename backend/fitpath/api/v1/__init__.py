"""Registro explícito de APIs versionadas."""


def init_api_v1(app):
    from .account_profile import account_profile_api_blueprint
    from .admin import admin_api_blueprint
    from .assistant import assistant_api_blueprint
    from .calendar import calendar_api_blueprint
    from .client import client_api_blueprint
    from .manager import manager_api_blueprint
    from .payments import payments_api_blueprint
    from .profile import profile_api_blueprint
    from .technician import technician_api_blueprint
    from .trainer import trainer_api_blueprint

    app.register_blueprint(account_profile_api_blueprint)
    app.register_blueprint(admin_api_blueprint)
    app.register_blueprint(assistant_api_blueprint)
    app.register_blueprint(calendar_api_blueprint)
    app.register_blueprint(client_api_blueprint)
    app.register_blueprint(manager_api_blueprint)
    app.register_blueprint(payments_api_blueprint)
    app.register_blueprint(profile_api_blueprint)
    app.register_blueprint(technician_api_blueprint)
    app.register_blueprint(trainer_api_blueprint)
