import React, { useState, useEffect, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  LayoutDashboard,
  UserRound,
  BriefcaseBusiness,
  Settings2,
  CalendarClock,
  BookOpen,
  ArrowUpRight,
  Plus,
  Search,
  Check,
  Pause,
  Play,
  Upload,
  FileText,
  Mail,
  LogOut,
  ShieldCheck,
  X,
  ChevronRight,
  CheckCircle2,
  Clock3,
  TriangleAlert,
  SlidersHorizontal,
  Download,
  RefreshCw,
  Trash2,
  Link2,
  Inbox,
} from "lucide-react";
import { ActionFeedback, type Action, type Feedback } from "./ActionFeedback";
import { api } from "./api";
import { Worklist } from "./Worklist";
import { BrowserPage } from "./BrowserPage";
import { AISettings } from "./AISettings";
import { AutomationPanel, RunSummary } from "./Automation";
import { editableJob, editableSettings, factCategories } from "./types";
import type {
  AppState,
  Profile,
  FactCategory,
  Settings,
  Job,
  JobInput,
  Followup,
} from "./types";
import "./style.css";

const statusLabels: Record<string, string> = {
  new: "Nova oportunidade",
  blocked: "Revisão necessária",
  ready: "Pronta para candidatura",
  review: "Abaixo do limite",
  sending: "Enviando",
  sent: "Aceita pelo SMTP",
  uncertain: "Resultado incerto",
  submitted_manual: "Envio informado",
  receipt: "Recebimento confirmado",
  selection: "Em seleção",
  interview: "Entrevista",
  technical: "Teste técnico",
  manager_interview: "Entrevista com gestor",
  offer: "Proposta",
  rejected: "Não selecionado",
  withdrawn: "Retirada",
  closed: "Encerrada",
};
const sentStates = [
  "sent",
  "receipt",
  "selection",
  "interview",
  "technical",
  "manager_interview",
  "offer",
  "rejected",
  "withdrawn",
  "closed",
  "submitted_manual",
];
const date = (s: string) =>
  new Date(s).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
const split = (v: string) =>
  v
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
const emptyJob: JobInput = {
  title: "",
  company: "",
  url: "",
  description: "",
  area: "",
  area_reviewed: false,
  modality: "Não informado",
  contract: "",
  location: "",
  salary: null,
  recipient: "",
  source: "manual",
};
function Badge({ status }: { status: string }) {
  return (
    <span
      className={
        "badge " +
        (["ready", "sent", "receipt", "offer"].includes(status)
          ? "green"
          : ["blocked", "uncertain"].includes(status)
            ? "amber"
            : "")
      }
    >
      {statusLabels[status] || status}
    </span>
  );
}
function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="toggle-row">
      <span>
        <strong>{label}</strong>
        {hint && <small>{hint}</small>}
      </span>
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
    </label>
  );
}
function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  const ref = React.useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button className="icon-btn" aria-label="Fechar" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
function App() {
  const [browserTarget, setBrowserTarget] = useState<{
    platform: string;
    job_id: string;
  } | null>(null);
  const [session, setSession] = useState<{
    configured: boolean;
    authenticated: boolean;
    setup_token_required: boolean;
  } | null>(null);
  const [state, setState] = useState<AppState | null>(null),
    [page, setPage] = useState("dashboard"),
    [toast, setToast] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [password, setPassword] = useState(""),
    [setupToken, setSetupToken] = useState("");
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [page]);
  const refresh = useCallback(async () => {
    setState(
      await api<AppState>("/state").then((next) => {
        if (!next.connectors || !next.metrics || !next.worklist)
          throw new Error(
            "Atualização aplicada. Encerre a janela do Iniciar.cmd, abra novamente e recarregue esta página.",
          );
        return next;
      }),
    );
  }, []);
  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 6000);
  };
  async function act(
    task: () => Promise<unknown>,
    message = "Alterações salvas.",
    report?: (feedback: Feedback) => void,
  ) {
    setBusy(true);
    setError("");
    report?.({ kind: "pending", message: "Aguarde…" });
    try {
      await task();
      const current = await api<{ authenticated: boolean }>("/session");
      if (current.authenticated) await refresh();
      if (report) report({ kind: "success", message });
      else notify(message);
    } catch (e) {
      const message = (e as Error).message;
      if (report) report({ kind: "error", message });
      else setError(message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    api<typeof session>("/session")
      .then(setSession)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (session?.authenticated) refresh().catch((e) => setError(e.message));
  }, [session?.authenticated, refresh]);
  useEffect(() => {
    if (!session?.authenticated) return;
    const id = setInterval(
      () => {
        if (!document.hidden) refresh().catch(() => {});
      },
      state?.running ? 3000 : 30000,
    );
    return () => clearInterval(id);
  }, [session?.authenticated, state?.running, refresh]);
  async function login(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(session?.configured ? "/login" : "/setup", "POST", {
        password,
        setup_token: setupToken,
      });
      setPassword("");
      if (!session?.configured) setPage("setup");
      setSession(await api("/session"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!session)
    return (
      <div className="loading">
        Conectando à sua instalação…{error && <p role="alert">{error}</p>}
      </div>
    );
  if (!session.authenticated)
    return (
      <main className="auth">
        <div className="auth-card">
          <div className="brand-mark">
            <BriefcaseBusiness />
          </div>
          <p className="eyebrow">APPLICATION ASSISTANT</p>
          <h1>
            Sua próxima oportunidade
            <br />
            começa aqui.
          </h1>
          <p>
            Menos tarefas repetidas. Mais espaço para o próximo passo da sua
            carreira.
          </p>
          <form onSubmit={login}>
            <h2>
              {session.configured
                ? "Entre na sua instalação"
                : "Vamos preparar seu espaço"}
            </h2>
            <Field
              label={
                session.configured
                  ? "Senha"
                  : "Crie uma senha (mínimo de 12 caracteres)"
              }
            >
              <input
                autoFocus
                type="password"
                autoComplete={
                  session.configured ? "current-password" : "new-password"
                }
                minLength={12}
                maxLength={256}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            {!session.configured && session.setup_token_required && (
              <Field label="Código de configuração do servidor">
                <input
                  type="password"
                  required
                  value={setupToken}
                  onChange={(e) => setSetupToken(e.target.value)}
                />
              </Field>
            )}
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            <button className="primary" disabled={busy}>
              {busy
                ? "Aguarde…"
                : session.configured
                  ? "Entrar"
                  : "Criar meu espaço"}
            </button>
          </form>
          <small>
            <ShieldCheck size={16} /> Seus dados ficam nesta instalação. O uso
            de IA é opcional e configurado por você.
          </small>
        </div>
        <div className="auth-art">
          <span>Um passo de cada vez.</span>
          <div className="orbit o1" />
          <div className="orbit o2" />
          <BriefcaseBusiness size={95} />
        </div>
      </main>
    );
  if (!state)
    return (
      <div className="loading">
        Preparando seu painel…{error && <p role="alert">{error}</p>}
      </div>
    );
  const nav = [
    ["dashboard", "Visão geral", LayoutDashboard],
    ["setup", "Configuração guiada", Settings2],
    ["autopilot", "Rotina automática", Play],
    ["profile", "Meu perfil", UserRound],
    ["worklist", "Vagas consolidadas", CheckCircle2],
    ["jobs", "Oportunidades", Search],
    ["applications", "Candidaturas", BriefcaseBusiness],
    ["followups", "Retornos", Inbox],
    ["schedule", "Agenda e execuções", CalendarClock],
    ["browser", "Navegador e sessões", Link2],
    ["settings", "Configurações", Settings2],
    ["help", "Como usar", BookOpen],
  ] as const;
  const titles: Record<string, string> = {
    dashboard: "Visão geral",
    setup: "Configuração guiada",
    autopilot: "Rotina automática",
    profile: "Meu perfil",
    worklist: "Vagas consolidadas",
    "linkedin-worklist": "Vagas consolidadas",
    jobs: "Oportunidades",
    "new-job": "Oportunidades",
    applications: "Minhas candidaturas",
    followups: "Retornos",
    schedule: "Agenda e execuções",
    browser: "Navegador e sessões",
    settings: "Configurações",
    help: "Como usar",
  };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("dashboard");
          }}
        >
          <span className="brand-mark">
            <BriefcaseBusiness size={21} />
          </span>
          <span>
            Application
            <strong>
              Assistant<span className="brand-dot">.</span>
            </strong>
          </span>
        </a>
        <p className="nav-label">SEU ESPAÇO DE CARREIRA</p>
        <nav>
          {nav.map(([key, label, Icon]) => (
            <button
              key={key}
              aria-label={label}
              title={label}
              className={
                page === key ||
                (page === "new-job" && key === "jobs") ||
                (page === "linkedin-worklist" && key === "worklist")
                  ? "active"
                  : ""
              }
              onClick={() => {
                setPage(key);
                setError("");
              }}
            >
              <Icon size={19} />
              {label}
              {key === "jobs" &&
                state.jobs.filter((j) => j.status === "new").length > 0 && (
                  <span className="nav-count">
                    {state.jobs.filter((j) => j.status === "new").length}
                  </span>
                )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-chip">
            <ShieldCheck size={18} />
            <span>
              Uma instalação. Seus dados.
              <small>Controle em cada candidatura.</small>
            </span>
          </div>
          <button
            className="account"
            onClick={() =>
              act(async () => {
                await api("/logout", "POST");
                setState(null);
                setSession(await api("/session"));
              }, "Sessão encerrada.")
            }
          >
            <span className="avatar">
              {state.profile.name?.charAt(0) || "V"}
            </span>
            <span>
              {state.profile.name || "Seu espaço"}
              <small>Sair da aplicação</small>
            </span>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>
            Meu espaço <ChevronRight size={14} />{" "}
            <strong>{titles[page]}</strong>
          </span>
          <div>
            <span
              className={"routine-chip " + (state.settings.paused ? "" : "on")}
            >
              <span />
              {state.settings.paused
                ? "Rotina pausada"
                : state.running
                  ? "Rotina em execução"
                  : "Rotina habilitada"}
            </span>
            <button
              className="icon-btn"
              aria-label="Atualizar dados"
              onClick={() => act(refresh, "Painel atualizado.")}
              disabled={busy}
            >
              <RefreshCw size={17} />
            </button>
          </div>
        </header>
        <main className="main">
          <div className="page-heading">
            <div>
              <p className="eyebrow">SEU PRÓXIMO PASSO</p>
              <h1>
                {page === "dashboard"
                  ? `Olá${state.profile.name ? ", " + state.profile.name.split(" ")[0] : ""}. Vamos em frente?`
                  : titles[page]}
              </h1>
              <p>
                {page === "dashboard"
                  ? "Acompanhe suas oportunidades, sem perder o controle da sua jornada."
                  : page === "profile"
                    ? "Seu histórico é a base de cada candidatura. Revise antes de confirmar."
                    : page === "jobs"
                      ? "Encontre compatibilidade de verdade, além das palavras-chave."
                      : page === "applications"
                        ? "Cada candidatura tem uma história. Acompanhe a sua."
                        : page === "settings"
                          ? "Defina como a aplicação trabalha por você."
                          : page === "schedule"
                            ? "Sua busca no seu ritmo, com horários e limites definidos."
                            : page === "followups"
                              ? "Transforme respostas em próximos passos."
                              : "Da primeira configuração à sua próxima oportunidade."}
              </p>
            </div>
            {page === "dashboard" && (
              <button
                className="primary"
                disabled={busy || state.running}
                onClick={() =>
                  act(
                    () => api("/runs", "POST"),
                    "Rotina iniciada. Acompanhe em Agenda e execuções.",
                  )
                }
              >
                <Play size={16} />
                Executar rotina
              </button>
            )}
          </div>
          {error && (
            <div role="alert" className="error banner">
              <TriangleAlert size={19} />
              <span>{error}</span>
              <button
                className="icon-btn"
                aria-label="Fechar erro"
                onClick={() => setError("")}
              >
                <X size={17} />
              </button>
            </div>
          )}
          {busy && (
            <div className="working" role="status">
              Processando… As análises de IA podem levar alguns instantes.
            </div>
          )}
          {page === "dashboard" && (
            <>
              <RunSummary state={state} />
              <Dashboard state={state} go={setPage} />
            </>
          )}
          {page === "setup" && (
            <SetupGuide
              state={state}
              act={act}
              busy={busy}
              refresh={refresh}
              go={setPage}
            />
          )}
          {page === "autopilot" && (
            <AutomationPanel state={state} act={act} busy={busy} go={setPage} />
          )}
          {page === "profile" && (
            <ProfilePage state={state} act={act} busy={busy} />
          )}
          {(page === "jobs" ||
            page === "new-job" ||
            page === "applications") && (
            <JobsPage
              key={page}
              newJob={page === "new-job"}
              state={state}
              act={act}
              busy={busy}
              applications={page === "applications"}
            />
          )}
          {(page === "worklist" || page === "linkedin-worklist") && (
            <Worklist
              key={page}
              initialTab={
                page === "linkedin-worklist" ? "linkedin-imports" : "eligible"
              }
              state={state}
              busy={busy}
              act={act}
              go={setPage}
              openBrowser={(target) => {
                setBrowserTarget(target);
                setPage("browser");
              }}
            />
          )}
          {page === "settings" && (
            <SettingsPage state={state} act={act} busy={busy} />
          )}
          {page === "schedule" && (
            <SchedulePage state={state} act={act} busy={busy} />
          )}
          {page === "followups" && (
            <Followups state={state} act={act} busy={busy} />
          )}
          {page === "browser" && (
            <BrowserPage
              state={state}
              refresh={refresh}
              target={browserTarget}
              openLinkedinImports={() => {
                setBrowserTarget(null);
                setPage("linkedin-worklist");
              }}
              returnToWorklist={
                browserTarget
                  ? () => {
                      setBrowserTarget(null);
                      setPage("worklist");
                    }
                  : undefined
              }
            />
          )}
          {page === "help" && <Help />}
        </main>
        <footer>
          Application Assistant{" "}
          <span>Feito para tornar a busca por emprego mais humana.</span>
          <span>v0.6.2 · teste local</span>
        </footer>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={19} />
          {toast}
        </div>
      )}
    </div>
  );
}

type Common = {
  state: AppState;
  act: Action;
  busy: boolean;
};
function Dashboard({
  state,
  go,
}: {
  state: AppState;
  go: (page: string) => void;
}) {
  const sent = state.jobs.filter((j) => sentStates.includes(j.status)),
    response = state.jobs.filter((j) =>
      ["receipt", "selection", "interview", "offer", "rejected"].includes(
        j.status,
      ),
    );
  const interview = state.jobs.filter((j) => j.status === "interview"),
    pending = state.jobs.filter((j) =>
      ["new", "blocked", "review", "ready", "uncertain"].includes(j.status),
    );
  const checklist = [
    {
      label: "Importar seu currículo",
      done: state.pdf_imported,
      page: "profile",
    },
    {
      label: "Confirmar seu perfil e objetivos",
      done: state.profile.confirmed,
      page: "profile",
    },
    {
      label: "Configurar seu modelo de IA",
      done: !!state.settings.ai_model && state.settings.ai_consent,
      page: "settings",
    },
    {
      label: "Adicionar sua primeira oportunidade",
      done: state.jobs.length > 0,
      page: "jobs",
    },
  ];
  const complete = checklist.every((x) => x.done);
  const bars = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - 6 + i);
    const n = sent.filter(
      (j) =>
        j.sent_at && new Date(j.sent_at).toDateString() === d.toDateString(),
    ).length;
    return {
      day: d.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", ""),
      n,
    };
  });
  const max = Math.max(1, ...bars.map((x) => x.n));
  return (
    <>
      <div className="stats-grid">
        {[
          {
            label: "Candidaturas registradas",
            n: sent.length,
            sub: "Envios SMTP, portais e informados por você",
            Icon: BriefcaseBusiness,
          },
          {
            label: "Retornos registrados",
            n: response.length,
            sub: "Atualizações confirmadas",
            Icon: Mail,
          },
          {
            label: "Entrevistas",
            n: interview.length,
            sub: "Conversas para o próximo passo",
            Icon: CalendarClock,
          },
          {
            label: "Para sua atenção",
            n: pending.length,
            sub: "Oportunidades e revisões pendentes",
            Icon: Clock3,
          },
        ].map(({ label, n, sub, Icon }) => (
          <section className="stat" key={label}>
            <div>
              <span>{label}</span>
              <Icon size={19} />
            </div>
            <strong>{n.toString().padStart(2, "0")}</strong>
            <small>{sub}</small>
          </section>
        ))}
      </div>
      {!complete && (
        <section className="onboarding">
          <div className="onboard-intro">
            <span className="mini-icon">
              <SlidersHorizontal size={22} />
            </span>
            <div>
              <h2>Seu assistente começa com você</h2>
              <p>Prepare o essencial para candidaturas com mais critério.</p>
            </div>
            <span className="progress-label">
              {checklist.filter((x) => x.done).length} de 4 etapas
            </span>
          </div>
          <div className="steps">
            {checklist.map((x, i) => (
              <button key={x.label} onClick={() => go(x.page)}>
                <span className={x.done ? "step-number done" : "step-number"}>
                  {x.done ? <Check size={15} /> : i + 1}
                </span>
                <span>{x.label}</span>
                <ChevronRight size={15} />
              </button>
            ))}
          </div>
        </section>
      )}
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Atividade de candidaturas</h2>
              <p>Candidaturas registradas nos últimos 7 dias</p>
            </div>
            <span className="subtle-pill">Últimos 7 dias</span>
          </div>
          <div className="chart">
            {bars.map((b, i) => (
              <div className="bar-wrap" key={i}>
                <span>{b.n}</span>
                <div className="bar-track">
                  <div
                    className="bar"
                    style={{ height: `${(b.n / max) * 100}%` }}
                  />
                </div>
                <small>{b.day}</small>
              </div>
            ))}
          </div>
        </section>
        <section className="panel policy-card">
          <div className="panel-heading">
            <h2>Seu critério de busca</h2>
            <ShieldCheck size={20} />
          </div>
          <div className="threshold">
            <strong>
              {state.settings.threshold}
              <span>%</span>
            </strong>
            <span>aderência mínima</span>
          </div>
          <div className="meter">
            <span style={{ width: `${state.settings.threshold}%` }} />
          </div>
          <p>
            {state.profile.roles.length
              ? state.profile.roles.join(" · ")
              : "Defina os cargos que fazem sentido para você."}
          </p>
          <div className="policy-line">
            <span>Modo de candidatura</span>
            <strong>
              {state.settings.mode === "review"
                ? "Com sua aprovação"
                : "Automático por e-mail"}
            </strong>
          </div>
          <button className="text-button" onClick={() => go("settings")}>
            Ajustar meus critérios <SlidersHorizontal size={15} />
          </button>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Oportunidades recentes</h2>
            <p>O próximo passo pode estar aqui.</p>
          </div>
          <button className="text-button" onClick={() => go("jobs")}>
            Ver oportunidades <ArrowUpRight size={16} />
          </button>
        </div>
        {state.jobs.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Vaga e empresa</th>
                  <th>Modalidade</th>
                  <th>Aderência</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {state.jobs.slice(0, 5).map((j) => (
                  <tr key={j.id}>
                    <td>
                      <strong>{j.title}</strong>
                      <small>{j.company}</small>
                    </td>
                    <td>{j.modality}</td>
                    <td>
                      {j.analysis?.score != null ? (
                        <span className="score">{j.analysis.score}%</span>
                      ) : (
                        "A analisar"
                      )}
                    </td>
                    <td>
                      <Badge status={j.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty">
            <Search size={30} />
            <h3>Ainda não há oportunidades</h3>
            <p>
              Importe uma vaga ou adicione o anúncio para começar a análise.
            </p>
            <button className="secondary" onClick={() => go("jobs")}>
              <Plus size={16} />
              Adicionar oportunidade
            </button>
          </div>
        )}
      </section>
      <div className="tip">
        <ShieldCheck size={19} />
        <p>
          Seu perfil vem primeiro. Áreas excluídas e critérios obrigatórios
          prevalecem sobre a pontuação da IA.
        </p>
      </div>
    </>
  );
}
function SetupGuide({
  state,
  act,
  busy,
  refresh,
  go,
}: Common & {
  refresh: () => Promise<unknown>;
  go: (page: string) => void;
}) {
  const [step, setStep] = useState(0);
  const [collectFeedback, setCollectFeedback] = useState<Feedback | null>(null);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [step]);
  const [editSources, setEditSources] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceFeedback, setSourceFeedback] = useState<Feedback | null>(null);
  const [testedModel, setTestedModel] = useState("");
  const [loginPortal, setLoginPortal] = useState("");
  const settings = state.settings;
  const sources = state.configured_sources || [];
  const portals = sources.filter(
    (source): source is "linkedin" | "indeed" =>
      source === "indeed" ||
      (source === "linkedin" && settings.linkedin_search_method !== "email"),
  );
  const portalIssues = state.search_portal_issues || {};
  const missingSessions = portals.filter((portal) =>
    Boolean(portalIssues[portal]),
  );
  const selectedPortal =
    portals.find((portal) => portal === loginPortal) ||
    missingSessions[0] ||
    portals[0];
  const portalNames = { linkedin: "LinkedIn", indeed: "Indeed" };
  const useLinkedInAlerts =
    sources.includes("linkedin") && settings.linkedin_search_method === "email";
  const missingAlertMailbox =
    useLinkedInAlerts &&
    !(
      settings.imap_host &&
      settings.imap_user &&
      settings.imap_password_configured
    );
  const model = `${settings.ai_url}|${settings.ai_model}`;
  const steps = [
    "Inteligência artificial",
    "Currículo e perfil",
    "Fontes e rotina",
    "Conectar contas",
    "Teste de coleta",
  ];
  const canTest =
    settings.ai_consent &&
    !!settings.ai_model &&
    state.profile.confirmed &&
    sources.some(
      (source) =>
        !missingSessions.some((portal) => portal === source) &&
        (source !== "linkedin" || !missingAlertMailbox),
    );
  const disabledReasons = [
    !settings.ai_consent || !settings.ai_model
      ? "Configure e salve o modelo com consentimento."
      : "",
    !state.profile.confirmed
      ? "Confirme e salve o perfil, com área, cargo e fatos."
      : "",
    !sources.length ? "Salve pelo menos uma fonte habilitada na rotina." : "",
    missingSessions.length
      ? `Conecte as contas em: ${missingSessions.map((portal) => portalNames[portal]).join(", ")}.`
      : "",
    missingAlertMailbox
      ? "Configure a caixa IMAP que recebe os alertas do LinkedIn na etapa Conectar contas."
      : "",
  ].filter(Boolean);
  async function addSource() {
    const address = new URL(sourceUrl.trim());
    if (
      address.protocol !== "https:" ||
      address.username ||
      address.password ||
      (address.port && address.port !== "443")
    ) {
      throw new Error(
        "Informe um endereço HTTPS público, sem usuário, senha ou porta personalizada.",
      );
    }
    const domain = address.hostname.toLowerCase();
    if (!domain.includes("."))
      throw new Error("Informe o endereço público da fonte.");
    const gupy = domain === "gupy.io" || domain.endsWith(".gupy.io");
    if (/(^|\.)(linkedin\.com|indeed\.com(?:\.br)?)$/.test(domain)) {
      throw new Error(
        "Escolha LinkedIn ou Indeed nos portais abaixo e entre pelo navegador interno.",
      );
    }
    const url = address.href;
    if (settings.sources.some((source) => source.url === url))
      throw new Error(
        "Este endereço já está cadastrado. Confira se a fonte está habilitada.",
      );
    const platform = gupy ? "gupy" : "company";
    await api("/settings", "PUT", {
      ...editableSettings(settings),
      search_platforms: [...new Set([...settings.search_platforms, platform])],
      allowed_domains: gupy
        ? settings.allowed_domains
        : [...new Set([...settings.allowed_domains, domain])],
      sources: [
        ...settings.sources,
        { name: domain, url, kind: "company", enabled: true },
      ],
    });
    setSourceUrl("");
  }
  return (
    <>
      <section className="panel">
        <h2>
          {step + 1} de {steps.length} · {steps[step]}
        </h2>
        <div className="chips" aria-label="Etapas da configuração">
          {steps.map((label, index) => (
            <button
              type="button"
              className={index === step ? "chip selected" : "chip"}
              key={label}
              disabled={busy}
              aria-current={index === step ? "step" : undefined}
              onClick={() => setStep(index)}
            >
              {label}
            </button>
          ))}
        </div>
      </section>
      {step === 0 && (
        <SettingsPage
          state={state}
          act={act}
          busy={busy}
          section="ai"
          onTested={() =>
            void api<AppState>("/state")
              .then(({ settings: saved }) =>
                setTestedModel(`${saved.ai_url}|${saved.ai_model}`),
              )
              .catch(() => {})
          }
        />
      )}
      {step === 1 && <ProfilePage state={state} act={act} busy={busy} />}
      {step === 2 && (
        <>
          <section className="panel">
            <h3>Adicionar uma fonte por link</h3>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                act(
                  addSource,
                  "Fonte adicionada e habilitada para a coleta.",
                  setSourceFeedback,
                );
              }}
            >
              <Field
                label="Link do feed ou da página de carreiras"
                hint="Aceita feeds RSS/JSON e páginas públicas de vagas da Gupy ou com dados JobPosting. A inclusão autoriza a consulta desse endereço."
              >
                <input
                  type="url"
                  required
                  value={sourceUrl}
                  onChange={(event) => setSourceUrl(event.target.value)}
                />
              </Field>
              <button className="secondary" disabled={busy}>
                Adicionar pelo link
              </button>
              <ActionFeedback feedback={sourceFeedback} />
            </form>
            <p>
              Ao selecionar LinkedIn ou Indeed, salve as preferências e entre na
              conta na etapa Conectar contas. Feeds e páginas públicas
              disponíveis podem ser pesquisados sem login.
            </p>
          </section>
          <section className="panel button-row">
            <button
              className={editSources ? "secondary" : "primary"}
              disabled={busy}
              onClick={() => setEditSources(false)}
            >
              Portais e modo de operação
            </button>
            <button
              className={editSources ? "primary" : "secondary"}
              disabled={busy}
              onClick={() => setEditSources(true)}
            >
              Feeds e páginas de empresas
            </button>
          </section>
          {editSources ? (
            <SettingsPage
              state={state}
              act={act}
              busy={busy}
              section="sources"
              key={settings.sources.length}
            />
          ) : (
            <AutomationPanel
              state={state}
              act={act}
              busy={busy}
              go={go}
              setup
              key={settings.sources.length}
            />
          )}
        </>
      )}
      {step === 3 && (
        <>
          <section className="panel">
            <h3>Conecte as contas usadas na busca</h3>
            {portals.length === 0 ? (
              <p>
                As fontes selecionadas nesta configuração não exigem login no
                navegador interno.
              </p>
            ) : (
              <>
                <p>
                  Para pesquisar em cada portal abaixo, clique em Abrir portal,
                  assuma o controle, entre na sua conta e salve a sessão.
                </p>
                <div className="button-row">
                  {portals.map((portal) => (
                    <button
                      key={portal}
                      type="button"
                      className={
                        portal === selectedPortal ? "primary" : "secondary"
                      }
                      aria-pressed={portal === selectedPortal}
                      onClick={() => setLoginPortal(portal)}
                    >
                      {portalNames[portal]} ·{" "}
                      {portalIssues[portal]
                        ? "Pendência de conexão"
                        : "Sessão salva"}
                    </button>
                  ))}
                </div>
                {selectedPortal && (
                  <BrowserPage
                    key={selectedPortal}
                    state={state}
                    refresh={refresh}
                    target={{ platform: selectedPortal, job_id: "" }}
                    fixedPortal
                    openLinkedinImports={() => go("linkedin-worklist")}
                  />
                )}
              </>
            )}
          </section>
          {useLinkedInAlerts && (
            <section className="panel">
              <h3>Caixa de alertas do LinkedIn</h3>
              <p>
                Ative o envio por e-mail dos alertas de vaga no LinkedIn.
                Configure abaixo a conta e a pasta IMAP que recebem esses
                e-mails. A leitura de respostas é opcional.
              </p>
              <a
                href="https://www.linkedin.com/jobs/"
                target="_blank"
                rel="noopener noreferrer"
              >
                Configurar alertas no LinkedIn
              </a>
            </section>
          )}
          <details open={useLinkedInAlerts || undefined}>
            <summary>
              {useLinkedInAlerts
                ? "Configurar e-mail de coleta"
                : "Configurar e-mail, se for usar"}
            </summary>
            <SettingsPage state={state} act={act} busy={busy} section="email" />
          </details>
        </>
      )}
      {step === 4 && (
        <>
          <section className="panel">
            <h3>Verificar antes de ativar a agenda</h3>
            {testedModel !== model &&
              settings.ai_consent &&
              settings.ai_model && (
                <p>
                  Use “Salvar e testar conexão” na primeira etapa se ainda não
                  testou o modelo.
                </p>
              )}
            {missingSessions.length > 0 && (
              <button
                type="button"
                className="secondary"
                onClick={() => setStep(3)}
              >
                Conectar contas pendentes
              </button>
            )}
            {disabledReasons.length > 0 && (
              <ul>
                {disabledReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
            <p>
              O teste consulta as fontes e consolida a fila. Nenhuma candidatura
              é enviada.
            </p>
            <div className="button-row">
              <button
                className="primary"
                disabled={busy || state.running || !canTest}
                onClick={() =>
                  act(
                    () => api("/runs", "POST", { action: "collect" }),
                    "Coleta de teste iniciada.",
                    setCollectFeedback,
                  )
                }
              >
                {state.running
                  ? "Coleta em andamento"
                  : "Testar coleta sem envio"}
              </button>
              <button className="secondary" onClick={() => go("worklist")}>
                Ver vagas consolidadas
              </button>
              <ActionFeedback feedback={collectFeedback} />
            </div>
          </section>
          <RunSummary state={state} />
          <details>
            <summary>Configurar agenda, se for usar</summary>
            <SchedulePage state={state} act={act} busy={busy} />
          </details>
        </>
      )}
      <section className="panel button-row">
        {step > 0 && (
          <button
            className="secondary"
            disabled={busy}
            onClick={() => setStep(step - 1)}
          >
            Voltar
          </button>
        )}
        {step < steps.length - 1 && (
          <button
            className="primary"
            disabled={busy}
            onClick={() => setStep(step + 1)}
          >
            Próxima etapa
          </button>
        )}
      </section>
    </>
  );
}
function ResumeVersions({ act, busy, state }: Common) {
  const [focus, setFocus] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [versions, setVersions] = useState<
    { id: string; focus: string; at: string }[]
  >([]);
  useEffect(() => {
    let active = true;
    api<typeof versions>("/profile/resume-versions")
      .then((items) => {
        if (active) setVersions(items);
      })
      .catch((error: Error) => {
        if (active) setFeedback({ kind: "error", message: error.message });
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <section className="panel">
      <h2>Versões do currículo</h2>
      <p>
        Informe um foco como IA generativa e LLMs ou desenvolvimento Python. A
        IA seleciona e ordena os fatos confirmados que mais ajudam nesse
        objetivo.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const value = focus.trim();
          act(
            async () => {
              const version = await api<(typeof versions)[number]>(
                "/profile/resume-versions",
                "POST",
                { focus: value },
              );
              setVersions((previous) => [version, ...previous].slice(0, 20));
              setFocus("");
            },
            "Versão pronta para baixar.",
            setFeedback,
          );
        }}
      >
        <Field label="Foco do currículo">
          <input
            value={focus}
            onChange={(event) => setFocus(event.target.value)}
            maxLength={150}
            minLength={2}
            required
          />
        </Field>
        <button
          className="primary"
          disabled={busy || !state.profile.confirmed || focus.trim().length < 2}
        >
          Gerar versão com IA
        </button>
        <ActionFeedback feedback={feedback} />
        {!state.profile.confirmed && (
          <p>
            <small>Confirme e salve o perfil para gerar uma versão.</small>
          </p>
        )}
      </form>
      {versions.map((version) => (
        <div className="button-row" key={version.id}>
          <strong>{version.focus}</strong>
          <a
            className="secondary"
            href={`/api/profile/resume-versions/${version.id}`}
            download
          >
            PDF
          </a>
          <a
            className="secondary"
            href={`/api/profile/resume-versions/${version.id}?format=docx`}
            download
          >
            Word (.docx)
          </a>
        </div>
      ))}
    </section>
  );
}
function ProfilePage({ state, act, busy }: Common) {
  const [p, setP] = useState<Profile>(state.profile),
    [text, setText] = useState(""),
    [factFilter, setFactFilter] = useState<FactCategory | "all">("all"),
    [showText, setShowText] = useState(false),
    [contactFields, setContactFields] = useState<string[]>([]),
    [draftMessage, setDraftMessage] = useState(""),
    [saveFeedback, setSaveFeedback] = useState<Feedback | null>(null),
    [importFeedback, setImportFeedback] = useState<Feedback | null>(null),
    [rolesText, setRolesText] = useState(state.profile.roles.join(", ")),
    [locationsText, setLocationsText] = useState(
      state.profile.locations.join(", "),
    );
  const patch = (key: keyof Profile, value: unknown) => {
    setSaveFeedback(null);
    setP((x) => ({ ...x, [key]: value, confirmed: false }));
  };
  const choose = (
    key: "areas" | "excluded_areas" | "modalities" | "contracts",
    v: string,
  ) =>
    patch(
      key,
      p[key].includes(v) ? p[key].filter((x) => x !== v) : [...p[key], v],
    );
  return (
    <div className="content-grid">
      <div>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Comece pelo seu currículo</h2>
              <p>Exporte o PDF no LinkedIn e importe aqui.</p>
            </div>
            <FileText size={21} />
          </div>
          {state.pdf_imported && (
            <div className="notice">
              <strong>Currículo importado</strong>
              <div>
                <a href="/api/profile/pdf" download>
                  {state.pdf_filename || "Curriculo.pdf"}
                </a>
              </div>
            </div>
          )}
          <label className="upload-zone">
            <Upload size={27} />
            <strong>
              {state.pdf_imported
                ? "Importar outro PDF"
                : "Escolher currículo em PDF"}
            </strong>
            <span>Até 10 MB · PDF com texto selecionável</span>
            <input
              type="file"
              accept="application/pdf"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                const data = new FormData();
                data.append("file", f);
                act(
                  async () => {
                    const r = await api<{
                      text: string;
                      contacts: Partial<
                        Record<
                          "name" | "email" | "phone" | "city" | "linkedin_url",
                          string
                        >
                      >;
                    }>("/profile/pdf", "POST", data);
                    const labels = {
                      name: "nome",
                      email: "e-mail",
                      phone: "telefone",
                      city: "cidade",
                      linkedin_url: "LinkedIn",
                    };
                    const keys = Object.keys(
                      r.contacts,
                    ) as (keyof typeof labels)[];
                    setContactFields(
                      keys.filter((key) => !p[key]).map((key) => labels[key]),
                    );
                    setText(r.text);
                    setShowText(true);
                    setDraftMessage("");
                    setP((x) => {
                      const contacts = Object.fromEntries(
                        keys
                          .filter((key) => !x[key])
                          .map((key) => [key, r.contacts[key]]),
                      );
                      return {
                        ...x,
                        ...contacts,
                        confirmed: false,
                        facts: x.facts.map((f) =>
                          f.source === "pdf"
                            ? { ...f, source: "manual", evidence: "" }
                            : f,
                        ),
                      };
                    });
                  },
                  "PDF importado. Confira o currículo e os dados do perfil.",
                  setImportFeedback,
                );
                e.target.value = "";
              }}
            />
          </label>
          <ActionFeedback feedback={importFeedback} />
          <div className="button-row">
            <button
              className="secondary"
              disabled={busy || !state.pdf_imported}
              onClick={() =>
                act(async () => {
                  const d = await api<Partial<Profile>>(
                    "/profile/extract",
                    "POST",
                  );
                  setP((x) => {
                    const facts = [...x.facts];
                    const known = new Set(facts.map((fact) => fact.text));
                    const ids = new Set(facts.map((fact) => fact.id));
                    let index = 1;
                    for (const fact of d.facts || []) {
                      if (known.has(fact.text) || facts.length >= 300) continue;
                      while (ids.has(`pdf-${index}`)) index++;
                      facts.push({ ...fact, id: `pdf-${index++}` });
                      known.add(fact.text);
                    }
                    return {
                      ...x,
                      name: x.name || d.name || "",
                      email: x.email || d.email || "",
                      facts,
                      confirmed: false,
                    };
                  });
                  setDraftMessage(
                    "Sugestões carregadas. Confira os fatos, selecione área e cargos e salve o perfil.",
                  );
                }, "Sugestões extraídas com evidências do PDF.")
              }
            >
              <RefreshCw size={16} />
              Extrair perfil com IA
            </button>
            <button
              className="text-button"
              disabled={!state.pdf_imported || busy}
              onClick={() =>
                act(async () => {
                  const r = await api<{ text: string }>("/profile/pdf-text");
                  setText(r.text);
                }, "Texto do PDF carregado.")
              }
            >
              Conferir texto
            </button>
          </div>
          {text && (
            <details
              open={showText}
              onToggle={(event) => setShowText(event.currentTarget.open)}
            >
              <summary>Texto extraído do currículo</summary>
              <pre className="source-text">{text}</pre>
            </details>
          )}
          {contactFields.length > 0 && (
            <p className="notice">
              Dados preenchidos a partir do PDF: {contactFields.join(", ")}.
              Confira antes de confirmar o perfil.
            </p>
          )}
          {draftMessage && <p className="notice">{draftMessage}</p>}
        </section>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            act(
              () =>
                api("/profile", "PUT", {
                  ...p,
                  roles: split(rolesText),
                  locations: split(locationsText),
                }),
              "Perfil salvo.",
              setSaveFeedback,
            );
          }}
        >
          <section className="panel">
            <div className="panel-heading">
              <h2>Dados e objetivos profissionais</h2>
              <Badge status={p.confirmed ? "receipt" : "review"} />
            </div>
            <div className="form-grid">
              <Field label="Nome completo">
                <input
                  value={p.name}
                  required
                  onChange={(e) => patch("name", e.target.value)}
                />
              </Field>
              <Field label="E-mail para contato">
                <input
                  type="email"
                  value={p.email}
                  onChange={(e) => patch("email", e.target.value)}
                />
              </Field>
              <Field label="Endereço público do perfil LinkedIn">
                <input
                  value={p.linkedin_url || ""}
                  onChange={(e) => patch("linkedin_url", e.target.value)}
                  placeholder="https://www.linkedin.com/in/seu-perfil"
                />
              </Field>
              <Field label="Telefone">
                <input
                  value={p.phone}
                  onChange={(e) => patch("phone", e.target.value)}
                />
              </Field>
              <Field label="Cidade / UF">
                <input
                  value={p.city}
                  onChange={(e) => patch("city", e.target.value)}
                />
              </Field>
            </div>
            <Field
              label="Cargos que você procura"
              hint="Separe por vírgula. Ex.: Desenvolvedor Python, Engenheiro de software"
            >
              <input
                value={rolesText}
                onChange={(e) => {
                  setRolesText(e.target.value);
                  patch("roles", split(e.target.value));
                }}
              />
            </Field>
            <p className="field-title">Áreas desejadas</p>
            <div className="chips">
              {state.areas.map((a) => (
                <button
                  key={a}
                  type="button"
                  className={p.areas.includes(a) ? "chip selected" : "chip"}
                  aria-pressed={p.areas.includes(a)}
                  onClick={() => choose("areas", a)}
                >
                  {a}
                </button>
              ))}
            </div>
            <details>
              <summary>Áreas que você não quer considerar</summary>
              <div className="chips">
                {state.areas.map((a) => (
                  <button
                    key={a}
                    type="button"
                    className={
                      p.excluded_areas.includes(a) ? "chip excluded" : "chip"
                    }
                    aria-pressed={p.excluded_areas.includes(a)}
                    onClick={() => choose("excluded_areas", a)}
                  >
                    {a}
                  </button>
                ))}
              </div>
            </details>
            <p className="field-title">Modalidades aceitas</p>
            <div className="chips">
              {["Remoto", "Híbrido", "Presencial"].map((a) => (
                <button
                  key={a}
                  type="button"
                  className={
                    p.modalities.includes(a) ? "chip selected" : "chip"
                  }
                  onClick={() => choose("modalities", a)}
                >
                  {a}
                </button>
              ))}
            </div>
            <p className="field-title">
              Regimes aceitos (nenhum selecionado = sem restrição)
            </p>
            <div className="chips">
              {["CLT", "PJ", "Estágio", "Temporário"].map((a) => (
                <button
                  key={a}
                  type="button"
                  className={p.contracts.includes(a) ? "chip selected" : "chip"}
                  onClick={() => choose("contracts", a)}
                >
                  {a}
                </button>
              ))}
            </div>
            <div className="form-grid">
              <Field
                label="Localidades aceitas"
                hint="Separadas por vírgula; vazio aceita qualquer localidade."
              >
                <input
                  value={locationsText}
                  onChange={(e) => {
                    setLocationsText(e.target.value);
                    patch("locations", split(e.target.value));
                  }}
                />
              </Field>
              <Field
                label="Remuneração mensal mínima (R$)"
                hint="0 desativa o filtro. Vagas sem salário exigirão revisão se houver mínimo."
              >
                <input
                  type="number"
                  min={0}
                  max={1000000}
                  value={p.minimum_salary}
                  onChange={(e) =>
                    patch("minimum_salary", Number(e.target.value))
                  }
                />
              </Field>
            </div>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Experiências, formação e competências</h2>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy || !state.profile.facts.length}
                  onClick={() =>
                    act(async () => {
                      const draft = await api<Partial<Profile>>(
                        "/profile/improve",
                        "POST",
                      );
                      setP((x) => ({ ...x, ...draft, confirmed: false }));
                      setDraftMessage(
                        "Sugestão de redação carregada, ainda não salva. Compare com os fatos originais e confirme antes de usar nas candidaturas.",
                      );
                    }, "Sugestão pronta para sua revisão. O perfil salvo ainda não foi alterado.")
                  }
                >
                  Melhorar redação com IA
                </button>
                {state.profile.confirmed && (
                  <div className="button-row">
                    <a
                      className="secondary"
                      href="/api/profile/resume"
                      download
                    >
                      Currículo padrão em PDF
                    </a>
                    <a
                      className="secondary"
                      href="/api/profile/resume?format=docx"
                      download
                    >
                      Currículo padrão em Word
                    </a>
                  </div>
                )}
                <p>
                  Experiências, formação, idiomas e competências verificáveis.
                </p>
              </div>
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  patch("facts", [
                    ...p.facts,
                    {
                      id: crypto.randomUUID(),
                      text: "",
                      evidence: "",
                      source: "manual",
                      category: factFilter === "all" ? "other" : factFilter,
                    },
                  ])
                }
              >
                <Plus size={16} />
                Adicionar
              </button>
            </div>
            {p.facts.length === 0 && (
              <p className="notice">
                Importe o PDF e use a IA para extrair sugestões, ou adicione os
                fatos manualmente.
              </p>
            )}
            {p.facts.length > 0 && (
              <Field label="Filtrar registros do perfil">
                <select
                  value={factFilter}
                  onChange={(event) =>
                    setFactFilter(event.target.value as FactCategory | "all")
                  }
                >
                  <option value="all">Todas as categorias</option>
                  {Object.entries(factCategories).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {p.facts.map(
              (f, i) =>
                (factFilter === "all" ||
                  (f.category || "other") === factFilter) && (
                  <div className="fact" key={f.id}>
                    <div>
                      <span className="subtle-pill">
                        {f.source === "pdf"
                          ? "Trecho do PDF"
                          : f.evidence
                            ? "Sugestão de redação — revise"
                            : "Informado por você"}
                      </span>
                      <button
                        className="icon-btn"
                        type="button"
                        aria-label="Remover fato"
                        onClick={() =>
                          patch(
                            "facts",
                            p.facts.filter((x) => x.id !== f.id),
                          )
                        }
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    {f.source === "manual" && f.evidence && (
                      <details>
                        <summary>Texto original para comparação</summary>
                        <p>{f.evidence}</p>
                      </details>
                    )}
                    <Field label={`Categoria do registro ${i + 1}`}>
                      <select
                        value={f.category || "other"}
                        onChange={(event) => {
                          const category = event.target.value as FactCategory;
                          patch(
                            "facts",
                            p.facts.map((fact) =>
                              fact.id === f.id ? { ...fact, category } : fact,
                            ),
                          );
                        }}
                      >
                        {Object.entries(factCategories).map(([key, label]) => (
                          <option key={key} value={key}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <textarea
                      required
                      aria-label={`Fato profissional ${i + 1}`}
                      value={f.text}
                      onChange={(e) =>
                        patch(
                          "facts",
                          p.facts.map((x) =>
                            x.id === f.id
                              ? {
                                  ...x,
                                  text: e.target.value,
                                  source: "manual",
                                  evidence: "",
                                }
                              : x,
                          ),
                        )
                      }
                    />
                  </div>
                ),
            )}
            <h3>Respostas reutilizáveis para cadastros</h3>
            <p>
              Cadastre respostas factuais uma vez. Os conectores de formulários
              usarão este banco quando forem validados. Estes campos não entram
              no prompt de análise de vagas.
            </p>
            {(p.answers || []).map((answer, index) => (
              <div className="source-card" key={index}>
                <Field label="Pergunta ou campo">
                  <input
                    required
                    value={answer.question}
                    onChange={(e) =>
                      patch(
                        "answers",
                        p.answers.map((x, n) =>
                          n === index ? { ...x, question: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </Field>
                <Field label="Sua resposta confirmada">
                  <textarea
                    required
                    value={answer.answer}
                    onChange={(e) =>
                      patch(
                        "answers",
                        p.answers.map((x, n) =>
                          n === index ? { ...x, answer: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </Field>
                <button
                  type="button"
                  className="text-button"
                  onClick={() =>
                    patch(
                      "answers",
                      p.answers.filter((_, n) => n !== index),
                    )
                  }
                >
                  Remover resposta
                </button>
              </div>
            ))}
            <button
              type="button"
              className="secondary"
              onClick={() =>
                patch("answers", [
                  ...(p.answers || []),
                  { question: "", answer: "" },
                ])
              }
            >
              Adicionar resposta reutilizável
            </button>
            <Toggle
              label="Revisei e confirmo a veracidade deste perfil"
              hint="Autoriza usar estes fatos nas candidaturas. Qualquer edição pede nova confirmação."
              checked={p.confirmed}
              onChange={(v) =>
                setP((x) => ({
                  ...x,
                  confirmed: v,
                  roles: x.roles.filter(Boolean),
                  locations: x.locations.filter(Boolean),
                }))
              }
            />
            <button className="primary" disabled={busy}>
              <Check size={17} />
              Salvar perfil
            </button>
            <ActionFeedback feedback={saveFeedback} />
          </section>
        </form>
        <ResumeVersions state={state} act={act} busy={busy} />
      </div>
      <aside>
        <section className="panel aside-note">
          <span className="mini-icon">
            <ShieldCheck />
          </span>
          <h2>Sua história, com precisão.</h2>
          <p>
            A IA seleciona os fatos mais relevantes para cada vaga. Ela não cria
            qualificações nem aumenta seu tempo de experiência.
          </p>
          <hr />
          <h3>Área e empresa são coisas diferentes</h3>
          <p>
            Desenvolver software em um banco não torna seu perfil financeiro.
            Você define a direção da sua carreira.
          </p>
        </section>
      </aside>
    </div>
  );
}
function JobsPage({
  state,
  act,
  busy,
  applications,
  newJob,
}: Common & { applications: boolean; newJob: boolean }) {
  const [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [editing, setEditing] = useState<JobInput | null>(
      newJob ? { ...emptyJob, country: "unknown" } : null,
    ),
    [editId, setEditId] = useState(""),
    [selected, setSelected] = useState(""),
    [importing, setImporting] = useState(false),
    [url, setUrl] = useState(""),
    [note, setNote] = useState(""),
    [status, setStatus] = useState("selection");
  const jobs = state.jobs.filter(
    (j) =>
      (!applications ||
        sentStates.includes(j.status) ||
        j.status === "uncertain") &&
      `${j.title} ${j.company} ${j.area}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "all" || j.status === filter),
  );
  const j = state.jobs.find((x) => x.id === selected);
  const patch = (k: keyof JobInput, v: unknown) =>
    setEditing((x) => (x ? { ...x, [k]: v } : null));
  return (
    <>
      <div className="toolbar">
        <div className="search-input">
          <Search size={18} />
          <input
            aria-label="Buscar oportunidades"
            placeholder="Buscar por cargo, empresa ou área…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select
          aria-label="Filtrar situação"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">Todas as situações</option>
          {Object.entries(statusLabels).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button className="secondary" onClick={() => setImporting(true)}>
          <Link2 size={16} />
          Importar link
        </button>
        <button
          className="primary"
          onClick={() => {
            setEditing({ ...emptyJob });
            setEditId("");
          }}
        >
          <Plus size={17} />
          Adicionar vaga
        </button>
      </div>
      <div className="result-caption">
        {jobs.length} {jobs.length === 1 ? "oportunidade" : "oportunidades"} ·{" "}
        {applications
          ? "envios registrados e resultados incertos"
          : "dados da sua instalação"}
      </div>
      {jobs.length ? (
        <section className="panel job-list">
          {jobs.map((item) => (
            <button
              className="job-row"
              key={item.id}
              onClick={() => setSelected(item.id)}
            >
              <span className="company-avatar">
                {item.company.slice(0, 2).toUpperCase()}
              </span>
              <span className="job-main">
                <strong>{item.title}</strong>
                <span>
                  {item.company} <span className="separator">·</span>{" "}
                  {item.location || "Local não informado"}
                </span>
                <small>
                  {item.modality} · {item.area || "Revisar área"}
                </small>
              </span>
              <span className="job-score">
                {item.analysis?.score != null ? (
                  <>
                    <strong>{item.analysis.score}%</strong>
                    <small>aderência</small>
                  </>
                ) : (
                  <small>Sem análise</small>
                )}
              </span>
              <Badge status={item.status} />
              <ChevronRight size={18} />
            </button>
          ))}
        </section>
      ) : (
        <section className="panel empty">
          <BriefcaseBusiness size={35} />
          <h2>
            {applications
              ? "Sua jornada vai aparecer aqui"
              : "Vamos encontrar o próximo passo"}
          </h2>
          <p>
            {applications
              ? "As candidaturas registradas ficam organizadas com histórico e retorno."
              : "Adicione o texto de uma vaga ou importe um link público com dados JobPosting."}
          </p>
          <button
            className="primary"
            onClick={() => {
              setEditing({ ...emptyJob });
              setEditId("");
            }}
          >
            <Plus size={17} />
            Adicionar minha primeira vaga
          </button>
        </section>
      )}
      <div className="tip">
        <BookOpen size={19} />
        <p>
          LinkedIn e Gupy: candidatura assistida nesta versão. Prepare o
          currículo aqui e finalize no site da vaga.
        </p>
      </div>
      {importing && (
        <Modal
          title="Importar oportunidade"
          onClose={() => setImporting(false)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                const r = await api<{ imported: number }>(
                  "/jobs/import-url",
                  "POST",
                  { url },
                );
                if (r.imported === 0)
                  throw new Error(
                    "Nenhuma vaga nova: o conteúdo pode já estar cadastrado.",
                  );
                setImporting(false);
              }, "Oportunidades importadas. Revise a área e os requisitos.");
            }}
          >
            <p>
              Use uma página pública com dados estruturados JobPosting ou um
              feed RSS/JSON. Autorize o domínio exato em Configurações → Fontes.
            </p>
            <Field label="Link HTTPS">
              <input
                type="url"
                required
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </Field>
            <button className="primary" disabled={busy}>
              Importar
            </button>
          </form>
        </Modal>
      )}
      {editing && (
        <Modal
          title={editId ? "Revisar oportunidade" : "Nova oportunidade"}
          onClose={() => setEditing(null)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await api(
                  editId ? "/jobs/" + editId : "/jobs",
                  editId ? "PUT" : "POST",
                  editing,
                );
                setEditing(null);
              }, "Oportunidade salva.");
            }}
          >
            {newJob && !editId && (
              <p>
                Cole o link e a descrição do anúncio do seu navegador. Confirme
                a empresa, a área e o país antes de usar a vaga para análise.
              </p>
            )}
            <div className="form-grid">
              <Field label="Cargo">
                <input
                  required
                  minLength={3}
                  maxLength={200}
                  value={editing.title}
                  onChange={(e) => patch("title", e.target.value)}
                />
              </Field>
              <Field label="Empresa">
                <input
                  required
                  minLength={2}
                  maxLength={200}
                  value={editing.company}
                  onChange={(e) => patch("company", e.target.value)}
                />
              </Field>
            </div>
            <Field label="Link da vaga (opcional)">
              <input
                type="url"
                disabled={!!editId}
                value={editing.url}
                onChange={(e) => patch("url", e.target.value)}
              />
            </Field>
            <Field
              label="Descrição completa"
              hint="Inclua requisitos e instruções de candidatura exatamente como publicados."
            >
              <textarea
                rows={8}
                required
                minLength={20}
                maxLength={40000}
                value={editing.description}
                onChange={(e) => patch("description", e.target.value)}
              />
            </Field>
            <div className="form-grid">
              <Field label="País de contratação">
                <select
                  value={editing.country || "BR"}
                  onChange={(e) => patch("country", e.target.value)}
                >
                  <option value="BR">Brasil (confirmado)</option>
                  <option value="unknown">Não confirmado</option>
                </select>
              </Field>
              <Field label="Área profissional">
                <select
                  required
                  value={editing.area}
                  onChange={(e) => {
                    patch("area", e.target.value);
                    patch("area_reviewed", false);
                  }}
                >
                  <option value="">Selecione a área</option>
                  {state.areas.map((a) => (
                    <option key={a}>{a}</option>
                  ))}
                </select>
              </Field>
              <Field label="Modalidade">
                <select
                  value={editing.modality}
                  onChange={(e) => patch("modality", e.target.value)}
                >
                  {["Não informado", "Remoto", "Híbrido", "Presencial"].map(
                    (x) => (
                      <option key={x}>{x}</option>
                    ),
                  )}
                </select>
              </Field>
              <Field label="Contratação">
                <select
                  value={editing.contract}
                  onChange={(e) => patch("contract", e.target.value)}
                >
                  <option value="">Não informada</option>
                  {["CLT", "PJ", "Estágio", "Temporário"].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </Field>
              <Field label="Cidade / UF">
                <input
                  value={editing.location}
                  onChange={(e) => patch("location", e.target.value)}
                />
              </Field>
              <Field label="Remuneração mensal (R$)">
                <input
                  type="number"
                  min={0}
                  value={editing.salary ?? ""}
                  onChange={(e) =>
                    patch(
                      "salary",
                      e.target.value === "" ? null : Number(e.target.value),
                    )
                  }
                />
              </Field>
              <Field
                label="E-mail solicitado pelo anúncio"
                hint="Só haverá envio se o endereço e a instrução estiverem na descrição."
              >
                <input
                  type="email"
                  value={editing.recipient}
                  onChange={(e) => patch("recipient", e.target.value)}
                />
              </Field>
            </div>
            <Toggle
              label="Confirmei a área desta oportunidade"
              hint="Considerei as atividades da função, e não o setor da empresa."
              checked={editing.area_reviewed}
              onChange={(v) => patch("area_reviewed", v)}
            />
            <button className="primary" disabled={busy}>
              Salvar oportunidade
            </button>
          </form>
        </Modal>
      )}
      {j && (
        <Modal title={j.title} onClose={() => setSelected("")}>
          {j.pending_reason && (
            <p className="notice">Pendência da rotina: {j.pending_reason}</p>
          )}
          <div className="detail-meta">
            <strong>{j.company}</strong>
            <Badge status={j.status} />
            <span>
              {j.modality} · {j.area || "Área não revisada"}
            </span>
          </div>
          <div className="button-row">
            <button
              className="secondary"
              disabled={
                busy ||
                sentStates.includes(j.status) ||
                j.status === "uncertain"
              }
              onClick={() => {
                setEditing(editableJob(j));
                setEditId(j.id);
                setSelected("");
              }}
            >
              Revisar dados
            </button>
            {j.url && (
              <a
                className="secondary"
                href={j.url}
                target="_blank"
                rel="noreferrer"
              >
                <ArrowUpRight size={16} />
                Abrir vaga
              </a>
            )}
            <button
              className="secondary"
              disabled={
                busy ||
                sentStates.includes(j.status) ||
                j.status === "uncertain"
              }
              onClick={() =>
                act(
                  () => api("/jobs/" + j.id + "/analyze", "POST"),
                  "Análise concluída. Confira as evidências.",
                )
              }
            >
              <RefreshCw size={16} />
              Analisar aderência
            </button>
          </div>
          {j.analysis && (
            <section className="analysis">
              <div className="analysis-scores">
                <div>
                  <span>Aderência</span>
                  <strong>
                    {j.analysis.score != null
                      ? j.analysis.score + "%"
                      : "Bloqueada"}
                  </strong>
                </div>
                <div>
                  <span>Confiança da análise</span>
                  <strong>
                    {j.analysis.confidence != null
                      ? j.analysis.confidence + "%"
                      : "—"}
                  </strong>
                </div>
              </div>
              {j.analysis.blocks?.map((b) => (
                <p className="notice" key={b}>
                  {b}
                </p>
              ))}
              {j.analysis.criteria &&
                Object.entries(j.analysis.criteria).map(([key, c]) => (
                  <details key={key}>
                    <summary>
                      {
                        (
                          {
                            function: "Função e atividades",
                            essential: "Competências essenciais",
                            seniority: "Senioridade",
                            desirable: "Competências desejáveis",
                            preferences: "Preferências",
                          } as Record<string, string>
                        )[key]
                      }{" "}
                      <strong>{c.grade}%</strong>
                    </summary>
                    <p>{c.reason}</p>
                    <blockquote>{c.job_quote}</blockquote>
                    {c.fact_ids.map((id) => (
                      <p className="evidence" key={id}>
                        Perfil:{" "}
                        {state.profile.facts.find((f) => f.id === id)?.text ||
                          "Fato de versão anterior; reanalise."}
                      </p>
                    ))}
                  </details>
                ))}
              {j.analysis.gaps && (
                <p>
                  <strong>Lacunas e observações:</strong> {j.analysis.gaps}
                </p>
              )}
            </section>
          )}
          <div className="button-row">
            {j.analysis?.criteria && (
              <a
                className="secondary"
                href={"/api/jobs/" + j.id + "/resume"}
                target="_blank"
                rel="noreferrer"
              >
                <Download size={16} />
                Currículo PDF
              </a>
            )}
            {!sentStates.includes(j.status) && j.status !== "uncertain" && (
              <>
                <button
                  className="secondary"
                  disabled={busy || !j.analysis?.criteria}
                  onClick={() =>
                    act(
                      () => api("/jobs/" + j.id + "/approve", "POST"),
                      "Candidatura aprovada para esta versão.",
                    )
                  }
                >
                  <Check size={16} />
                  {j.approved ? "Aprovada" : "Aprovar candidatura"}
                </button>
                <button
                  className="primary"
                  disabled={busy || !j.analysis?.criteria || !j.email_eligible}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Enviar o currículo por e-mail para ${j.recipient || "(nenhum destinatário)"}?`,
                      )
                    )
                      act(
                        () => api("/jobs/" + j.id + "/send", "POST"),
                        "Servidor SMTP aceitou a candidatura.",
                      );
                  }}
                >
                  <Mail size={16} />
                  Enviar por e-mail
                </button>
              </>
            )}
          </div>
          {!j.email_eligible && (
            <p className="notice">
              Finalização assistida: abra o site da vaga ou siga as instruções
              do anúncio. O envio SMTP exige destinatário explícito e instruções
              compatíveis. Assuntos literais são preservados; documentos extras
              e instruções ambíguas precisam de preparação manual.
            </p>
          )}
          <details>
            <summary>Descrição original</summary>
            <p className="preserve">{j.description}</p>
          </details>
          <details>
            <summary>Registrar acompanhamento</summary>
            <p>
              Use apenas para registrar uma ação ou retorno que realmente
              aconteceu.
            </p>
            <Field label="Situação">
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                {[
                  "submitted_manual",
                  "receipt",
                  "selection",
                  "interview",
                  "technical",
                  "manager_interview",
                  "offer",
                  "rejected",
                  "withdrawn",
                  "closed",
                ].map((k) => (
                  <option key={k} value={k}>
                    {statusLabels[k]}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="O que aconteceu?">
              <textarea
                value={note}
                minLength={5}
                onChange={(e) => setNote(e.target.value)}
              />
            </Field>
            <button
              className="secondary"
              disabled={busy || note.trim().length < 5}
              onClick={() => {
                if (
                  window.confirm("Confirmar este registro de acompanhamento?")
                )
                  act(
                    () =>
                      api("/jobs/" + j.id + "/status", "POST", {
                        status,
                        note,
                      }),
                    "Acompanhamento registrado.",
                  );
              }}
            >
              Registrar atualização
            </button>
          </details>
          <h3>Histórico</h3>
          <div className="timeline">
            {state.events
              .filter((e) => e.job_id === j.id)
              .map((e, i) => (
                <div key={i}>
                  <small>{date(e.at)}</small>
                  <p>{e.message}</p>
                </div>
              ))}
          </div>
        </Modal>
      )}
    </>
  );
}
function SettingsPage({
  state,
  act,
  busy,
  section,
  onTested,
}: Common & {
  section?: "ai" | "sources" | "email";
  onTested?: () => void;
}) {
  const [s, setS] = useState<Settings>(state.settings),
    [tab, setTab] = useState<string>(section || "ai"),
    [domains, setDomains] = useState(state.settings.allowed_domains.join(", "));
  const [saveFeedback, setSaveFeedback] = useState<Feedback | null>(null);
  const change = (key: keyof Settings, value: unknown) => {
    setSaveFeedback(null);
    setS((x) => ({ ...x, [key]: value }));
  };
  const payload = () => {
    const rest = editableSettings(s);
    return { ...rest, allowed_domains: split(domains) };
  };
  return (
    <div className={section ? undefined : "settings-layout"}>
      {!section && (
        <div className="settings-nav">
          {[
            ["ai", "Inteligência artificial"],
            ["automation", "Candidaturas e limites"],
            ["sources", "Fontes de vagas"],
            ["email", "Envio de e-mail"],
            ["privacy", "Dados e privacidade"],
          ].map(([id, label]) => (
            <button
              className={tab === id ? "active" : ""}
              key={id}
              onClick={() => {
                setSaveFeedback(null);
                setTab(id);
              }}
            >
              {label}
              <ChevronRight size={15} />
            </button>
          ))}
        </div>
      )}
      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault();
          act(
            () => api("/settings", "PUT", payload()),
            "Configurações salvas.",
            setSaveFeedback,
          );
        }}
      >
        {tab === "ai" && (
          <AISettings
            settings={s}
            update={(values) => {
              setSaveFeedback(null);
              setS((x) => ({ ...x, ...values }));
            }}
            onTested={onTested}
            save={() => api("/settings", "PUT", payload())}
            act={act}
            busy={busy}
          />
        )}
        {tab === "automation" && (
          <>
            <h2>Você define a autonomia</h2>
            <p>
              O modo manual consolida a fila. Os modos com automação usam os
              destinos habilitados; formulários experimentais exigem
              configuração própria.
            </p>
            <Field label="Modo de candidatura">
              <select
                value={s.mode}
                onChange={(e) => change("mode", e.target.value)}
              >
                <option value="manual">
                  Somente consolidar; eu me candidato
                </option>
                <option value="review">
                  Quero revisar e aprovar cada candidatura
                </option>
                <option value="automatic">
                  Quero envio automático nos conectores habilitados
                </option>
              </select>
            </Field>
            <div className="form-grid">
              <Field label="Aderência mínima (%)">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={s.threshold}
                  onChange={(e) => change("threshold", Number(e.target.value))}
                />
              </Field>
              <Field label="Confiança mínima da análise (%)">
                <input
                  type="number"
                  min={50}
                  max={100}
                  value={s.minimum_confidence}
                  onChange={(e) =>
                    change("minimum_confidence", Number(e.target.value))
                  }
                />
              </Field>
              <Field label="Tentativas de envio por dia">
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={s.daily_limit}
                  onChange={(e) =>
                    change("daily_limit", Number(e.target.value))
                  }
                />
              </Field>
              <Field label="Vagas processadas por execução">
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={s.max_jobs_per_run}
                  onChange={(e) =>
                    change("max_jobs_per_run", Number(e.target.value))
                  }
                />
              </Field>
              <Field label="Intervalo entre vagas (segundos)">
                <input
                  type="number"
                  min={5}
                  max={600}
                  value={s.interval_seconds}
                  onChange={(e) =>
                    change("interval_seconds", Number(e.target.value))
                  }
                />
              </Field>
            </div>
            <Toggle
              label="Rotina pausada"
              hint="A pausa suspende a rotina agendada e os envios. A coleta manual de vagas continua disponível."
              checked={s.paused}
              onChange={(v) => change("paused", v)}
            />
            <div className="notice">
              Áreas excluídas, dados desconhecidos e respostas não verificadas
              não são liberados ao reduzir a aderência.
            </div>
          </>
        )}
        {tab === "sources" && (
          <>
            <h2>Suas fontes de oportunidades</h2>
            <p>
              Autorize os domínios exatos e adicione feeds RSS ou JSON. Páginas
              individuais precisam expor JobPosting.
            </p>
            <Field
              label="Domínios autorizados"
              hint="Separe por vírgula. Ex.: carreiras.empresa.com.br. Redirecionamentos precisam estar autorizados também."
            >
              <textarea
                value={domains}
                onChange={(e) => setDomains(e.target.value)}
              />
            </Field>
            {s.sources.map((source, i) => (
              <div className="source-card" key={i}>
                <Field
                  label="Nome da fonte / empresa"
                  hint="Em Greenhouse e Lever, use o nome da empresa; ele será usado para identificar as vagas."
                >
                  <input
                    required
                    value={source.name}
                    onChange={(e) =>
                      change(
                        "sources",
                        s.sources.map((x, n) =>
                          n === i ? { ...x, name: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </Field>
                <Field label="Tipo de fonte">
                  <select
                    value={source.kind || "feed"}
                    onChange={(e) =>
                      change(
                        "sources",
                        s.sources.map((x, n) =>
                          n === i
                            ? { ...x, kind: e.target.value, url: "", board: "" }
                            : x,
                        ),
                      )
                    }
                  >
                    <option value="feed">Feed RSS/JSON</option>
                    <option value="company">
                      Página pública de empresa (JobPosting)
                    </option>
                    <option value="greenhouse">
                      Quadro público Greenhouse
                    </option>
                    <option value="lever">Quadro público Lever</option>
                  </select>
                </Field>
                {["greenhouse", "lever"].includes(source.kind || "") ? (
                  <Field
                    label="Identificador do quadro da empresa"
                    hint="É o nome da empresa no endereço da página de carreiras. O endereço da API será montado automaticamente."
                  >
                    <input
                      required
                      pattern="[a-zA-Z0-9_-]+"
                      value={source.board || ""}
                      onChange={(e) =>
                        change(
                          "sources",
                          s.sources.map((x, n) =>
                            n === i ? { ...x, board: e.target.value } : x,
                          ),
                        )
                      }
                    />
                  </Field>
                ) : (
                  <Field label="Endereço HTTPS do feed ou página">
                    <input
                      type="url"
                      required
                      value={source.url}
                      onChange={(e) =>
                        change(
                          "sources",
                          s.sources.map((x, n) =>
                            n === i ? { ...x, url: e.target.value } : x,
                          ),
                        )
                      }
                    />
                  </Field>
                )}
                <Toggle
                  label="Fonte habilitada"
                  checked={source.enabled}
                  onChange={(v) =>
                    change(
                      "sources",
                      s.sources.map((x, n) =>
                        n === i ? { ...x, enabled: v } : x,
                      ),
                    )
                  }
                />
                <button
                  className="text-button"
                  type="button"
                  onClick={() =>
                    change(
                      "sources",
                      s.sources.filter((_, n) => n !== i),
                    )
                  }
                >
                  <Trash2 size={15} />
                  Remover fonte
                </button>
              </div>
            ))}
            <button
              className="secondary"
              type="button"
              onClick={() =>
                change("sources", [
                  ...s.sources,
                  { name: "", url: "", enabled: true },
                ])
              }
            >
              <Plus size={17} />
              Adicionar fonte
            </button>
            <div className="notice">
              Para pesquisar no LinkedIn ou Indeed, selecione o portal na rotina
              e entre pelo navegador interno. Para a Gupy, adicione a página
              pública da empresa como fonte e habilite Gupy na rotina.
            </div>
          </>
        )}
        {tab === "email" && (
          <>
            <h2>Candidaturas por e-mail</h2>
            <p>
              Use uma conta de sua propriedade. Para o teste inicial,
              recomendamos uma caixa de teste e um destinatário que você
              controla.
            </p>
            <Toggle
              label="Habilitar envio de candidaturas por SMTP"
              checked={s.email_enabled}
              onChange={(v) => change("email_enabled", v)}
            />
            <div className="form-grid">
              <Field label="Servidor SMTP">
                <input
                  value={s.smtp_host}
                  onChange={(e) => change("smtp_host", e.target.value)}
                />
              </Field>
              <Field label="Porta">
                <input
                  type="number"
                  min={1}
                  max={65535}
                  value={s.smtp_port}
                  onChange={(e) => change("smtp_port", Number(e.target.value))}
                />
              </Field>
              <Field label="Segurança">
                <select
                  value={s.smtp_security}
                  onChange={(e) => change("smtp_security", e.target.value)}
                >
                  <option value="ssl">TLS direto (normalmente 465)</option>
                  <option value="starttls">STARTTLS (normalmente 587)</option>
                </select>
              </Field>
              <Field label="E-mail do remetente">
                <input
                  type="email"
                  value={s.smtp_from}
                  onChange={(e) => change("smtp_from", e.target.value)}
                />
              </Field>
            </div>
            <Field label="Usuário SMTP">
              <input
                autoComplete="off"
                value={s.smtp_user}
                onChange={(e) => change("smtp_user", e.target.value)}
              />
            </Field>
            <Field
              label="Senha de aplicativo SMTP"
              hint={
                s.smtp_password_configured
                  ? "Senha salva. Deixe vazio para manter."
                  : "Use senha de aplicativo quando disponível; nunca informe a senha em uma vaga."
              }
            >
              <input
                type="password"
                autoComplete="new-password"
                value={s.smtp_password}
                onChange={(e) => change("smtp_password", e.target.value)}
              />
            </Field>
            {s.smtp_password_configured && (
              <button
                type="button"
                className="text-button"
                onClick={() =>
                  act(async () => {
                    await api("/settings/clear-secret", "POST", {
                      name: "smtp_password",
                    });
                    change("smtp_password_configured", false);
                    change("smtp_password", "");
                  }, "Senha SMTP removida.")
                }
              >
                Remover senha salva
              </button>
            )}
            <div className="notice">
              Alguns provedores exigem OAuth e não aceitam senha de aplicativo.
              OAuth ainda não está disponível. O aceite pelo SMTP não confirma
              entrega ou leitura.
            </div>
          </>
        )}
        {tab === "email" && (
          <section className="source-card">
            <h3>Leitura de alertas e respostas por IMAP</h3>
            <p>
              Leitura com TLS e senha de aplicativo. Provedores que exigem OAuth
              ainda não são suportados. Nenhuma mensagem é enviada por este
              recurso.
            </p>
            <Toggle
              label="Consultar respostas periodicamente"
              checked={s.imap_enabled}
              onChange={(v) => change("imap_enabled", v)}
            />
            <div className="form-grid">
              <Field label="Servidor IMAP">
                <input
                  value={s.imap_host}
                  onChange={(e) => change("imap_host", e.target.value)}
                />
              </Field>
              <Field label="Porta TLS">
                <input
                  type="number"
                  min={1}
                  max={65535}
                  value={s.imap_port}
                  onChange={(e) => change("imap_port", Number(e.target.value))}
                />
              </Field>
            </div>
            <Field label="Usuário do e-mail">
              <input
                value={s.imap_user}
                onChange={(e) => change("imap_user", e.target.value)}
              />
            </Field>
            <Field
              label="Senha de aplicativo IMAP"
              hint={
                s.imap_password_configured
                  ? "Já existe senha salva para esta conta. Vazio mantém se servidor e usuário não mudarem."
                  : "Consulte o seu provedor para habilitar IMAP com senha de aplicativo."
              }
            >
              <input
                type="password"
                autoComplete="new-password"
                value={s.imap_password}
                onChange={(e) => change("imap_password", e.target.value)}
              />
            </Field>
            {s.imap_password_configured && (
              <button
                type="button"
                className="text-button"
                onClick={() =>
                  act(async () => {
                    await api("/settings/clear-secret", "POST", {
                      name: "imap_password",
                    });
                    change("imap_password_configured", false);
                  }, "Senha IMAP removida.")
                }
              >
                Remover senha IMAP salva
              </button>
            )}
            <div className="form-grid">
              <Field label="Pasta">
                <input
                  value={s.imap_folder}
                  onChange={(e) => change("imap_folder", e.target.value)}
                />
              </Field>
              <Field label="Intervalo (minutos)">
                <input
                  type="number"
                  min={5}
                  max={1440}
                  value={s.imap_poll_minutes}
                  onChange={(e) =>
                    change("imap_poll_minutes", Number(e.target.value))
                  }
                />
              </Field>
              <Field label="Mensagens recentes por consulta">
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={s.imap_max_messages}
                  onChange={(e) =>
                    change("imap_max_messages", Number(e.target.value))
                  }
                />
              </Field>
            </div>
            <Toggle
              label="Atualizar etapas automaticamente nos casos reconhecidos"
              hint="Exige resposta da mesma conversa, mesmo remetente da candidatura e etapa identificada. Os demais casos viram sugestões para revisão. Não aceita entrevistas nem faz testes."
              checked={s.auto_followup}
              onChange={(v) => change("auto_followup", v)}
            />
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api("/settings", "PUT", payload());
                  await api("/followups/sync", "POST");
                }, "Caixa de e-mail consultada.")
              }
            >
              Salvar e consultar respostas
            </button>
            {state.mail_status.error && (
              <p className="notice">{state.mail_status.error}</p>
            )}
          </section>
        )}
        {tab === "privacy" && (
          <>
            <h2>Seus dados, sob seu controle</h2>
            <p>
              Perfil, vagas, documentos e credenciais são armazenados nesta
              instalação, com conteúdo criptografado. A chave local também
              precisa ser protegida.
            </p>
            <a className="secondary" href="/api/export">
              <Download size={17} />
              Exportar meus dados
            </a>
            <h3>Backup completo</h3>
            <p>
              Encerre a aplicação e copie a pasta de dados inteira, incluindo o
              banco e vault.key. A exportação acima não inclui credenciais e não
              substitui o backup.
            </p>
            <h3>Para encerrar o uso</h3>
            <p>
              Exporte seus dados, feche a aplicação e remova a pasta de dados
              conforme o guia. Desinstalar o programa preserva os dados por
              segurança.
            </p>
            <h3>Integrações desta versão</h3>
            <ul>
              <li>PDF do LinkedIn e revisão do perfil.</li>
              <li>IA por endpoint compatível e SMTP TLS.</li>
              <li>Importação de respostas por arquivo .eml.</li>
              <li>
                LinkedIn, Gupy e sites externos: finalização assistida pelo
                usuário.
              </li>
            </ul>
          </>
        )}
        {tab !== "privacy" && (
          <div className="form-footer">
            <button className="primary" disabled={busy}>
              <Check size={17} />
              Salvar configurações
            </button>
            <ActionFeedback feedback={saveFeedback} />
          </div>
        )}
      </form>
    </div>
  );
}
function SchedulePage({ state, act, busy }: Common) {
  const [s, setS] = useState(state.settings);
  const [saveFeedback, setSaveFeedback] = useState<Feedback | null>(null);
  const change = (k: keyof Settings, v: unknown) =>
    setS((x) => ({ ...x, [k]: v }));
  return (
    <>
      <div className="content-grid">
        <form
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            const payload = editableSettings(s);
            act(
              () => api("/settings", "PUT", payload),
              "Agenda salva.",
              setSaveFeedback,
            );
          }}
        >
          <div className="panel-heading">
            <div>
              <h2>Uma rotina que cabe no seu dia</h2>
              <p>O programa precisa estar aberto e o computador ligado.</p>
            </div>
            <CalendarClock size={23} />
          </div>
          <Toggle
            label="Executar nos horários programados"
            checked={s.schedule_enabled}
            onChange={(v) => change("schedule_enabled", v)}
          />
          <p className="field-title">Dias da semana</p>
          <div className="chips">
            {["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"].map((d, i) => (
              <button
                type="button"
                className={s.weekdays.includes(i) ? "chip selected" : "chip"}
                key={d}
                onClick={() =>
                  change(
                    "weekdays",
                    s.weekdays.includes(i)
                      ? s.weekdays.filter((x) => x !== i)
                      : [...s.weekdays, i],
                  )
                }
              >
                {d}
              </button>
            ))}
          </div>
          <div className="form-grid">
            <Field label="Horário de início">
              <input
                type="time"
                required
                value={s.time}
                onChange={(e) => change("time", e.target.value)}
              />
            </Field>
            <Field label="Fuso horário">
              <select
                value={s.timezone}
                onChange={(e) => change("timezone", e.target.value)}
              >
                {[
                  "America/Sao_Paulo",
                  "America/Manaus",
                  "America/Rio_Branco",
                  "America/Belem",
                  "America/Noronha",
                ].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </Field>
          </div>
          <Toggle
            label="Rotina pausada"
            checked={s.paused}
            onChange={(v) => change("paused", v)}
          />
          <div className="notice">
            Ao ligar ou acordar depois do horário, a rotina pode executar no
            mesmo dia, se ele estiver habilitado. Execuções de dias anteriores
            não são acumuladas.
          </div>
          <button className="primary" disabled={busy}>
            Salvar agenda
          </button>
          <ActionFeedback feedback={saveFeedback} />
        </form>
        <section className="panel aside-note">
          <h2>Controle da rotina</h2>
          <p>
            {state.running
              ? "Há uma execução em andamento."
              : "Nenhuma execução em andamento."}
          </p>
          <div className="stack">
            <button
              className="primary"
              disabled={busy || state.running}
              onClick={() =>
                act(() => api("/runs", "POST"), "Execução iniciada.")
              }
            >
              <Play size={16} />
              Executar agora
            </button>
            <button
              className="secondary"
              disabled={busy || state.settings.paused}
              onClick={() =>
                act(
                  () => api("/pause", "POST"),
                  "Rotina pausada. A oportunidade em andamento será finalizada antes de parar.",
                )
              }
            >
              <Pause size={16} />
              Pausar rotina
            </button>
          </div>
          <p>
            Uma execução por vez, com limite diário de tentativas e de chamadas
            de IA.
          </p>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Histórico de execuções</h2>
          <span className="subtle-pill">{state.runs.length} registros</span>
        </div>
        {!state.runs.length ? (
          <div className="empty">
            <Clock3 size={29} />
            <h3>Nenhuma execução ainda</h3>
            <p>Configure seu perfil, fontes e IA antes de retomar a rotina.</p>
          </div>
        ) : (
          state.runs.map((r) => (
            <details key={r.id}>
              <summary>
                {date(r.started_at)}{" "}
                <span className="subtle-pill">
                  {(
                    {
                      running: "Em execução",
                      completed: "Concluída",
                      paused: "Pausada",
                      failed: "Falhou",
                    } as Record<string, string>
                  )[r.status] || r.status}
                </span>
              </summary>
              <p>
                {r.imported} vagas importadas · {r.analyzed} analisadas ·{" "}
                {r.sent} concluídas por conector
              </p>
              {r.errors.map((error, i) => (
                <p className="notice" key={i}>
                  {error}
                </p>
              ))}
            </details>
          ))
        )}
      </section>
    </>
  );
}
function Followups({ state, act, busy }: Common) {
  const [selected, setSelected] = useState<Followup | null>(null),
    [jobId, setJobId] = useState(""),
    [status, setStatus] = useState("selection");
  return (
    <>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Recebeu uma resposta?</h2>
            <p>
              Exporte o e-mail como .eml e importe. Você confirma a associação e
              a etapa.
            </p>
          </div>
          <Mail size={22} />
        </div>
        <label className="upload-zone compact">
          <Upload size={24} />
          <strong>Importar resposta por e-mail</strong>
          <span>Arquivo .eml · até 2 MB</span>
          <input
            type="file"
            accept=".eml,message/rfc822"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              const data = new FormData();
              data.append("file", f);
              act(
                () => api("/followups/import", "POST", data),
                "Resposta importada. Revise a associação sugerida.",
              );
              e.target.value = "";
            }}
          />
        </label>
        <div className="notice">
          Ative a consulta periódica IMAP em Configurações para acompanhar
          respostas automaticamente. Nenhuma entrevista será aceita nem resposta
          enviada por este fluxo.
        </div>
      </section>
      <section className="panel">
        <h2>Respostas importadas</h2>
        {!state.followups.length ? (
          <div className="empty">
            <Inbox size={32} />
            <h3>Um lugar para os próximos passos</h3>
            <p>
              Os retornos importados aparecerão aqui. Você também pode atualizar
              cada candidatura manualmente.
            </p>
          </div>
        ) : (
          state.followups.map((f) => (
            <div key={f.id} className="followup-row">
              <div>
                <strong>{f.subject || "Sem assunto"}</strong>
                <small>{f.from}</small>
              </div>
              {f.confirmed ? (
                <span className="badge green">
                  {f.method === "email_thread"
                    ? "Identificado em resposta"
                    : "Confirmado"}
                </span>
              ) : (
                <button
                  className="secondary"
                  onClick={() => {
                    setSelected(f);
                    setJobId(f.candidates.length === 1 ? f.candidates[0] : "");
                    setStatus(f.suggested_status);
                  }}
                >
                  Revisar retorno
                </button>
              )}
            </div>
          ))
        )}
      </section>
      {selected && (
        <Modal title="Revisar retorno" onClose={() => setSelected(null)}>
          <p className="preserve">{selected.excerpt}</p>
          <p className="notice">
            Confira o conteúdo e escolha a candidatura correta. Sugestões podem
            estar erradas.
          </p>
          <Field label="Candidatura">
            <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">Selecione</option>
              {state.jobs
                .filter(
                  (j) =>
                    sentStates.includes(j.status) || j.status === "uncertain",
                )
                .map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title} — {j.company}
                  </option>
                ))}
            </select>
          </Field>
          <Field label="Etapa confirmada">
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {[
                "receipt",
                "selection",
                "interview",
                "technical",
                "manager_interview",
                "offer",
                "rejected",
                "withdrawn",
                "closed",
              ].map((k) => (
                <option key={k} value={k}>
                  {statusLabels[k]}
                </option>
              ))}
            </select>
          </Field>
          <button
            className="primary"
            disabled={busy || !jobId}
            onClick={() =>
              act(async () => {
                await api("/followups/" + selected.id + "/confirm", "POST", {
                  job_id: jobId,
                  status,
                });
                setSelected(null);
              }, "Retorno confirmado.")
            }
          >
            Confirmar associação e etapa
          </button>
        </Modal>
      )}
    </>
  );
}
function Help() {
  return (
    <div className="help">
      <section className="panel">
        <span className="mini-icon">
          <BookOpen size={25} />
        </span>
        <h2>Primeiro teste, passo a passo</h2>
        <ol>
          <li>
            Em <strong>Configurações</strong>, informe o endereço e modelo de
            IA. Autorize o uso dos dados e teste a conexão.
          </li>
          <li>
            Em <strong>Meu perfil</strong>, importe o PDF do LinkedIn, extraia
            sugestões e confira cada fato. Escolha as áreas, os cargos e as
            preferências. Confirme e salve.
          </li>
          <li>
            Em <strong>Oportunidades</strong>, cadastre uma vaga de teste com
            descrição completa. Confirme a área profissional.
          </li>
          <li>
            Abra a oportunidade e selecione <strong>Analisar aderência</strong>.
            Confira as justificativas, evidências e lacunas.
          </li>
          <li>
            Baixe o currículo em PDF e confira seu conteúdo. Para testar
            bloqueios, adicione uma vaga de uma área excluída.
          </li>
          <li>
            Para testar e-mail, use remetente e destinatário que você controla.
            A descrição precisa pedir explicitamente o envio do currículo para
            aquele endereço.
          </li>
          <li>
            Configure SMTP, mantenha o modo de aprovação, aprove a candidatura e
            retome a rotina antes de enviar.
          </li>
          <li>
            Depois do teste, pause novamente. Só habilite envio automático
            quando estiver confortável com os critérios.
          </li>
        </ol>
      </section>
      <section className="panel">
        <h2>O que esta versão já permite</h2>
        <p>
          Perfil por PDF, revisão factual, análise por IA, filtros obrigatórios,
          currículo em PDF, fontes RSS/JSON/JobPosting, agenda, envio SMTP e
          acompanhamento manual ou por .eml.
        </p>
        <h3>LinkedIn e Gupy</h3>
        <p>
          O fluxo é assistido: prepare os documentos aqui e finalize no site. O
          navegador interno permite login manual e sessões criptografadas. O
          preenchimento automático desses dois portais ainda está pendente.
          InHire possui um formulário direto experimental. Verificações e testes
          seletivos exigem sua intervenção.
        </p>
        <h3>Privacidade e backup</h3>
        <p>
          No Windows os dados ficam em %LOCALAPPDATA%\Application Assistant.
          Encerre a aplicação antes de copiar a pasta inteira para backup. Banco
          e vault.key precisam ser guardados juntos em local seguro.
        </p>
        <h3>Rotina e computador desligado</h3>
        <p>
          O computador precisa estar ligado, conectado à internet e sem
          suspensão, com o aplicativo aberto. Para execução contínua, utilize a
          instalação Docker em servidor próprio.
        </p>
        <h3>Resultado incerto</h3>
        <p>
          Uma falha de rede durante SMTP pode acontecer depois de o servidor
          aceitar o e-mail. A aplicação não repete esse envio. Confira
          manualmente e registre a situação na candidatura.
        </p>
        <h3>Custos de IA</h3>
        <p>
          São definidos pelo provedor escolhido. O limite diário conta
          tentativas de chamada, inclusive falhas. Para modelos locais,
          configure um endpoint compatível do Ollama.
        </p>
      </section>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
