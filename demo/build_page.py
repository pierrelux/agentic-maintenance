"""Inline results/demo_data.json into the page template.

    python demo/build_page.py   -> demo/p201.html   (page body, as published on claude.ai)
                                -> docs/index.html  (standalone document, served by GitHub Pages)
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
data = json.loads((root.parent / "results" / "demo_data.json").read_text())
html = (root / "page_template.html").read_text()
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
page = html.replace("__DATA__", blob)
(root / "p201.html").write_text(page)
print("wrote", root / "p201.html", round(len(page) / 1e3), "kB")

# Standalone version: same page wrapped in a full HTML document (title, fonts and styles in <head>).
cut = page.index("</style>") + len("</style>")
head, body = page[:cut].replace('<meta charset="utf-8">\n', "", 1), page[cut:]
doc = ("<!doctype html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"utf-8\">\n"
       "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
       "<meta name=\"description\" content=\"Banc d'essai de diagnostic actif : une alarme de pompe simulée avec NASA ProgPy, "
       "des agents qui choisissent quand payer pour un test, et les traces rejouées de leurs enquêtes.\">\n"
       + head + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n")
docs = root.parent / "docs"
docs.mkdir(exist_ok=True)
(docs / "index.html").write_text(doc)
(docs / ".nojekyll").write_text("")
print("wrote", docs / "index.html", round(len(doc) / 1e3), "kB")
