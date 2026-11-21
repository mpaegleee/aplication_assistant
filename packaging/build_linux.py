"""Bundle relocatable CPython, Linux wheels and Chromium without a large duplicate tree."""

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--browsers", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "dist/ApplicationAssistant-0.4.0-Linux-x64.tar.gz"
    output.parent.mkdir(exist_ok=True)
    prefix = "ApplicationAssistant-Linux"

    def filter_files(info):
        parts = Path(info.name).parts
        if any(
            p in ("__pycache__", ".links", "_pytest", "pytest")
            or p.startswith(("pytest-", "iniconfig-", "pluggy-"))
            for p in parts
        ):
            return None
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        if info.isfile():
            info.mode = 0o755 if info.mode & 0o111 else 0o644
        return info

    with tarfile.open(output, "w:gz") as archive:

        def add(path, name):
            archive.add(path, arcname=prefix + "/" + name, filter=filter_files)

        # Skip the runtime's original site-packages and merge the pinned target environment.
        for part in args.runtime.iterdir():
            if part.name == "lib":
                for child in part.iterdir():
                    if child.name == "python3.14":
                        for item in child.iterdir():
                            if item.name != "site-packages":
                                add(item, "runtime/lib/python3.14/" + item.name)
                    else:
                        add(child, "runtime/lib/" + child.name)
            else:
                add(part, "runtime/" + part.name)
        add(args.site, "runtime/lib/python3.14/site-packages")
        add(root / "backend/assistant", "app/assistant")
        add(root / "backend/launcher.py", "app/launcher.py")
        add(root / "backend/reset_password.py", "app/reset_password.py")
        add(root / "frontend/dist", "frontend/dist")
        for browser in args.browsers.iterdir():
            if browser.name.startswith(("chromium-", "ffmpeg-")):
                add(browser, "browsers/" + browser.name)
        add(root / "docs", "Ajuda")
        add(root / "LICENSE.txt", "LICENSE.txt")
        if (root / "frontend/THIRD-PARTY-NOTICES.txt").exists():
            add(root / "frontend/THIRD-PARTY-NOTICES.txt", "FRONTEND-NOTICES.txt")
        scripts = {
            "Iniciar.sh": '#!/bin/sh\nset -eu\naa_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexport PLAYWRIGHT_BROWSERS_PATH="$aa_root/browsers"\nexec "$aa_root/runtime/bin/python3.14" "$aa_root/app/launcher.py"\n',
            "Instalar.sh": """#!/bin/sh
set -eu
aa_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aa_install="${XDG_DATA_HOME:-$HOME/.local/share}/ApplicationAssistant"
mkdir -p "$aa_install"
if [ "$aa_root" != "$aa_install" ]; then cp -a "$aa_root/." "$aa_install/"; fi
mkdir -p "${XDG_DATA_HOME:-$HOME/.local/share}/applications"
printf '[Desktop Entry]\\nType=Application\\nName=Application Assistant\\nExec="%s/Iniciar.sh"\\nTerminal=true\\nCategories=Office;\\n' "$aa_install" > "${XDG_DATA_HOME:-$HOME/.local/share}/applications/application-assistant.desktop"
printf 'Instalado em %s. Abra Application Assistant no menu ou execute Iniciar.sh.\\n' "$aa_install"
""",
            "Redefinir-senha.sh": '#!/bin/sh\nset -eu\naa_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$aa_root/runtime/bin/python3.14" "$aa_root/app/reset_password.py"\n',
        }
        scripts["build-manifest.json"] = (
            json.dumps(
                {
                    "version": "0.4.0",
                    "target": "linux-x64",
                    "runtime": args.runtime.name,
                    "browser": "chromium-1255",
                    "native_smoke_test": "See Ajuda/VERIFICACAO.md",
                    "code_license": "MIT",
                },
                indent=2,
            )
            + "\n"
        )
        for name, text in scripts.items():
            data = text.encode()
            info = tarfile.TarInfo(prefix + "/" + name)
            info.mode = 0o755 if name.endswith(".sh") else 0o644
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    digest = hashlib.file_digest(output.open("rb"), "sha256").hexdigest()
    Path(str(output) + ".sha256").write_text(digest + "  " + output.name + "\n")
    print(output, round(output.stat().st_size / 1e6, 2), "MB", digest)


if __name__ == "__main__":
    main()
