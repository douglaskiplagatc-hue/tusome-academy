"""Scan project for likely-unused Python modules and HTML templates."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"venv", "__pycache__", ".git", "migrations", "static", "uploads"}


def iter_source_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix in {".py", ".html", ".htm", ".md", ".txt", ".json"}:
            yield p


def main():
    refs = set()
    pattern_render = re.compile(r'render_template\s*\(\s*["\']([^"\']+)["\']')
    pattern_ext = re.compile(r'extends\s+["\']([^"\']+)["\']')
    pattern_inc = re.compile(r'include\s+["\']([^"\']+)["\']')
    pattern_import = re.compile(r"(?:from|import)\s+([\w\.]+)")

    all_text = ""
    py_modules = {}  # stem -> paths

    for p in iter_source_files():
        rel = p.relative_to(ROOT)
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        all_text += text + "\n"
        if p.suffix == ".py":
            py_modules.setdefault(p.stem, []).append(str(rel).replace("\\", "/"))

        for pat in (pattern_render, pattern_ext, pattern_inc):
            for m in pat.finditer(text):
                refs.add(m.group(1).replace("\\", "/"))

    # Templates
    tpl_dir = ROOT / "templates"
    templates = []
    if tpl_dir.exists():
        for p in tpl_dir.rglob("*"):
            if p.suffix in {".html", ".htm"}:
                templates.append(str(p.relative_to(tpl_dir)).replace("\\", "/"))

    unused_tpl = []
    for t in sorted(templates):
        if t in refs or f"templates/{t}" in refs:
            continue
        if any(t in r or r.endswith(t) for r in refs):
            continue
        unused_tpl.append(t)

    # Root-level / orphan Python files
    registered = set()
    init_py = ROOT / "routes" / "__init__.py"
    if init_py.exists():
        registered.update(re.findall(r"from routes\.(\w+)", init_py.read_text(encoding="utf-8")))

    orphan_py = []
    legacy_py = []
    for rel, paths in sorted(py_modules.items()):
        if rel in {"__init__", "env", "find_unused"}:
            continue
        path = paths[0]
        if path.startswith("routes/") and rel not in registered and rel != "reports":
            if rel.endswith("_routes") or rel == "subject_routes":
                orphan_py.append(path)
        if path in {
            "routes.py",
            "analytics.py",
            "advanced_api.py",
            "advanced_analytics.py",
            "mobile_api.py",
            "audit_log.py",
            "audit_logs.py",
            "reports.py",
            "add_column.py",
            "seed_data.py",
            "security.py",
        }:
            legacy_py.append(path)

    # Check imports for legacy files
    for name in [
        "routes",
        "advanced_api",
        "advanced_analytics",
        "mobile_api",
        "audit_log",
        "audit_logs",
        "reports",
        "add_column",
        "seed_data",
        "security",
        "analytics",
    ]:
        if name not in all_text and f"import {name}" not in all_text:
            pass  # handled in legacy list

    print("=== LIKELY UNUSED PYTHON (not in routes/__init__.py) ===")
    for p in orphan_py:
        print(p)
    print("\n=== LEGACY / UNREGISTERED ROOT PYTHON ===")
    for p in legacy_py:
        used = p.replace(".py", "") in all_text or p.replace("/", ".").replace(".py", "") in all_text
        flag = "maybe referenced" if used else "NOT imported by app"
        print(f"{p}  ({flag})")

    print(f"\n=== UNUSED TEMPLATES ({len(unused_tpl)}) ===")
    for t in unused_tpl:
        print(t)


if __name__ == "__main__":
    main()
