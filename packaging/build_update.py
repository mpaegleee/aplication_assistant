"""Atualização completa: runtime e Chromium também mudam na versão 0.3."""

import hashlib
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
portable = root / "dist" / "ApplicationAssistant-Windows-Local"
manifest = json.loads((portable / "build-manifest.json").read_text())
version = manifest["version"]
files = []
for directory in ["app", "frontend", "Ajuda", "runtime", "browsers"]:
    files.extend(p for p in (portable / directory).rglob("*") if p.is_file())
files.append(portable / "build-manifest.json")
assert all(p.is_relative_to(portable) for p in files)
assert not any(p.suffix in [".key", ".sqlite3", ".sqlite"] for p in files)
output = root / "dist" / f"ApplicationAssistant-Atualizacao-{version}.zip"
with zipfile.ZipFile(
    output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
) as archive:
    checksums = []
    for file in sorted(files):
        relative = file.relative_to(portable).as_posix()
        archive.write(file, relative)
        checksums.append(
            hashlib.sha256(file.read_bytes()).hexdigest() + "  " + relative
        )
    guide = root / "docs" / f"ATUALIZACAO-{version}.md"
    archive.writestr("LEIA-ME-ATUALIZACAO.txt", guide.read_text(encoding="utf-8"))
    archive.writestr("UPDATE-FILES.sha256", "\n".join(checksums) + "\n")
checksum = hashlib.sha256(output.read_bytes()).hexdigest()
Path(str(output) + ".sha256").write_text(checksum + "  " + output.name + "\n")
print(output)
print(f"{output.stat().st_size / 1e6:.2f} MB — SHA256 {checksum}")
