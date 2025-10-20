# routes/__init__.py

from .seasons import seasons_bp
from .races import races_bp

# Se vuoi avere tutti i blueprint in una lista da registrare in run.py
all_blueprints = [seasons_bp, races_bp]
