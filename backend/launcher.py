"""Entrada do executável Windows e do processo Docker."""

import os, sys, threading, webbrowser, time, urllib.request
from pathlib import Path
import uvicorn
from assistant.api import create_app


def main():
    server = os.environ.get("AA_SERVER") == "1"
    if getattr(sys, "frozen", False):
        static = Path(sys._MEIPASS) / "frontend"
    else:
        static = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    app = create_app(static_dir=static)
    port = int(os.environ.get("AA_PORT", "8765"))
    if not server and os.environ.get("AA_NO_BROWSER") != "1":

        def open_ui():
            for _ in range(60):
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/api/health", timeout=1
                    ) as response:
                        if response.status == 200:
                            webbrowser.open(f"http://127.0.0.1:{port}")
                            return
                except Exception:
                    time.sleep(0.5)

        threading.Thread(target=open_ui, daemon=True).start()
    print("Application Assistant — " + f"http://127.0.0.1:{port}")
    print(
        "Mantenha esta janela aberta para executar a agenda. Ctrl+C encerra o aplicativo."
    )
    uvicorn.run(
        app,
        host="0.0.0.0" if server else "127.0.0.1",
        port=port,
        workers=1,
        access_log=False,
    )


if __name__ == "__main__":
    main()
