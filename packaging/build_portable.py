"""Prepara Windows x64 em Linux ou Windows; não executa binários Windows.

Uso: python packaging/build_portable.py --compiler /caminho/para/python3.14
O compilador deve ser CPython da mesma versão major.minor do runtime embutido.
"""

import argparse, hashlib, json, shutil, subprocess, sys, tempfile, urllib.request, zipfile, re
from pathlib import Path
from packaging.requirements import Requirement
from packaging.markers import default_environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--version", default="3.14.10")
    parser.add_argument(
        "--browsers",
        required=True,
        help="Diretório Chromium Windows instalado pela mesma versão Playwright",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not (root / "frontend/dist/index.html").exists():
        raise SystemExit("Compile a interface antes de empacotar.")
    compiler_version = subprocess.check_output(
        [
            args.compiler,
            "-c",
            'import sys;print(".".join(map(str,sys.version_info[:2])))',
        ],
        text=True,
    ).strip()
    if compiler_version != ".".join(args.version.split(".")[:2]):
        raise SystemExit("Compilador incompatível com o runtime.")
    output = root / "dist"
    output.mkdir(exist_ok=True)
    target = output / "ApplicationAssistant-Windows-Local"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir()
    runtime = target / "runtime"
    runtime.mkdir()
    url = f"https://www.python.org/ftp/python/{args.version}/python-{args.version}-embed-amd64.zip"
    print("Baixando runtime CPython oficial:", url, flush=True)
    request = urllib.request.Request(
        url, headers={"User-Agent": "ApplicationAssistantBuild/0.1"}
    )
    blob = urllib.request.urlopen(request, timeout=60).read(100_000_000)
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        archive = work / "python.zip"
        archive.write_bytes(blob)
        with zipfile.ZipFile(archive) as z:
            z.extractall(runtime)
        wheels = work / "wheels"
        wheels.mkdir()
        # pip --platform selects wheels, but still evaluates markers on the build host.
        # Evaluate the universal lock against Windows before handing it to pip.
        environment = default_environment()
        environment.update(
            sys_platform="win32",
            os_name="nt",
            platform_system="Windows",
            platform_machine="AMD64",
            python_version=compiler_version,
            python_full_version=args.version,
            implementation_version=args.version,
        )
        entries = []
        logical = re.sub(
            r"\\\s*\n", " ", (root / "backend/requirements.lock").read_text()
        )
        for line in logical.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(" --hash=", 1)
            requirement = Requirement(parts[0].strip())
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            requirement.marker = None
            entries.append(
                str(requirement) + (" --hash=" + parts[1] if len(parts) > 1 else "")
            )
        windows_requirements = work / "windows-requirements.txt"
        windows_requirements.write_text("\n".join(entries) + "\n")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--only-binary=:all:",
                "--platform",
                "win_amd64",
                "--implementation",
                "cp",
                "--python-version",
                compiler_version.replace(".", ""),
                "--dest",
                str(wheels),
                "--require-hashes",
                "-r",
                str(windows_requirements),
            ],
            check=True,
        )
        site = runtime / "Lib/site-packages"
        site.mkdir(parents=True)
        dependencies = []
        for wheel in sorted(wheels.glob("*.whl")):
            dependencies.append(
                {
                    "file": wheel.name,
                    "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                }
            )
            with zipfile.ZipFile(wheel) as z:
                z.extractall(site)
            for data in site.glob("*.data"):
                for kind in ["purelib", "platlib"]:
                    if (data / kind).exists():
                        shutil.copytree(data / kind, site, dirs_exist_ok=True)
                shutil.rmtree(data)
        minor = compiler_version.replace(".", "")
        (runtime / f"python{minor}._pth").write_text(
            f"python{minor}.zip\n.\nLib/site-packages\n../app\nimport site\n",
            encoding="utf-8",
        )
        shutil.copytree(
            root / "backend/assistant",
            target / "app/assistant",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copy(root / "backend/launcher.py", target / "app/launcher.py")
        shutil.copy(
            root / "backend/reset_password.py", target / "app/reset_password.py"
        )
        subprocess.run(
            [
                args.compiler,
                "-m",
                "compileall",
                "-q",
                "-b",
                "-s",
                str(target),
                str(target / "app"),
            ],
            check=True,
        )
        for source in (target / "app").rglob("*.py"):
            source.unlink()
        browser_source = Path(args.browsers)
        if not list(browser_source.glob("chromium-*/chrome-win64/chrome.exe")):
            raise SystemExit(
                "Chromium Windows ausente. Use PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=win64 e playwright install --no-shell chromium."
            )
        shutil.copytree(
            browser_source, target / "browsers", ignore=shutil.ignore_patterns(".links")
        )
        shutil.copytree(root / "frontend/dist", target / "frontend/dist")
        shutil.copytree(root / "docs", target / "Ajuda")
        shutil.copy(root / "LICENSE.txt", target / "LICENSE.txt")
        # Preserve complete third-party license files in dist-info and Python's runtime LICENSE.
        (target / "THIRD-PARTY-NOTICES.txt").write_text(
            "CPython: consulte runtime/LICENSE.txt.\nDependências Python: licenças em runtime/Lib/site-packages/*.dist-info.\nFrontend: consulte FRONTEND-NOTICES.txt.\n",
            encoding="utf-8",
        )
        npm_license = root / "frontend/THIRD-PARTY-NOTICES.txt"
        if npm_license.exists():
            shutil.copy(npm_license, target / "FRONTEND-NOTICES.txt")
        (target / "Iniciar.cmd").write_text(
            '@echo off\r\ncd /d "%~dp0"\r\n"%~dp0runtime\\python.exe" "%~dp0app\\launcher.pyc"\r\nif errorlevel 1 pause\r\n',
            encoding="ascii",
        )
        (target / "Redefinir-senha.cmd").write_text(
            '@echo off\r\ncd /d "%~dp0"\r\n"%~dp0runtime\\python.exe" "%~dp0app\\reset_password.pyc"\r\npause\r\n',
            encoding="ascii",
        )
        (target / "LEIA-ME.txt").write_text(
            "APPLICATION ASSISTANT - TESTE LOCAL WINDOWS 10/11 x64\n\n1. Extraia a pasta inteira do ZIP para uma pasta pessoal.\n2. Clique duas vezes em Iniciar.cmd.\n3. Mantenha a janela aberta. O navegador abre em http://127.0.0.1:8765\n4. Crie uma senha e siga Ajuda/TESTE-LOCAL.md.\n\nNao precisa instalar Python, Node.js ou Docker.\nEste pacote foi montado em Linux e ainda precisa de validacao em Windows.\nNavegador interno: login manual e sessoes locais. InHire experimental e SMTP para envio automatico. Consulte Ajuda/ATUALIZACAO-0.6.2.md.\nNao ha chaves de IA, contas ou dados pessoais incluidos.\nCodigo aberto sob MIT. Versao experimental: valide a instalacao antes de distribuir como estavel.\n",
            encoding="utf-8",
        )
        manifest = {
            "version": "0.6.2",
            "target": "windows-x64",
            "runtime_url": url,
            "runtime_sha256": hashlib.sha256(blob).hexdigest(),
            "runtime_version": args.version,
            "dependencies": dependencies,
            "tested_on_windows": False,
        }
        (target / "build-manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    zip_path = shutil.make_archive(
        str(output / "ApplicationAssistant-Windows-Local-0.6.2"),
        "zip",
        target.parent,
        target.name,
    )
    digest = hashlib.sha256(Path(zip_path).read_bytes()).hexdigest()
    Path(zip_path + ".sha256").write_text(digest + "  " + Path(zip_path).name + "\n")
    print("Pacote preparado:", zip_path, flush=True)
    print("SHA256:", digest, flush=True)


if __name__ == "__main__":
    main()
