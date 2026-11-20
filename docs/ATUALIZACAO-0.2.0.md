# Versão 0.2.0 — motor de rotina automática

## O que esta versão automatiza
Coleta em fontes públicas configuradas → consolidação → filtros obrigatórios → classificação conservadora por cargo (se habilitada) → análise por IA ou cache → currículo factual → envio SMTP → registro do resultado. Agenda local de segunda a sexta às 09:00 é configurável. Não é necessário manter o navegador aberto, mas o processo iniciado por Iniciar.cmd e o computador precisam continuar ligados, conectados e sem suspensão.

**O cadastro e o envio por navegador em LinkedIn, Gupy e Indeed ainda NÃO estão implementados/validados.** Marcar essas plataformas registra uma preferência, não habilita um conector inexistente. O painel mostra essa limitação e as pendências. Esta versão não entrega ainda o ciclo de inscrições automáticas nos três portais.

## Atualizar a instalação existente
1. Encerre o programa na janela do Iniciar.cmd (Ctrl+C), não apenas a aba.
2. Extraia o conteúdo de **ApplicationAssistant-Atualizacao-0.2.0.zip** diretamente em `D:\Pessoal\ApplicationAssistant-Windows-Local`, substituindo os arquivos, sem criar uma subpasta adicional.
3. Abra Iniciar.cmd e recarregue a interface.

O pacote de atualização não contém nem modifica banco, chave de dados ou credenciais. O runtime e suas dependências não mudaram. Os dados continuam em `%LOCALAPPDATA%\Application Assistant`. Análises antigas podem precisar de nova avaliação pela nova política e novos campos. A escolha prévia entre aprovação e automático é preservada; nenhuma integração de e-mail nova é ativada silenciosamente.

## Configuração inicial para o modo automático
- Confirme perfil, fatos e objetivos. Configure e teste a IA.
- Em **Rotina automática**, escolha o modo automático, aderência mínima (por exemplo 85%), fontes de busca e destinos permitidos.
- Se desejar processar vagas sem confirmar cada área individualmente, habilite a classificação por regras de cargo. Cargos ambíguos, país de contratação desconhecido e requisitos obrigatórios não informados continuam pendentes. Área excluída nunca é liberada por nota.
- Em Configurações → Fontes, cadastre um feed RSS/JSON ou página pública JobPosting e autorize os domínios. Há adaptadores de leitura para quadros públicos Greenhouse/Lever: escolha o tipo e informe o identificador do quadro; o endereço da API é montado automaticamente. Nome da fonte deve ser o nome da empresa para esses quadros. Coleta não equivale a autorização de envio por API.
- Em Configurações → E-mail, configure SMTP TLS e habilite envio. Autorize o destino e-mail também em Rotina automática.
- Em Agenda e execuções, marque dias, horário e fuso, habilite a agenda e retire a pausa.

O automático atende somente canais com envio implementado. Fontes e destinos são independentes: autorizar Gupy como destino não faz buscas independentes na Gupy. Destino não autorizado, conector ausente, limite, baixa confiança ou instruções ambíguas geram pendências sem travar as demais vagas.

## E-mail com assunto solicitado
Destinatário pode ser extraído quando houver um único endereço e uma instrução explícita de envio de currículo. Um assunto literal entre aspas ou numa linha `Assunto: ...` é preservado. Exemplo:

```
Envie seu currículo para ENDERECO-QUE-VOCE-CONTROLA.
Assunto: "Desenvolvedor Sênior"
```

Não use o exemplo como vaga real. Substitua por uma conta de teste sua no piloto. Múltiplos endereços exigem revisão da associação. Templates com nome/CPF e instruções para documentos extras não são inventados: ficam assistidos. Resultado incerto durante SMTP bloqueia reenvio. Aceite SMTP não prova entrega, leitura ou cadastro em ATS.

## Currículo e dados reutilizáveis
Meu perfil permite baixar um currículo padrão sem nova chamada de IA. A opção Melhorar redação com IA produz um rascunho comparável aos fatos originais, não altera o perfil salvo automaticamente. A pessoa revisa e confirma uma vez; os currículos por vaga selecionam os fatos aprovados em ordem de relevância. A ferramenta não concede qualificações nem garante aprovação por RH.

Respostas reutilizáveis podem ser cadastradas no perfil para futuros conectores de formulários. Esse banco não entra nos prompts de comparação ou melhoria de redação. Ele não significa que um formulário Gupy já será preenchido nesta versão.

## Acompanhamento automático
Opcionalmente configure IMAP TLS com senha de aplicativo e habilite consultas periódicas. OAuth ainda não está implementado; provedores que exigem OAuth não funcionarão apenas com usuário/senha. A consulta usa leitura somente, não marca mensagens como lidas e não responde recrutadores.

A primeira consulta considera no máximo o limite configurado entre as mensagens mais recentes dos últimos 15 dias. Depois há cursor por conta/pasta e deduplicação, para avançar nos novos e-mails em lotes sem repetir sugestões. Mensagens acima de 2 MB são ignoradas. Aumente o limite ou use importação .eml para mensagens fora desse recorte.

Atualização automática de etapa é opcional. Exige uma única candidatura, referência exata à conversa e remetente igual ao destinatário original, além de etapa reconhecida. Os demais retornos ficam como sugestões. Não há regressão automática de etapa nem aceitação de entrevistas, resolução de testes ou agendamento de compromissos. Pausar candidaturas não desabilita a consulta IMAP; para isso, desative sua opção própria.

## Painel e histórico
O resumo de execução informa encontradas, novas, duplicadas, avaliadas, aderentes, aceitas por SMTP, pendências e fontes consultadas. Candidatura confirmada em portal não é inferida de formulário preenchido. Registros manuais continuam identificados como informados pelo usuário.

Histórico de 15 dias considera candidaturas com data de envio registrada e mostra retorno e etapa atual, incluindo teste técnico e entrevista com gestor. Datas ausentes em registros antigos não são inventadas. A interface atualiza enquanto visível, mesmo sem uma busca em andamento.

A análise de vagas idênticas é reaproveitada; perfil, descrição e critérios relevantes invalidam o cache. O botão de análise manual força nova chamada, respeitando o limite. Fontes desmarcadas não são consultadas. A duração máxima limita o início de novas etapas; uma operação de rede em andamento pode terminar depois do prazo. Execuções não são garantidas em exatamente uma hora.

## Validação desta entrega
65 testes passaram em Python 3.12 e 3.14. Em cenário controlado: 12 vagas encontradas → 7 aderentes → 7 mensagens MIME com PDF e assunto literal. Ao executar de novo, não houve novos envios nem novas chamadas de análise para as descrições iguais. SMTP e IMAP foram simulados, sem contas pessoais ou mensagens a empresas reais. O teste não demonstra estatisticamente a precisão do modelo em vagas reais.

Também foram testados seleção de fontes/destinos, conector ausente, deduplicação por destino e identificadores conhecidos, classificação de profissão incompatível antes da IA, histórico de etapas, não regressão por e-mail antigo, sigilo de credenciais, leitura IMAP com PEEK e deduplicação, redação apenas como rascunho e rejeição de métricas inventadas.

Build TypeScript/Vite aprovado. Execução nativa e inspeção visual desta versão em Windows ainda precisam de confirmação. A próxima etapa indispensável para o objetivo completo é o conector autenticado de formulários, começando pela validação de um fluxo real da Gupy, com conta e sessão controladas pelo usuário.

## APIs públicas de leitura utilizadas
- Greenhouse Job Board: https://docs.greenhouse.io/job-board
- Lever Postings: https://github.com/lever/postings-api
