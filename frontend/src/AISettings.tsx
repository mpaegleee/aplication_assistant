import { useEffect, useState } from "react";
import { RefreshCw, ExternalLink } from "lucide-react";
import { ActionFeedback, type Action, type Feedback } from "./ActionFeedback";
import { api } from "./api";
import type { AIModel, AIProvider, Settings } from "./types";

type Props = {
  settings: Settings;
  update: (values: Partial<Settings>) => void;
  save: () => Promise<unknown>;
  act: Action;
  busy: boolean;
  onTested?: () => void;
};
const normalized = (url: string) =>
  url.replace(/\/+$/, "").replace("127.0.0.1", "localhost");

export function AISettings({
  settings: s,
  update,
  save,
  act,
  busy,
  onTested,
}: Props) {
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [providerId, setProviderId] = useState("");
  const [catalog, setCatalog] = useState<AIModel[] | null>(null);
  const [manual, setManual] = useState(false);
  const [search, setSearch] = useState("");
  const [problem, setProblem] = useState("");
  const [modelsFeedback, setModelsFeedback] = useState<Feedback | null>(null);
  const [testFeedback, setTestFeedback] = useState<Feedback | null>(null);
  useEffect(() => {
    let active = true;
    api<{ providers: AIProvider[] }>("/ai/providers")
      .then(({ providers: items }) => {
        if (!active) return;
        setProviders(items);
        const found = items.find(
          (p) =>
            p.url &&
            (normalized(p.url) === normalized(s.ai_url) ||
              (p.id === "deepseek" && normalized(s.ai_url) === p.url + "/v1")),
        );
        if (s.ai_model || s.ai_key_configured || !found)
          setProviderId(found?.id || "custom");
      })
      .catch((e) => {
        if (active) setProblem(e.message);
      });
    return () => {
      active = false;
    };
    // Infer once from the saved installation; later changes are explicit user actions.
  }, []);
  const provider = providers.find((p) => p.id === providerId);
  const missing =
    catalog !== null &&
    !!s.ai_model &&
    !catalog.some((m) => m.id === s.ai_model);
  const visible = (catalog || []).filter(
    (m) =>
      `${m.name} ${m.id}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()) || m.id === s.ai_model,
  );
  const changeProvider = (id: string) => {
    const selected = providers.find((p) => p.id === id);
    setProviderId(id);
    setCatalog(null);
    setSearch("");
    setProblem("");
    setModelsFeedback(null);
    setTestFeedback(null);
    setManual(false);
    update({
      ai_url: selected?.url || s.ai_url,
      ai_model: "",
      ai_key: "",
      ai_key_configured: false,
      ai_consent: false,
    });
  };
  const loadModels = () =>
    act(
      async () => {
        setCatalog(null);
        setSearch("");
        const result = await api<{ models: AIModel[] }>("/ai/models", "POST", {
          ai_url: s.ai_url,
          ai_key: s.ai_key,
        });
        setCatalog(result.models);
      },
      "Lista de modelos carregada. Escolha o modelo e teste a conexão.",
      setModelsFeedback,
    );
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>Escolha como usar a IA</h2>
          <p>Selecione seu serviço. O endereço é configurado para você.</p>
        </div>
      </div>
      {problem && (
        <p className="error" role="alert">
          {problem}
        </p>
      )}
      <label className="field">
        <span>1. Onde você usa a IA?</span>
        <select
          value={providerId}
          disabled={busy || !providers.length}
          onChange={(e) => changeProvider(e.target.value)}
        >
          <option value="" disabled>
            Selecione um serviço
          </option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <small>
          Escolha o serviço onde você criou a chave, mesmo que o modelo tenha o
          nome de outra empresa.
        </small>
      </label>
      {provider && (
        <>
          <div className="notice">
            <strong>{provider.name}</strong>
            <p>{provider.help}</p>
            {provider.docs && (
              <a href={provider.docs} target="_blank" rel="noreferrer">
                Ajuda oficial do serviço <ExternalLink size={13} />
              </a>
            )}
          </div>
          {providerId === "custom" ? (
            <label className="field">
              <span>Endereço base da API (avançado)</span>
              <input
                type="url"
                required
                value={s.ai_url}
                onChange={(e) => {
                  setCatalog(null);
                  update({
                    ai_url: e.target.value,
                    ai_key: "",
                    ai_key_configured: false,
                    ai_model: "",
                    ai_consent: false,
                  });
                }}
              />
              <small>
                Use o endereço compatível com Chat Completions fornecido pelo
                serviço, normalmente com /v1.
              </small>
            </label>
          ) : (
            <details>
              <summary>Ver endereço configurado automaticamente</summary>
              <label className="field">
                <span>Endereço da API</span>
                <input readOnly value={s.ai_url} />
                <small>
                  Para outra porta ou servidor, selecione “Outro serviço
                  compatível”.
                </small>
              </label>
            </details>
          )}
          <label className="field">
            <span>
              2.{" "}
              {provider.local
                ? "Chave da API (opcional para serviço local)"
                : `Chave da API ${provider.name.split(" (")[0]}`}
            </span>
            <input
              type="password"
              autoComplete="new-password"
              value={s.ai_key}
              onChange={(e) => {
                setCatalog(null);
                update({ ai_key: e.target.value });
              }}
            />
            <small>
              {s.ai_key_configured
                ? "Chave já salva para este endereço. Deixe vazio para mantê-la."
                : provider.local
                  ? "Normalmente pode ficar vazio. Não use aqui uma chave de outro serviço."
                  : "Cole uma chave criada nesse serviço. Ao trocar de endereço, informe a chave correspondente."}
            </small>
          </label>
          {s.ai_key_configured && (
            <button
              type="button"
              className="text-button"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api("/settings/clear-secret", "POST", {
                    name: "ai_key",
                  });
                  update({ ai_key: "", ai_key_configured: false });
                  setCatalog(null);
                }, "Chave removida.")
              }
            >
              Remover chave salva
            </button>
          )}
          <div className="button-row">
            <button
              type="button"
              className="secondary"
              disabled={
                busy ||
                !s.ai_url ||
                (!provider.local &&
                  providerId !== "custom" &&
                  !s.ai_key &&
                  !s.ai_key_configured)
              }
              onClick={loadModels}
            >
              <RefreshCw size={16} />
              Carregar modelos disponíveis
            </button>
            <small>
              Consulta o serviço sem enviar seu currículo e sem consumir o
              limite de análises.
            </small>
          </div>
          <ActionFeedback feedback={modelsFeedback} />
          {!manual && (
            <>
              {catalog && catalog.length > 15 && (
                <label className="field">
                  <span>Buscar na lista de modelos</span>
                  <input
                    type="search"
                    value={search}
                    placeholder="Ex.: DeepSeek"
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
              )}
              <label className="field">
                <span>3. Qual modelo você quer usar?</span>
                <select
                  value={s.ai_model}
                  disabled={busy || !catalog?.length}
                  onChange={(e) => update({ ai_model: e.target.value })}
                >
                  <option value="">
                    {catalog
                      ? "Selecione um modelo"
                      : "Clique em Carregar modelos disponíveis"}
                  </option>
                  {s.ai_model && !catalog?.some((m) => m.id === s.ai_model) && (
                    <option value={s.ai_model}>
                      Modelo anterior: {s.ai_model}
                      {missing ? " (não listado)" : ""}
                    </option>
                  )}
                  {visible.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name === m.id ? m.id : `${m.name} — ${m.id}`}
                    </option>
                  ))}
                </select>
                <small>
                  {catalog
                    ? `${catalog.length} modelos retornados. O teste abaixo verifica a resposta em JSON.`
                    : "A lista usa os identificadores reais do serviço. Nenhum modelo pago é escolhido automaticamente."}
                </small>
              </label>
              {catalog?.length === 0 && (
                <p className="notice">
                  Nenhum modelo de texto foi retornado.{" "}
                  {provider.local
                    ? "Instale ou carregue um modelo no programa local e atualize a lista."
                    : "Confira os modelos disponíveis na sua conta ou use o modo manual."}
                </p>
              )}
              {missing && (
                <p className="notice">
                  O modelo anterior não apareceu neste serviço. Escolha um
                  modelo da lista ou use a configuração manual se seu provedor
                  confirmar esse identificador.
                </p>
              )}
            </>
          )}
          <label className="toggle-row">
            <span>
              <strong>Informar modelo manualmente (avançado)</strong>
              <small>
                Use se o serviço não oferecer uma lista ou se você já conhece o
                identificador exato.
              </small>
            </span>
            <input
              type="checkbox"
              checked={manual}
              onChange={(e) => setManual(e.target.checked)}
            />
          </label>
          {manual && (
            <label className="field">
              <span>Identificador exato do modelo</span>
              <input
                value={s.ai_model}
                onChange={(e) => update({ ai_model: e.target.value })}
                placeholder="Identificador informado pelo serviço"
              />
            </label>
          )}
          <label className="field">
            <span>Máximo de chamadas de IA por dia</span>
            <input
              type="number"
              min={1}
              max={1000}
              value={s.ai_daily_limit}
              onChange={(e) =>
                update({ ai_daily_limit: Number(e.target.value) })
              }
            />
          </label>
          <label className="toggle-row">
            <span>
              <strong>
                Autorizo usar meu perfil e as vagas com este serviço
              </strong>
              <small>
                {provider.local
                  ? "Ollama e LM Studio são acessados no endereço local configurado."
                  : "O provedor externo recebe os dados necessários para a análise e pode cobrar pelo uso."}
              </small>
            </span>
            <input
              type="checkbox"
              checked={s.ai_consent}
              onChange={(e) => update({ ai_consent: e.target.checked })}
            />
          </label>
          <div className="button-row">
            <button
              type="button"
              className="secondary"
              disabled={
                busy || !s.ai_model || !s.ai_consent || (!manual && missing)
              }
              onClick={() =>
                act(
                  async () => {
                    await save();
                    await api("/ai/test", "POST");
                    onTested?.();
                  },
                  "Conexão e resposta JSON validadas.",
                  setTestFeedback,
                )
              }
            >
              <RefreshCw size={16} />
              Salvar e testar conexão
            </button>
            <ActionFeedback feedback={testFeedback} />
          </div>
        </>
      )}
    </>
  );
}
