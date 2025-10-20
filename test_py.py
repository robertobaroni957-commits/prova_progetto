import os
import ast

# Cartella del progetto
PROJECT_DIR = os.path.abspath(".")

# Cartelle da ignorare completamente
IGNORE_DIRS = {"__pycache__", "venv", ".git"}

# File critici da ignorare (inizializzazione, blueprint principali, utils condivisi)
IGNORE_FILES = {
    "__init__.py",
    "db.py",
    "run.py",
    "zwift.py",
    "edit.py"
}

# Lista dei file sospetti
suspicious_files = []

for root, dirs, files in os.walk(PROJECT_DIR):
    # Filtra le directory da ignorare
    dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

    for file in files:
        if file.endswith(".py") and file not in IGNORE_FILES:
            path = os.path.join(root, file)
            # Prova a leggere il file e verificare se ha definizioni (funzioni o classi)
            with open(path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=file)
                    has_defs = any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in tree.body)
                    if not has_defs:
                        suspicious_files.append(path)
                except Exception as e:
                    # Se non riesce a leggere/parsing, ignora per sicurezza
                    pass

print("\nFile .py potenzialmente inutilizzati o vuoti:")
for f in suspicious_files:
    print(f)

print(f"\nTotale sospetti: {len(suspicious_files)}")
