import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { AppState } from "./types";

type Session = {
  id: string;
  open: boolean;
  saved_at?: string;
  busy: boolean;
  controlled: boolean;
  job_id?: string;
  handoff?: { platform: string };
};
export function BrowserPage({
  state,
  refresh,
  target,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
  target?: { platform: string; job_id: string } | null;
}) {
  const [platform, setPlatform] = useState(target?.platform || "linkedin");
  const [url, setUrl] = useState("");
  const [files, setFiles] = useState<
    { id: string; label: string; accept: string }[]
  >([]);
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
  const load = useCallback(
    () => api<Session[]>("/browser").then(setSessions),
    [],
  );
  useEffect(() => {
    const timer = setInterval(() => load().catch(() => {}), 4000);
    load().catch(() => setMessage("Não foi possível consultar as sessões."));
    return () => clearInterval(timer);
  }, [load]);
  useEffect(() => {
    setControlled(false);
    setFiles([]);
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
        if (value.notice) {
          setMessage(value.notice);
          setFiles([]);
        }
        if (Array.isArray(value.file_fields)) {
          setFiles(value.file_fields);
          if (!value.file_fields.length)
            setMessage(
              "Nenhum campo de arquivo encontrado. Abra a etapa do currículo e tente novamente.",
            );
        }
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
  }, [platform, load]);
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
  const current = sessions.find((s) => s.id === platform);
  const currentJob = state.jobs.find((j) => j.id === current?.job_id);
  return (
    <section className="card browser-panel">
      <h2>Navegador da aplicação</h2>
      <button
        disabled={busy}
        onClick={() =>
          action(async () => {
            const test = await api<{ ok: boolean; version: string }>(
              "/browser/self-test",
              "POST",
            );
            if (!test.ok)
              throw new Error("Navegador não concluiu o diagnóstico.");
            return { reason: "Chromium disponível: " + test.version };
          })
        }
      >
        Testar navegador instalado
      </button>
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
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
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
      {current?.handoff && (
        <div className="notice">
          <p>
            A vaga direcionou para {current.handoff.platform}. Libere o controle
            e continue no navegador desse portal; a conta e a sessão são
            separadas.
          </p>
          <button
            disabled={controlled || busy}
            onClick={() =>
              action(async () => {
                const next = await api<{ platform: string }>(
                  `/browser/${platform}/handoff`,
                  "POST",
                );
                setPlatform(next.platform);
                return next;
              })
            }
          >
            Continuar no portal de destino
          </button>
        </div>
      )}
      {currentJob && (
        <section className="panel">
          <h3>Currículo para {currentJob.title}</h3>
          <p>
            {currentJob.company}. Abra a etapa de anexo, assuma o controle e
            localize o campo do currículo. O envio final continua sob seu
            controle.
          </p>
          <a
            href={`/api/jobs/${currentJob.id}/resume`}
            target="_blank"
            rel="noreferrer"
          >
            Conferir PDF específico desta vaga
          </a>
          <div className="button-row">
            <button
              disabled={!controlled}
              onClick={() => {
                setFiles([]);
                send({ type: "file-fields" });
              }}
            >
              Localizar campo de currículo
            </button>
          </div>
          {files.map((field) => (
            <div key={field.id}>
              <strong>{field.label}</strong>
              <small> {field.accept || "Formato não informado"}</small>
              <button
                disabled={!controlled}
                aria-label={"Anexar currículo em " + field.label}
                onClick={() =>
                  send({
                    type: "attach-resume",
                    job_id: currentJob.id,
                    field_id: field.id,
                  })
                }
              >
                Anexar currículo neste campo
              </button>
            </div>
          ))}
        </section>
      )}
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
        manual neste navegador. LinkedIn e Indeed têm busca experimental; o
        preenchimento e envio automático desses portais ainda não está
        disponível.
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
