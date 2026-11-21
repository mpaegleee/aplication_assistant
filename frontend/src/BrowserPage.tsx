import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { AppState } from "./types";

type Session = {
  id: string;
  open: boolean;
  saved_at?: string;
  busy: boolean;
  controlled: boolean;
};
export function BrowserPage({
  state,
  refresh,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
}) {
  const [platform, setPlatform] = useState("linkedin");
  const [url, setUrl] = useState("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [image, setImage] = useState("");
  const [controlled, setControlled] = useState(false);
  const [connected, setConnected] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const socket = useRef<WebSocket | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const send = (value: object) => {
    if (socket.current?.readyState === WebSocket.OPEN)
      socket.current.send(JSON.stringify(value));
  };
  const load = () => api<Session[]>("/browser").then(setSessions);
  useEffect(() => {
    load().catch(() => setMessage("Não foi possível consultar as sessões."));
  }, []);
  useEffect(() => {
    setControlled(false);
    setConnected(false);
    setImage("");
    setMessage("");
    let previous = "";
    const ws = new WebSocket(
      `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/browser/${platform}/view`,
    );
    ws.binaryType = "blob";
    socket.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onmessage = (event) => {
      if (event.data instanceof Blob) {
        if (previous) URL.revokeObjectURL(previous);
        previous = URL.createObjectURL(event.data);
        setImage(previous);
      } else {
        const value = JSON.parse(event.data);
        if (value.error) setMessage(value.error);
        if (typeof value.controlled === "boolean") {
          setControlled(value.controlled);
          load().catch(() => {});
        }
      }
    };
    ws.onclose = () => {
      setControlled(false);
      setConnected(false);
    };
    ws.onerror = () =>
      setMessage("Conexão com o navegador interrompida. Reabra esta tela.");
    return () => {
      ws.close();
      if (previous) URL.revokeObjectURL(previous);
    };
  }, [platform]);
  async function action(task: () => Promise<unknown>) {
    setBusy(true);
    setMessage("");
    try {
      const result = (await task()) as { reason?: string };
      setMessage(result?.reason || "Operação concluída.");
      await load();
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Operação não concluída.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card browser-panel">
      <h2>Navegador da aplicação</h2>
      <p>
        Faça login diretamente no portal. Ao liberar o controle ou sair desta
        tela, os cookies e dados de sessão do portal são salvos criptografados
        nesta instalação. O portal pode pedir um novo login ou verificação.
      </p>
      <div className="form-grid">
        <label>
          Portal
          <select
            value={platform}
            onChange={(e) => {
              setPlatform(e.target.value);
              setUrl("");
            }}
          >
            <option value="linkedin">LinkedIn</option>
            <option value="gupy">Gupy</option>
            <option value="indeed">Indeed</option>
            <option value="inhire">InHire</option>
          </select>
        </label>
        <label>
          Link da vaga ou página do portal (opcional, exceto InHire)
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://..."
          />
        </label>
      </div>
      <div className="button-row">
        <button
          disabled={busy || controlled}
          onClick={() =>
            action(() => api("/browser/open", "POST", { platform, url }))
          }
        >
          Abrir portal
        </button>
        <button
          disabled={!connected || controlled}
          onClick={() => send({ type: "acquire" })}
        >
          Assumir controle
        </button>
        <button
          disabled={!controlled}
          onClick={() => {
            send({ type: "release" });
            if (input.current) input.current.value = "";
          }}
        >
          Salvar sessão e liberar controle
        </button>
        <button
          disabled={busy || controlled}
          onClick={() => action(() => api(`/browser/${platform}`, "DELETE"))}
        >
          Apagar sessão local
        </button>
      </div>
      <p>
        {sessions.find((s) => s.id === platform)?.saved_at
          ? "Há uma sessão salva. Sua validade será verificada pelo próprio portal."
          : "Nenhuma sessão salva para este portal."}{" "}
        {controlled ? "Você está no controle." : "Visualização sem controle."}
      </p>
      {message && (
        <p role="status" className="banner">
          {message}
        </p>
      )}
      <div
        ref={viewport}
        className="browser-viewport"
        tabIndex={0}
        aria-label="Navegador remoto. Clique em um campo e use a caixa de digitação abaixo."
        onKeyDown={(e) => {
          if (!controlled) return;
          const key =
            (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a"
              ? "ControlOrMeta+A"
              : e.shiftKey && e.key === "Tab"
                ? "Shift+Tab"
                : e.key === " "
                  ? "Space"
                  : e.key;
          if (
            [
              "Tab",
              "Shift+Tab",
              "Enter",
              "Backspace",
              "Delete",
              "Escape",
              "ArrowDown",
              "ArrowUp",
              "ArrowLeft",
              "ArrowRight",
              "ControlOrMeta+A",
              "Space",
            ].includes(key)
          ) {
            e.preventDefault();
            send({ type: "key", key });
          }
        }}
      >
        {image ? (
          <img
            src={image}
            alt="Página atual do portal no Chromium da aplicação"
            draggable={false}
            onClick={(e) => {
              if (!controlled) return;
              const rect = e.currentTarget.getBoundingClientRect();
              send({
                type: "click",
                x: ((e.clientX - rect.left) * 1280) / rect.width,
                y: ((e.clientY - rect.top) * 800) / rect.height,
              });
              viewport.current?.focus();
            }}
          />
        ) : (
          <p>Abra o portal para ver a página.</p>
        )}
      </div>
      <div className="button-row">
        <button
          disabled={!controlled}
          onClick={() => send({ type: "scroll", delta: -600 })}
        >
          Rolar para cima
        </button>
        <button
          disabled={!controlled}
          onClick={() => send({ type: "scroll", delta: 600 })}
        >
          Rolar para baixo
        </button>
        <button
          disabled={!controlled}
          onClick={() => send({ type: "key", key: "Tab" })}
        >
          Próximo campo
        </button>
        <button
          disabled={!controlled}
          onClick={() => send({ type: "key", key: "Enter" })}
        >
          Enter
        </button>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (controlled && input.current?.value) {
            send({ type: "text", text: input.current.value });
            input.current.value = "";
            viewport.current?.focus();
          }
        }}
      >
        <label>
          Texto ou senha para o campo selecionado no portal
          <input
            ref={input}
            type="password"
            autoComplete="off"
            disabled={!controlled}
            maxLength={2000}
          />
        </label>
        <button disabled={!controlled}>Digitar no portal</button>
      </form>
      <hr />
      <h3>Candidaturas InHire</h3>
      <p>
        Versão experimental para formulários diretos. Habilite InHire nos
        destinos, confirme o perfil e analise a vaga. Salve perguntas e
        respostas exatas no perfil, incluindo pretensão salarial e
        disponibilidade. Antes de preencher, leia a política do portal e
        registre a autorização solicitada nas pendências. No modo revisão,
        aprove a vaga antes.
      </p>
      <p>
        LinkedIn, Gupy e Indeed já podem ser abertos para login e operação
        manual neste navegador. A busca e o preenchimento automático desses três
        portais ainda não estão disponíveis.
      </p>
      {state.jobs
        .filter((j) => (j.application_url || j.url).includes(".inhire.app/"))
        .map((job) => (
          <div key={job.id} className="browser-job">
            <strong>
              {job.title} — {job.company}
            </strong>
            <p>{job.pending_reason || job.status}</p>
            <div className="button-row">
              <button
                disabled={busy || controlled}
                onClick={() =>
                  action(() => api(`/jobs/${job.id}/browser/prepare`, "POST"))
                }
              >
                Preencher sem enviar
              </button>
              <button
                disabled={busy || controlled}
                onClick={() =>
                  action(() => api(`/jobs/${job.id}/browser/submit`, "POST"))
                }
              >
                Executar candidatura
              </button>
              <a
                href={`/api/jobs/${job.id}/resume`}
                target="_blank"
                rel="noreferrer"
              >
                Currículo desta vaga
              </a>
              {job.browser_confirmed && (
                <a
                  href={`/api/jobs/${job.id}/browser/proof`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Comprovante do portal
                </a>
              )}
            </div>
          </div>
        ))}
    </section>
  );
}
