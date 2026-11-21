import { useState } from "react";
import { api } from "./api";
import type { AppState, Job } from "./types";

type Props = {
  state: AppState;
  busy: boolean;
  act: (task: () => Promise<unknown>, message?: string) => Promise<void>;
  openBrowser: (target: { platform: string; job_id: string }) => void;
  go: (page: string) => void;
};
export function Worklist({ state, busy, act, openBrowser, go }: Props) {
  const [query, setQuery] = useState("");
  const [visible, setVisible] = useState(20);
  const [minimum, setMinimum] = useState(state.settings.threshold);
  const [platform, setPlatform] = useState("");
  const [tab, setTab] = useState("eligible");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const entries = new Map(state.worklist.items.map((e) => [e.job_id, e]));
  const active = state.jobs.filter(
    (j) =>
      ![
        "sent",
        "sending",
        "uncertain",
        "submitted_manual",
        "receipt",
        "selection",
        "technical",
        "interview",
        "manager_interview",
        "offer",
        "rejected",
        "withdrawn",
        "closed",
      ].includes(j.status),
  );
  const rows = active
    .filter((j) =>
      tab === "archived"
        ? j.archived
        : !j.archived &&
          (tab === "review" ? !entries.has(j.id) : entries.has(j.id)),
    )
    .filter(
      (j) =>
        (!query ||
          `${j.title} ${j.company} ${j.description}`
            .toLocaleLowerCase()
            .includes(query.toLocaleLowerCase())) &&
        (!platform ||
          entries.get(j.id)?.destination === platform ||
          j.origins?.some((o) => o.platform === platform)),
    )
    .filter(
      (j) =>
        tab !== "eligible" ||
        (entries.get(j.id)?.score || 0) >=
          Math.max(minimum, state.settings.threshold),
    )
    .sort(
      (a, b) =>
        (entries.get(b.id)?.score || 0) - (entries.get(a.id)?.score || 0),
    );
  const sourceNames = Object.fromEntries(
    state.connectors.map((c) => [c.id, c.name]),
  );
  async function open(job: Job) {
    const target = await api<{ platform: string; job_id: string }>(
      `/jobs/${job.id}/browser/open`,
      "POST",
    );
    openBrowser(target);
  }
  return (
    <>
      <section className="panel">
        <h2>Uma fila para todas as suas oportunidades</h2>
        <p>
          Busque em fontes selecionadas, consulte vagas e publicações, prepare o
          currículo e conclua a candidatura pelo destino indicado. A busca
          abaixo apenas consolida; não envia candidaturas.
        </p>
        <div className="button-row">
          <button
            className="primary"
            disabled={busy || state.running || state.settings.paused}
            onClick={() =>
              act(
                () => api("/runs", "POST", { action: "collect" }),
                "Busca iniciada. As vagas serão consolidadas sem envio.",
              )
            }
          >
            Buscar e consolidar agora
          </button>
          <button onClick={() => go("autopilot")}>
            Configurar fontes e modo automático
          </button>
          <button onClick={() => go("jobs")}>
            Importar vaga ou revisar cadastro
          </button>
        </div>
        {state.settings.paused && (
          <p className="notice">
            A rotina está pausada. Retome em Rotina automática para iniciar a
            busca. Você pode consultar e usar manualmente as vagas já
            consolidadas.
          </p>
        )}
        <p>
          {state.worklist.summary.eligible} aderentes ·{" "}
          {state.worklist.summary.stale} sem análise atual ·{" "}
          {state.worklist.summary.blocked} com informações ou critérios a
          revisar · {state.worklist.summary.below_threshold} abaixo dos limites
        </p>
        <div className="form-grid">
          <label>
            Buscar por cargo, empresa ou texto
            <input value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          <label>
            Origem ou destino
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
            >
              <option value="">Todos</option>
              {state.connectors.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Aderência mínima na lista
            <input
              type="number"
              min={state.settings.threshold}
              max={100}
              value={minimum}
              onChange={(e) => setMinimum(Number(e.target.value))}
            />
          </label>
          <label>
            Mostrar
            <select value={tab} onChange={(e) => setTab(e.target.value)}>
              <option value="eligible">Aderentes e prontas</option>
              <option value="review">Revisar informações ou análise</option>
              <option value="archived">Arquivadas</option>
            </select>
          </label>
        </div>
        <small>
          A lista usa o mínimo configurado de {state.settings.threshold}% e
          confiança de {state.settings.minimum_confidence}%. Alterar esse filtro
          não autoriza envios com critérios menores. Fontes de navegador são
          experimentais e precisam de sessão válida; postagens sem informações
          suficientes ficam para revisão.
        </small>
      </section>
      {!rows.length && (
        <section className="panel">
          <h3>Nenhuma oportunidade neste filtro</h3>
          <p>
            Execute uma busca, configure fontes ou consulte as vagas que
            precisam de revisão. Uma execução vazia não significa que não
            existam vagas no portal.
          </p>
        </section>
      )}
      {rows.slice(0, visible).map((job) => {
        const entry = entries.get(job.id);
        return (
          <article className="panel worklist-card" key={job.id}>
            <div className="panel-heading">
              <div>
                <h2>{job.title}</h2>
                <p>
                  {job.company} · {job.location || "Local a confirmar"} ·{" "}
                  {job.modality}
                </p>
              </div>
              <strong>
                {entry ? `${entry.score}% aderência` : "Revisão necessária"}
              </strong>
            </div>
            <p>
              {entry
                ? `${entry.confidence}% de confiança · Destino: ${sourceNames[entry.destination] || entry.destination} · ${entry.automatic_available ? "Conector de envio disponível" : "Conclusão manual no portal"}`
                : "Confira informações e reanalise antes de gerar o currículo desta vaga."}
            </p>
            <p>
              {job.source.endsWith("_post")
                ? "Descoberta em uma publicação"
                : "Anúncio de vaga"}{" "}
              ·{" "}
              <a href={job.url} target="_blank" rel="noreferrer">
                Ver origem
              </a>{" "}
              {job.application_url && (
                <>
                  {" "}
                  ·{" "}
                  <a
                    href={job.application_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Destino da candidatura
                  </a>
                </>
              )}
            </p>
            <details>
              <summary>Descrição completa, instruções e análise</summary>
              <p className="vacancy-description">{job.description}</p>
              {job.analysis?.criteria &&
                Object.entries(job.analysis.criteria).map(([name, c]) => (
                  <p key={name}>
                    <strong>
                      {name}: {c.grade}%
                    </strong>{" "}
                    — {c.reason}
                    <br />
                    <q>{c.job_quote}</q>
                  </p>
                ))}
              {job.analysis?.gaps && <p>Lacunas: {job.analysis.gaps}</p>}
              {job.analysis?.blocks.map((b, i) => (
                <p key={i} className="notice">
                  {b}
                </p>
              ))}
            </details>
            {job.recipient && (
              <p>
                Envio por e-mail: <strong>{job.recipient}</strong>
                {job.email_subject && (
                  <>
                    {" "}
                    · Assunto: <strong>{job.email_subject}</strong>
                  </>
                )}
              </p>
            )}
            {job.pending_reason && (
              <p className="notice">{job.pending_reason}</p>
            )}
            <div className="button-row">
              <button
                disabled={busy || !!job.archived}
                onClick={() =>
                  act(
                    () => api(`/jobs/${job.id}/analyze`, "POST"),
                    "Análise atualizada. O currículo usa os fatos selecionados para esta posição.",
                  )
                }
              >
                Analisar e preparar currículo
              </button>
              {entry && (
                <>
                  <a
                    className="secondary"
                    href={`/api/jobs/${job.id}/resume`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Ver currículo PDF desta vaga
                  </a>
                  {entry.destination !== "email" && (
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() =>
                        act(
                          () => open(job),
                          "Vaga aberta no navegador da aplicação.",
                        )
                      }
                    >
                      Candidatar-me pelo navegador
                    </button>
                  )}
                  {entry.destination === "email" && (
                    <button onClick={() => go("jobs")}>
                      Revisar e enviar e-mail na aplicação
                    </button>
                  )}
                  <button
                    disabled={busy || job.approved}
                    onClick={() =>
                      act(
                        () => api(`/jobs/${job.id}/approve`, "POST"),
                        "Versão aprovada para o modo com revisão.",
                      )
                    }
                  >
                    {job.approved ? "Aprovada" : "Aprovar para a rotina"}
                  </button>
                </>
              )}
              <button
                disabled={busy}
                onClick={() =>
                  act(
                    () =>
                      api(`/jobs/${job.id}/archive`, "POST", {
                        archived: !job.archived,
                      }),
                    job.archived
                      ? "Vaga restaurada."
                      : "Vaga arquivada. A rotina não se candidatará nela.",
                  )
                }
              >
                {job.archived ? "Restaurar" : "Não tenho interesse / arquivar"}
              </button>
            </div>
            {entry && (
              <details>
                <summary>Já concluí a candidatura manualmente</summary>
                <p>
                  Abrir a vaga ou anexar o currículo não confirma o envio.
                  Registre somente depois de conferir a conclusão no portal.
                </p>
                <label>
                  Observação do envio
                  <input
                    value={notes[job.id] || ""}
                    onChange={(e) =>
                      setNotes({ ...notes, [job.id]: e.target.value })
                    }
                    placeholder="Ex.: envio confirmado na página da empresa"
                  />
                </label>
                <button
                  disabled={busy || (notes[job.id] || "").trim().length < 5}
                  onClick={() =>
                    act(
                      () =>
                        api(`/jobs/${job.id}/status`, "POST", {
                          status: "submitted_manual",
                          note: notes[job.id],
                        }),
                      "Conclusão manual registrada no histórico.",
                    )
                  }
                >
                  Registrar que concluí no portal
                </button>
              </details>
            )}
          </article>
        );
      })}
      {rows.length > visible && (
        <button onClick={() => setVisible((v) => v + 20)}>
          Mostrar mais {Math.min(20, rows.length - visible)} vagas
        </button>
      )}
    </>
  );
}
