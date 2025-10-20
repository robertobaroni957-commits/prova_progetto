import os
import re

root = "C:/Progetti/gestioneZRL"

# 1. Trova tutti i file template
template_dir = os.path.join(root, "templates")
templates = []
for path, _, files in os.walk(template_dir):
    for f in files:
        if f.endswith(".html"):
            rel = os.path.relpath(os.path.join(path, f), template_dir)
            templates.append(rel.replace("\\", "/"))

# 2. Trova tutti i render_template nei .py
used_templates = set()
pattern = re.compile(r'render_template\(["\'](.*?)["\']')

for path, _, files in os.walk(root):
    for f in files:
        if f.endswith(".py"):
            full_path = os.path.join(path, f)
            try:
                text = open(full_path, encoding="utf-8").read()
                matches = pattern.findall(text)
                used_templates.update(matches)
            except Exception:
                pass

# 3. Confronta
unused = sorted(set(templates) - used_templates)
print("\n🔍 TEMPLATE NON USATI:")
for t in unused:
    print("  -", t)

print(f"\nTotale non usati: {len(unused)}")
