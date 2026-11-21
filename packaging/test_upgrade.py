"""Install the published 0.5.0, create test data, then install the new package over it."""

import argparse
import hashlib
import io
import os
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.request import urlopen

import httpx
from assistant.history import record_stage
from assistant.store import Store
from reportlab.pdfgen.canvas import Canvas

BASE = "https://github.com/mpaegleee/aplication_assistant/releases/download/v0.5.0/"
PREVIOUS = {
    "windows": (
        "ApplicationAssistant-Setup-0.5.0-Windows-x64.exe",
        "487b6c23a3986fecac6fdaff09e98116c6413191b7d0b60eff7eaefe6f4fa7ee",
    ),
    "linux": (
        "ApplicationAssistant-0.5.0-Linux-x64.tar.gz",
        "989c4cfbac443c8f80504c6aeade5c83875734e73fde0a5c64185833e7f3ead7",
    ),
}
PASSWORD = "ci-only-upgrade-password-123"
AI_KEY = "ci-test-key-never-used-externally"


def previous_package(platform, root):
    name, digest = PREVIOUS[platform]
    path = root / name
    with urlopen(BASE + name, timeout=90) as response, path.open("wb") as output:
        shutil.copyfileobj(response, output)
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != digest:
            raise RuntimeError(
                "O pacote anterior não corresponde ao SHA-256 publicado."
            )
    return path


def install(platform, package, root, env, *, previous=False):
    if platform == "windows":
        app_path = root / "program"
        subprocess.run(
            [
                str(package),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                f"/DIR={app_path}",
            ],
            check=True,
            timeout=180,
        )
        return app_path / "ApplicationAssistant.exe"
    with tempfile.TemporaryDirectory(dir=root) as staging:
        with tarfile.open(package) as archive:
            if previous:
                # The published Linux 0.5.0 included the build virtualenv as its
                # runtime. Install exactly its app and UI, using the runner's
                # interpreter to create the database with the previous code.
                members = (
                    item
                    for item in archive
                    if not item.name.startswith("ApplicationAssistant-Linux/runtime/")
                )
                archive.extractall(staging, members=members, filter="data")
            else:
                archive.extractall(staging, filter="data")
        subprocess.run(
            [str(Path(staging) / "ApplicationAssistant-Linux" / "Instalar.sh")],
            env=env,
            check=True,
            timeout=120,
        )
    return Path(env["XDG_DATA_HOME"]) / "ApplicationAssistant" / "Iniciar.sh"


@contextmanager
def app_session(command, env, version, log):
    windows = sys.platform == "win32"
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if windows else 0
    with log.open("w+", encoding="utf-8", errors="replace") as output:
        process = subprocess.Popen(
            command, env=env, stdout=output, stderr=output, creationflags=flags
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{env['AA_PORT']}",
                headers={"X-AA-Request": "1"},
                timeout=90,
                trust_env=False,
            ) as client:
                for _ in range(180):
                    if process.poll() is not None:
                        raise RuntimeError(
                            "O processo instalado encerrou na inicialização."
                        )
                    try:
                        health = client.get("/api/health", timeout=1)
                    except httpx.TransportError:
                        time.sleep(0.5)
                        continue
                    assert health.raise_for_status().json()["version"] == version
                    assert (
                        client.get("/")
                        .raise_for_status()
                        .text.find("Application Assistant")
                        >= 0
                    )
                    break
                else:
                    raise RuntimeError("A instalação não respondeu dentro do prazo.")
                yield client
        except Exception:
            output.seek(0)
            print(output.read(), file=sys.stderr)
            raise
        finally:
            if process.poll() is None:
                try:
                    if windows:
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        process.terminate()
                    process.wait(timeout=20)
                except (OSError, subprocess.TimeoutExpired):
                    if windows:
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            capture_output=True,
                            timeout=10,
                            check=False,
                        )
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=10)


def write_test_data(client):
    client.post("/api/setup", json={"password": PASSWORD}).raise_for_status()
    settings = client.get("/api/state").raise_for_status().json()["settings"]
    payload = {k: v for k, v in settings.items() if not k.endswith("_configured")}
    client.put(
        "/api/settings",
        json={**payload, "ai_key": AI_KEY, "ai_model": "preservar-modelo"},
    ).raise_for_status()
    stream = io.BytesIO()
    canvas = Canvas(stream)
    canvas.drawString(
        40, 770, "Perfil de teste da atualizacao: experiencia em Python por tres anos."
    )
    canvas.save()
    document = stream.getvalue()
    client.post(
        "/api/profile/pdf",
        files={"file": ("Perfil de teste.pdf", document, "application/pdf")},
    ).raise_for_status()
    client.put(
        "/api/profile", json={"name": "Pessoa Teste", "email": "qa@example.com"}
    ).raise_for_status()
    job = (
        client.post(
            "/api/jobs",
            json={
                "title": "Desenvolvedor Python",
                "company": "Empresa fictícia",
                "url": "https://example.com/vagas/python",
                "description": "Esta oportunidade local existe apenas para verificar o banco.",
            },
        )
        .raise_for_status()
        .json()["job"]
    )
    return job["id"], document


def verify_upgrade(platform, package, version, root):
    prior = previous_package(platform, root)
    data = root / "user-data"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {
        **os.environ,
        "AA_DATA_DIR": str(data),
        "XDG_DATA_HOME": str(root / "xdg"),
        "AA_PORT": str(port),
        "AA_NO_BROWSER": "1",
    }
    # Point the installed app at its own bundled Chromium.
    env.pop("PLAYWRIGHT_BROWSERS_PATH", None)
    launcher = install(platform, prior, root, env, previous=True)
    if platform == "linux":
        previous_command = [sys.executable, str(launcher.parent / "app/launcher.py")]
    else:
        previous_command = [str(launcher)]
    with app_session(previous_command, env, "0.5.0", root / "old.log") as client:
        job_id, document = write_test_data(client)
    store = Store(data)
    job = store.get("jobs", job_id)
    record_stage(job, "submitted_manual", "manual")
    record_stage(job, "interview", "manual")
    store.put("jobs", job, job_id)
    original_key = (data / "vault.key").read_bytes()

    assert install(platform, package, root, env) == launcher
    with app_session([str(launcher)], env, version, root / "new.log") as client:
        client.post("/api/login", json={"password": PASSWORD}).raise_for_status()
        state = client.get("/api/state").raise_for_status().json()
        assert state["profile"]["name"] == "Pessoa Teste"
        assert state["settings"]["ai_key_configured"]
        assert state["settings"]["ai_model"] == "preservar-modelo"
        assert state["settings"]["ai_key"] == ""
        assert state["pdf_filename"] == "Curriculo.pdf"
        assert client.get("/api/profile/pdf").raise_for_status().content == document
        saved_job = next(row for row in state["jobs"] if row["id"] == job_id)
        assert saved_job["status"] == "interview"
        assert [item["status"] for item in saved_job["stage_history"]] == [
            "submitted_manual",
            "interview",
        ]
        assert state["metrics"]["applied"] == 1
        assert client.post("/api/browser/self-test").raise_for_status().json()["ok"]
    assert (data / "vault.key").read_bytes() == original_key
    assert Store(data).get("settings")["ai_key"] == AI_KEY
    print(
        f"Upgrade 0.5.0 to {version} ({platform}): password, key, PDF, profile, application and history preserved."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=PREVIOUS)
    parser.add_argument("package", type=Path)
    parser.add_argument("version")
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(
        prefix="aa-upgrade-", ignore_cleanup_errors=sys.platform == "win32"
    ) as temporary:
        verify_upgrade(
            options.platform,
            options.package.resolve(),
            options.version,
            Path(temporary),
        )
