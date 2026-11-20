"""Gera avisos das dependências; não substitui revisão de licenças antes da distribuição."""

import importlib.metadata as metadata
import json, sys
from pathlib import Path

out = []
for dist in sorted(metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
    if dist.metadata["Name"].lower() in [
        "pip",
        "setuptools",
        "pytest",
        "pyinstaller",
        "pip-audit",
    ]:
        continue
    out.append(
        f"\n{'=' * 60}\n{dist.metadata['Name']} {dist.version}\nLicença: {dist.metadata.get('License-Expression') or dist.metadata.get('License', 'consulte os avisos abaixo')}\n"
    )
    for f in dist.files or []:
        if any(
            k in f.name.lower() for k in ["license", "copying", "notice"]
        ) and f.suffix.lower() in ["", ".txt", ".md", ".rst"]:
            try:
                out.append(dist.locate_file(f).read_text(errors="replace"))
            except OSError:
                pass
lock = Path(__file__).resolve().parents[1] / "frontend" / "package-lock.json"
if lock.exists():
    out.append("\nDEPENDÊNCIAS DO FRONTEND\n")
    for name, pkg in json.loads(lock.read_text()).get("packages", {}).items():
        if name:
            out.append(
                f"{name}: {pkg.get('version', '')} — {pkg.get('license', 'consulte pacote original')}\n"
            )
notices = Path(__file__).resolve().parents[1] / "frontend" / "THIRD-PARTY-NOTICES.txt"
if notices.exists():
    out.append(notices.read_text(encoding="utf-8"))
Path(sys.argv[1]).write_text("\n".join(out), encoding="utf-8")
