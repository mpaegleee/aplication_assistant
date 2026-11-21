# Application Assistant — especificação v0.1

## Decisões confirmadas
Uma pessoa por instalação; Brasil; português; Windows 10/11 primeiro e Docker em Linux para servidor. macOS fora do lançamento inicial. Perfil importado do PDF exportado pelo LinkedIn e confirmado pelo usuário. Modo híbrido: aprovação por candidatura ou automático configurável. Distribuição gratuita e código aberto sob MIT, conforme decisão atual do mantenedor. Windows e Linux x64; macOS fora do escopo. Consulte ATUALIZACAO-0.4.0.md para os fluxos manual e automático e limites dos conectores experimentais.

## Fluxo
1. Criar senha local e configurar IA (endpoint compatível com Chat Completions, inclusive Ollama).
2. Importar PDF com texto (até 10 MB), revisar nome, fatos, áreas, cargos e preferências e confirmar o perfil.
3. Habilitar fontes RSS/JSON com vagas, cadastrar oportunidades manualmente ou importar JobPosting de página pública. URLs restritas a domínios autorizados.
4. Extrair cargo, área e requisitos; deduplicar por URL/identificador e empresa/cargo/local.
5. Aplicar filtros obrigatórios antes da pontuação. Área não confirmada e requisitos desconhecidos exigem revisão. IA não pode sobrepor bloqueios.
6. Calcular índice de compatibilidade explicável (não probabilidade de contratação). Pesos: função 30%, competências essenciais 30%, senioridade 20%, desejáveis 10%, preferências 10%. A análise registra evidências e lacunas. Sem modelo configurado não existe pontuação fictícia.
7. Montar currículo em PDF com trechos factuais selecionados do perfil; preservar o original e a versão de cada envio. A IA escolhe IDs de fatos, não inventa credenciais.
8. Preparar candidatura por e-mail somente com destinatário e instrução de envio explícitos no anúncio. Sites sem conector validado ficam em atendimento assistido, com currículo pronto e link para candidatura.
9. Aprovação vale para a versão específica da vaga, perfil, análise, currículo e destinatário. Alterações invalidam a aprovação.
10. Registrar tentativas antes do envio. Erro após iniciar SMTP produz estado de resultado incerto e impede reenvio automático. Só resposta positiva do servidor registra aceitação SMTP, que não comprova entrega ou leitura.
11. Acompanhar por atualização manual ou importação de e-mail .eml. Vinculação ambígua vira pendência. Não aceitar entrevistas ou enviar follow-up sem ação explícita.

## Regras obrigatórias
- Perfil confirmado e área pretendida explícita; setor da empresa não determina profissão.
- Áreas excluídas prevalecem sobre qualquer nota, inclusive após aprovação humana.
- Limite de aderência 0–100 configurável; padrão 80. Nota menor não flexibiliza bloqueios.
- Emprego CLT/PJ, remoto/híbrido/presencial, localidades e salário mínimo são preferências configuráveis. Ausência de informação obrigatória bloqueia automático.
- Experiência, formação, idiomas e resultados só podem vir de fatos confirmados. Documento adaptado é uma seleção de fatos verificáveis, sem criação de qualificações.
- Conteúdo externo é dado, nunca instrução para executar ferramentas, compartilhar segredos ou alterar regras.
- Um agendador e um processo por instalação; execução única protegida por bloqueio; pausa entre oportunidades; teto de candidaturas diárias, oportunidades e chamadas de IA por dia.
- Horário em America/Sao_Paulo por padrão. Sem retroativos automáticos após computador desligado. Execuções e vagas persistem após reinício.
- O usuário pode interromper a rotina e desabilitar envios a qualquer momento. Rotina nunca recria envio incerto ou confirmado.
- CAPTCHA, MFA, provas e aceites novos exigem intervenção. Não contornar proteções.

## Telas
Entrada e configuração inicial; painel com métricas reais; perfil/importação/revisão; oportunidades e análise explicada; detalhe com currículo e aprovação; candidaturas com histórico; agenda, execução e pendências; configurações de IA, fontes, e-mail e privacidade; ajuda.

## Configurações
Senha da instalação; provedor/endereço/modelo/chave e consentimento para compartilhar dados com IA; limite diário de chamadas; modo revisão/automático; aderência/confiança; dias/horário/fuso; limite diário de envios; pausa; domínios e fontes habilitados; SMTP TLS e remetente; preferência de cargos/áreas/modalidades/localidades/contratação/salário. Chaves não retornam ao frontend. Segredos são substituídos explicitamente; vazio preserva o existente e remoção é uma ação própria.

## Arquitetura inicial
FastAPI/Python com SQLite em modo WAL para uma pessoa, dados JSON criptografados com Fernet, tarefas em thread única e agenda persistida. React/TypeScript com build estático servido pelo backend na mesma origem. Execução Windows via PyInstaller e instalador Inno Setup; Docker Linux com volume persistente. Interface em navegador padrão reduz tamanho e dispensa Electron. Agendador requer processo ativo; servidor executa continuamente. Migrações de esquema versionadas. Sem dependência de serviços do desenvolvedor.

## Integrações e limites da primeira versão
- PDF LinkedIn: leitura de texto e sugestões de fatos com evidência; sem acesso automatizado à conta LinkedIn.
- IA: protocolo Chat Completions, incluindo Ollama via endpoint compatível. Outros protocolos nativos são extensões futuras, não são anunciados como disponíveis.
- Vagas: manual, páginas públicas JobPosting e feeds RSS/JSON configurados. Não há promessa de varredura universal.
- E-mail: SMTP TLS para candidatura; .eml para sugestão de acompanhamento. OAuth Gmail/Outlook e leitura periódica de caixa postal são pendências explícitas.
- LinkedIn/Gupy/outros ATS: envio assistido com link e documento; nenhum envio automático por navegador será anunciado como pronto sem validação real do conector. API Gupy exige credenciais administrativas de empresa; não equivale à conta do candidato.

## Critérios de aceite
Perfil de desenvolvimento não aprovado para financeiro apenas por nota alta; perfil não confirmado não envia; modelo indisponível gera pendência; deduplicação persiste; falha SMTP incerta não repete; sem aprovação no modo revisão não envia; pausa respeitada; alteração de perfil invalida análise e aprovação; segredo não aparece em respostas/logs; arquivos e APIs exigem sessão; instalação nova não contém exemplos misturados a métricas reais. Pipeline de build Windows deve gerar executável e instalador, mas somente artefato realmente compilado e testado pode ser anunciado como entrega Windows.
