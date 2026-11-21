import { useState } from "react";
import { Play, Pause, CheckCircle2, TriangleAlert } from "lucide-react";
import { api } from "./api";
import { editableSettings } from "./types";
import type { AppState, Settings } from "./types";
type Props = {
  state: AppState;
  act: (task: () => Promise<unknown>, message?: string) => Promise<void>;
  busy: boolean;
  go: (page: string) => void;
};
const format = (date: string) => new Date(date).toLocaleString("pt-BR");

export function RunSummary({ state }: { state: AppState }) {
  const run = state.runs[0];
  if (!run) return null;
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>
            {run.status === "running"
              ? "Sua rotina está trabalhando"
              : "Resumo da última execução"}
          </h2>
          <p>
            {format(run.started_at)} ·{" "}
            {run.status === "running"
              ? "Em execução"
              : run.status === "completed"
                ? "Concluída"
                : run.status === "time_limit"
                  ? "Limite de duração atingido"
                  : run.status === "paused"
                    ? "Pausada"
                    : "Interrompida"}
          </p>
        </div>
        {(run.pending || 0) > 0 ||
        run.errors.length > 0 ||
        run.status === "failed" ? (
          <TriangleAlert size={21} />
        ) : (
          <CheckCircle2 size={21} />
        )}
      </div>
      <div className="stats-grid">
        {[
          ["Encontradas", run.found ?? "—"],
          ["Aderentes", run.eligible ?? "—"],
          ["Concluídas pelo conector", run.sent],
          ["Pendências", run.pending ?? "—"],
        ].map(([label, value]) => (
          <div className="stat" key={label}>
            <div>{label}</div>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <p>
        <small>
          {run.imported} novas · {run.duplicates ?? 0} já conhecidas ·{" "}
          {run.analyzed} avaliadas, incluindo análises reaproveitadas. Aceite
          SMTP não confirma recebimento ou cadastro num portal.
        </small>
      </p>
      {run.errors.map((error, index) => (
        <p className="notice" key={index}>
          {error}
        </p>
      ))}
    </section>
  );
}
export function AutomationPanel({ state, act, busy, go }: Props) {
  const [s, setS] = useState(state.settings);
  const change = (key: keyof Settings, value: unknown) =>
    setS((x) => ({ ...x, [key]: value }));
  const toggle = (
    key: "search_platforms" | "allowed_destinations",
    id: string,
  ) =>
    change(
      key,
      s[key].includes(id) ? s[key].filter((x) => x !== id) : [...s[key], id],
    );
  const metrics = state.metrics;
  const checks = [
    ["Perfil confirmado", state.profile.confirmed],
    ["IA e consentimento configurados", !!s.ai_model && s.ai_consent],
    ["Modo automático escolhido", s.mode === "automatic"],
    [
      "Envio de e-mail habilitado",
      s.email_enabled && s.allowed_destinations.includes("email"),
    ],
    ["Fonte de busca cadastrada", s.sources.some((x) => x.enabled)],
    ["Agenda habilitada", s.schedule_enabled],
    ["Rotina sem pausa", !s.paused],
  ] as const;
  return (
    <>
      <RunSummary state={state} />
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Seu histórico nos últimos {metrics.days} dias</h2>
            <p>
              Candidaturas registradas nesse período e a etapa atual de cada
              uma.
            </p>
          </div>
        </div>
        <div className="stats-grid">
          {[
            ["Candidaturas", metrics.applied],
            ["Com retorno", metrics.responses],
            ["Em teste técnico", metrics.current.technical || 0],
            ["Com gestor", metrics.current.manager_interview || 0],
          ].map(([label, value]) => (
            <div className="stat" key={label}>
              <div>{label}</div>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
        <p>
          <small>
            {metrics.browser_confirmed || 0} confirmadas por portal ·{" "}
            {metrics.smtp_accepted} com aceite SMTP · {metrics.reported_manual}{" "}
            envios informados manualmente · {metrics.current.interview || 0} em
            entrevista · {metrics.pending} pendências atuais. Estes números não
            representam submissões automáticas em LinkedIn, Gupy ou Indeed.
          </small>
        </p>
      </section>
      <div className="content-grid">
        <form
          className="panel"
          onSubmit={(event) => {
            event.preventDefault();
            act(
              () => api("/settings", "PUT", editableSettings(s)),
              "Preferências de automação salvas.",
            );
          }}
        >
          <h2>Configurar uma vez, acompanhar depois</h2>
          <label className="field">
            <span>Autonomia</span>
            <select
              value={s.mode}
              onChange={(e) => change("mode", e.target.value)}
            >
              <option value="review">Aprovar cada candidatura</option>
              <option value="automatic">
                Enviar automaticamente nos conectores disponíveis
              </option>
            </select>
          </label>
          <div className="form-grid">
            <label className="field">
              <span>Aderência mínima (%)</span>
              <input
                type="number"
                min={0}
                max={100}
                value={s.threshold}
                onChange={(e) => change("threshold", Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>Duração máxima da rotina (minutos)</span>
              <input
                type="number"
                min={1}
                max={240}
                value={s.run_time_limit_minutes}
                onChange={(e) =>
                  change("run_time_limit_minutes", Number(e.target.value))
                }
              />
            </label>
          </div>
          <label className="toggle-row">
            <span>
              <strong>Classificar áreas por regras de cargo conhecidas</strong>
              <small>
                Permite processar fontes sem confirmar cada área manualmente.
                Cargos ambíguos e critérios desconhecidos continuam pendentes;
                áreas excluídas continuam bloqueadas.
              </small>
            </span>
            <input
              type="checkbox"
              checked={s.auto_classify_areas}
              onChange={(e) => change("auto_classify_areas", e.target.checked)}
            />
          </label>
          <h3>Onde pesquisar</h3>
          {state.connectors
            .filter((c) => c.id !== "email" && c.id !== "inhire")
            .map((c) => (
              <label className="toggle-row" key={c.id}>
                <span>
                  <strong>
                    {c.name} {c.discovery ? "" : "· conector pendente"}
                  </strong>
                  <small>{c.reason}</small>
                </span>
                <input
                  type="checkbox"
                  checked={s.search_platforms.includes(c.id)}
                  onChange={() => toggle("search_platforms", c.id)}
                />
              </label>
            ))}
          <h3>Onde permitir finalizar</h3>
          <p>
            Autorizar um destino não inicia buscas nele. Um destino sem conector
            validado permanece como pendência.
          </p>
          {state.connectors
            .filter((c) => c.id !== "feed")
            .map((c) => (
              <label className="toggle-row" key={c.id}>
                <span>
                  <strong>
                    {c.name}{" "}
                    {c.submission
                      ? "· envio disponível"
                      : "· finalização assistida"}
                  </strong>
                </span>
                <input
                  type="checkbox"
                  checked={s.allowed_destinations.includes(c.id)}
                  onChange={() => toggle("allowed_destinations", c.id)}
                />
              </label>
            ))}
          <button className="primary" disabled={busy}>
            Salvar preferências
          </button>
        </form>
        <section className="panel aside-note">
          <h2>Preparação da rotina</h2>
          {checks.map(([label, done]) => (
            <p key={label}>
              {done ? "✓" : "○"} {label}
            </p>
          ))}
          <div className="stack">
            <button className="secondary" onClick={() => go("profile")}>
              Revisar perfil
            </button>
            <button className="secondary" onClick={() => go("settings")}>
              Configurar fontes, IA e e-mail
            </button>
            <button className="secondary" onClick={() => go("schedule")}>
              Definir dias e horário
            </button>
            <button
              className="primary"
              disabled={busy || state.running}
              onClick={() =>
                act(() => api("/runs", "POST"), "Rotina iniciada.")
              }
            >
              <Play size={16} />
              Executar agora
            </button>
            <button
              className="secondary"
              disabled={busy || state.settings.paused}
              onClick={() =>
                act(() => api("/pause", "POST"), "Rotina pausada.")
              }
            >
              <Pause size={16} />
              Pausar
            </button>
          </div>
        </section>
      </div>
      <section className="panel">
        <h2>Pendências que precisam de você</h2>
        {state.jobs
          .filter(
            (j) =>
              j.pending_reason &&
              ![
                "sent",
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
          )
          .slice(0, 20)
          .map((j) => (
            <div className="followup-row" key={j.id}>
              <div>
                <strong>
                  {j.title} — {j.company}
                </strong>
                <small>{j.pending_reason}</small>
              </div>
              <button className="secondary" onClick={() => go("jobs")}>
                Ver oportunidades
              </button>
            </div>
          ))}
        {!state.jobs.some((j) => j.pending_reason) && (
          <p>Nenhuma pendência registrada.</p>
        )}
      </section>
      <section className="panel">
        <h2>Fontes consultadas na última execução</h2>
        {(state.runs[0]?.sources || []).map((source, index) => (
          <p key={index}>
            <strong>{source.name}</strong> · {source.found} encontradas ·{" "}
            {source.new} novas · {source.duplicates} conhecidas ·{" "}
            {source.status === "completed" ? "concluída" : "falha na consulta"}
          </p>
        ))}
        {!state.runs[0]?.sources?.length && (
          <p>Nenhuma fonte consultada neste registro.</p>
        )}
      </section>
    </>
  );
}
