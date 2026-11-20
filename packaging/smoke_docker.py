"""Teste HTTP real do container local, sem IA paga ou envio de mensagens."""

import os, subprocess, secrets, time, json
import httpx

name = "aa-local-smoke-" + secrets.token_hex(4)
volume = name + "-data"
env = dict(os.environ)
env["AA_SETUP_TOKEN"] = secrets.token_urlsafe(32)


def docker(*args):
    return subprocess.check_output(
        ["docker", "--host=unix:///var/run/docker.sock", *args], env=env, text=True
    ).strip()


def start():
    docker(
        "run",
        "--detach",
        "--name",
        name,
        "-p",
        "127.0.0.1:8766:8765",
        "-e",
        "AA_SETUP_TOKEN",
        "--mount",
        f"type=volume,src={volume},dst=/data",
        "application-assistant:local-test",
    )
    for _ in range(30):
        try:
            if (
                httpx.get(
                    "http://127.0.0.1:8766/api/health", trust_env=False
                ).status_code
                == 200
            ):
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    print(docker("logs", name))
    raise RuntimeError("Container não iniciou.")


try:
    start()
    with httpx.Client(
        base_url="http://127.0.0.1:8766", headers={"X-AA-Request": "1"}, trust_env=False
    ) as client:
        assert client.get("/api/state").status_code == 401
        assert (
            client.post(
                "/api/setup",
                json={"password": "local-smoke-password", "setup_token": "wrong"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/setup",
                json={
                    "password": "local-smoke-password",
                    "setup_token": env["AA_SETUP_TOKEN"],
                },
            ).status_code
            == 200
        )
        page = client.get("/")
        assert page.status_code == 200 and "Application Assistant" in page.text
        import re

        asset = re.search(r'src="([^"]+\.js)"', page.text)[1]
        assert client.get(asset).status_code == 200
        profile = {
            "name": "Teste Local",
            "areas": ["Desenvolvimento"],
            "excluded_areas": ["Financeiro"],
            "roles": ["Desenvolvedor Python"],
            "facts": [{"id": "f1", "text": "Desenvolvi APIs em Python."}],
            "confirmed": True,
        }
        assert client.put("/api/profile", json=profile).status_code == 200
        result = client.post(
            "/api/jobs",
            json={
                "title": "Analista financeiro",
                "company": "Empresa fictícia",
                "description": "Atuar com contas a pagar e relatórios financeiros.",
                "area": "Financeiro",
                "area_reviewed": True,
                "modality": "Remoto",
            },
        )
        assert result.status_code == 200
        job_id = result.json()["job"]["id"]
        analyzed = client.post("/api/jobs/" + job_id + "/analyze")
        assert analyzed.status_code == 200 and analyzed.json()["status"] == "blocked"
        state = client.get("/api/state").json()
        assert len(state["jobs"]) == 1 and state["settings"]["paused"]
        print(
            "HTTP real: senha, token de configuração, sessão, assets, perfil, vaga e bloqueio de área: OK"
        )
    docker("stop", name)
    docker("rm", name)
    start()
    with httpx.Client(
        base_url="http://127.0.0.1:8766", headers={"X-AA-Request": "1"}, trust_env=False
    ) as client:
        assert client.get("/api/session").json()["configured"]
        assert (
            client.post(
                "/api/login", json={"password": "local-smoke-password"}
            ).status_code
            == 200
        )
        assert client.get("/api/state").json()["profile"]["name"] == "Teste Local"
    print("Reinício com volume e persistência dos dados: OK")
finally:
    subprocess.run(
        ["docker", "--host=unix:///var/run/docker.sock", "rm", "-f", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["docker", "--host=unix:///var/run/docker.sock", "volume", "rm", volume],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
