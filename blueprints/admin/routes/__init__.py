# blueprints/admin/routes/__init__.py

# Blueprint singoli
from .admin_dashboard import admin_panel_bp
from .admin_manage_riders import admin_lineup_bp  # usa questo per gestione lineup/riders
#from .admin_lineup import admin_lineup_bp  # ✅ non c'è piu
from .admin_races import admin_races_bp
from .admin_teams import admin_teams_bp
from .admin_imports import admin_imports_bp
from .admin_import_riders import admin_import_riders_bp
from .import_wtrl import import_wtrl_bp

# Lista di tutti i blueprint da registrare
all_blueprints = [
    admin_panel_bp,
    admin_lineup_bp,  # qui sostituito admin_manage_riders_bp con admin_lineup_bp
    admin_races_bp,
    admin_teams_bp,
    admin_imports_bp,
    admin_import_riders_bp,
    import_wtrl_bp
]
