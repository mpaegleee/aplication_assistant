import { useState } from "react";
import { Play, Pause, CheckCircle2, TriangleAlert } from "lucide-react";
import { ActionFeedback, type Action, type Feedback } from "./ActionFeedback";
import { api } from "./api";
import { editableSettings } from "./types";
import type { AppState, Settings } from "./types";
type Props = {
  state: AppState;
  act: Action;
  busy: boolean;
  go: (page: string) => void;
  setup?: boolean;
};
const format = (date: string) => new Date(date).toLocaleString("pt-BR");

export function RunSummary({ state }: { state: AppState }) {
  const run = state.runs[0];
  if (!run) return null;
  const warnings = [...new Set(run.errors)];
  const blocked =
    run.status === "blocked" ||
    (run.status === "completed" &&
      (run.found ?? 0) === 0 &&
      warnings.length > 0 &&
      !run.sources?.some((source) => source.status === "completed"));
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
            {run.action === "collect"
              ? "Coleta sem envio · "
              : "Execução com candidaturas · "}
            {format(run.started_at)} ·{" "}
            {run.status === "running"
              ? "Em execução"
              : blocked
                ? "Busca bloqueada"
                : run.status === "completed"
                  ? warnings.length > 0
                    ? "Concluída com avisos"
                    : "Concluída"
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
      {warnings.length > 0 && (
        <div className="notice" role="status">
          <strong>
            {blocked ? "O que impediu a busca" : "Avisos da busca"}
          </strong>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="stats-grid">
        {[
          ["Encontradas", run.found ?? "—"],
          ["Aderentes", run.eligible ?? "—"],
          ["Fora do filtro de data", run.skipped_age || 0],
          ["Concluídas pelo conector", run.sent],
          ["Consolidadas sem envio", run.consolidated ?? 0],
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
    </section>
  );
}
export function AutomationPanel({ state, act, busy, go, setup }: Props) {
  const [s, setS] = useState(state.settings);
  const [saveFeedback, setSaveFeedback] = useState<Feedback | null>(null);
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
    ["Fonte de busca habilitada", !!state.configured_sources?.length],
    ["Agenda habilitada", s.schedule_enabled],
    ["Rotina sem pausa", !s.paused],
  ] as const;
  return (
    <>
      {!setup && (
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
                {metrics.smtp_accepted} com aceite SMTP ·{" "}
                {metrics.reported_manual} envios informados manualmente ·{" "}
                {metrics.current.interview || 0} em entrevista ·{" "}
                {metrics.pending} pendências atuais. Estes números não
                representam submissões automáticas em LinkedIn, Gupy ou Indeed.
              </small>
            </p>
          </section>
        </>
      )}
      <div className="content-grid">
        <form
          className="panel"
          onSubmit={(event) => {
            event.preventDefault();
            act(
              () => api("/settings", "PUT", editableSettings(s)),
              "Preferências de automação salvas.",
              setSaveFeedback,
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
              <option value="manual">
                Somente consolidar; eu me candidato
              </option>
              <option value="review">Automatizar após minha aprovação</option>
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
          <label className="field">
            <span>Idade máxima da publicação</span>
            <select
              value={s.max_job_age_days}
              onChange={(e) =>
                change("max_job_age_days", Number(e.target.value))
              }
            >
              <option value={7}>Últimos 7 dias</option>
              <option value={15}>Últimos 15 dias</option>
              <option value={30}>Últimos 30 dias</option>
            </select>
          </label>
          <label className="toggle-row">
            <span>
              <strong>Incluir vagas sem data de publicação</strong>
              <small>
                Desmarque para poupar chamadas à IA quando a fonte não informa a
                data.
              </small>
            </span>
            <input
              type="checkbox"
              checked={s.include_undated_jobs}
              onChange={(e) => change("include_undated_jobs", e.target.checked)}
            />
          </label>
          <h3>Termos da busca nos portais</h3>
          <label className="field">
            <span>
              Um cargo ou expressão por linha. Em branco, a busca usa os três
              primeiros cargos do perfil.
            </span>
            <textarea
              value={s.browser_search_queries.join("\n")}
              onChange={(e) =>
                change("browser_search_queries", e.target.value.split("\n"))
              }
              onBlur={() =>
                change(
                  "browser_search_queries",
                  s.browser_search_queries.map((q) => q.trim()).filter(Boolean),
                )
              }
            />
          </label>
          {s.search_platforms.includes("linkedin") && (
            <label className="field">
              <span>Como encontrar vagas do LinkedIn</span>
              <select
                value={s.linkedin_search_method || "browser"}
                onChange={(event) =>
                  change("linkedin_search_method", event.target.value)
                }
              >
                <option value="browser">
                  Pesquisar pelo navegador interno
                </option>
                <option value="email">
                  Importar alertas do LinkedIn por e-mail
                </option>
              </select>
              {s.linkedin_search_method === "email" && (
                <small>
                  Ative alertas por e-mail no LinkedIn e configure a leitura
                  IMAP. A busca usará os alertas recebidos.
                </small>
              )}
            </label>
          )}
          {s.linkedin_search_method !== "email" && (
            <label className="toggle-row">
              <span>
                Incluir publicações do LinkedIn com oportunidades e instruções
                de e-mail
              </span>
              <input
                type="checkbox"
                checked={s.linkedin_posts_enabled}
                onChange={(e) =>
                  change("linkedin_posts_enabled", e.target.checked)
                }
              />
            </label>
          )}
          <p>
            O LinkedIn pode usar alertas do e-mail ou o navegador interno. O
            Indeed usa o navegador e a sessão salva. A Gupy pesquisa no portal
            público sem exigir conta. Para se candidatar, entre na Gupy.
          </p>
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
          <label className="toggle-row">
            <span>
              <strong>Usar formulários automáticos experimentais</strong>
              <small>
                LinkedIn, Gupy e Indeed: somente etapas reconhecidas, respostas
                salvas e currículo confirmado. Login, cadastro de conta e etapas
                desconhecidas exigem intervenção. Ainda sem validação nos
                portais reais.
              </small>
            </span>
            <input
              type="checkbox"
              checked={s.experimental_portal_submission}
              onChange={(e) =>
                change("experimental_portal_submission", e.target.checked)
              }
            />
          </label>
          <h3>Onde permitir finalizar</h3>
          <p>
            Autorizar um destino não inicia buscas nele. Um destino sem conector
            validado permanece como pendência.
          </p>
          <label className="toggle-row">
            <span>
              <strong>
                Autorizar o compartilhamento com empresas nos portais de destino
                habilitados
              </strong>
              <small>
                Permite preencher dados pessoais e anexar o currículo para essas
                empresas. Uma recusa salva para um domínio continua valendo.
              </small>
            </span>
            <input
              type="checkbox"
              checked={s.share_with_enabled_portals}
              onChange={(e) =>
                change("share_with_enabled_portals", e.target.checked)
              }
            />
          </label>
          {state.connectors
            .filter((c) => c.id !== "feed")
            .map((c) => (
              <label className="toggle-row" key={c.id}>
                <span>
                  <strong>
                    {c.name}{" "}
                    {c.experimental
                      ? "· formulário experimental"
                      : c.submission
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
          <ActionFeedback feedback={saveFeedback} />
        </form>
        <section className="panel aside-note">
          <h2>Preparação da rotina</h2>
          {checks.map(([label, done]) => (
            <p key={label}>
              {done ? "✓" : "○"} {label}
            </p>
          ))}
          <div className="stack">
            <button className="secondary" onClick={() => go("worklist")}>
              Ver vagas consolidadas
            </button>
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
