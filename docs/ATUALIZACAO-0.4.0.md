# Versão 0.4.0 — fila central, modo manual e automação

## Primeiro uso e atualização

Windows: feche a versão anterior, faça backup de `%LOCALAPPDATA%\Application Assistant` e execute o instalador `.exe`. Os arquivos do programa ficam em `%LOCALAPPDATA%\Programs\Application Assistant`; os dados continuam separados. O instalador não contém contas ou chaves. O binário ainda não tem assinatura digital nem foi executado em Windows neste ambiente; esta é uma versão para validação, não uma versão estável certificada.

Linux: veja LINUX.md. macOS não é incluído.

A licença passou a MIT por decisão do mantenedor: o código pode ser publicado, estudado, modificado e redistribuído com os avisos da licença. Orientações antigas sobre manter o código fechado são substituídas por esta decisão.

## Manual: tudo começa na aplicação

1. Importe o PDF, confirme o perfil, cargos, preferências e fatos. Configure o provedor de IA e autorize seu uso.
2. Em Rotina automática, escolha **Somente consolidar; eu me candidato** e as fontes de interesse. Aderência e confiança mínimas são critérios separados.
3. Para LinkedIn/Indeed, entre no navegador interno, conclua o login, salve a sessão e libere o controle. Para Gupy, cadastre as páginas de empresas em Configurações → Fontes como páginas de empresas; não há busca global de todas as empresas Gupy.
4. Informe os termos de busca, um por linha; vazio usa até três cargos do perfil. Habilite **Incluir publicações do LinkedIn** para buscar posts além de anúncios. Retire a pausa da rotina.
5. Abra **Vagas consolidadas** e clique **Buscar e consolidar agora**. Esta ação não dispara candidaturas nem SMTP, mesmo se o modo automático estiver escolhido. Também pode agendar a consolidação no modo manual.
6. Filtre por texto, origem/destino e aderência. Leia a descrição completa e as evidências. Posts preservam seu texto, link original, e-mail e assunto literal quando identificados.
7. **Analisar e preparar currículo** usa a IA para avaliar a posição e selecionar/ordenar fatos confirmados. O PDF destaca esses fatos, sem inventar experiências. Uma análise atual pode ser reutilizada pela rotina; o botão de análise explícita solicita nova análise e pode consumir cota.
8. **Candidatar-me pelo navegador** abre o destino integrado: LinkedIn, Gupy, Indeed, InHire, Greenhouse ou Lever. No navegador, assuma o controle e percorra as etapas. Na etapa do currículo, use **Localizar campo de currículo** e **Anexar currículo neste campo**. A aplicação anexa o PDF daquela vaga, sem abrir um diálogo de arquivos do seu computador. Formatos incompatíveis, arquivos de 2 MB ou maiores e mudança de página invalidam o anexo.
9. Conclua o envio no portal. Volte à fila e registre a conclusão manual com uma observação. Abrir a página ou anexar o arquivo não significa candidatura enviada.

Outros sites permanecem acessíveis pelo link de destino. Uma nova plataforma precisa de integração própria para abrir com sessão no navegador interno. Em e-mail, a tela da vaga permite revisão, aprovação e envio pelo SMTP configurado.

**Revisar informações ou análise** reúne anúncios incompletos, área desconhecida, país não comprovado, dados incompatíveis ou análise desatualizada. Não é correto afirmar aderência apenas porque o cargo parece semelhante. Complete os dados e reanalise. Arquivar retira a vaga da fila e da rotina, sem apagar o histórico; restaurar permite nova revisão.

## Automático e com aprovação

- **Automatizar após minha aprovação:** coleta e analisa; aguarda aprovação de cada versão antes do conector enviar.
- **Enviar automaticamente:** aplica os critérios e tenta concluir nos destinos habilitados sem aprovação por vaga.
- Configure dias, horário (por exemplo, segunda a sexta às 09:00, America/Sao_Paulo), percentual, confiança, máximo de vagas, duração e limite diário de tentativas/IA.
- O computador e processo precisam estar ligados e sem suspensão. Não há compensação de horário perdido com o computador desligado. O sistema evita executar duas vezes o mesmo horário e uma segunda rotina simultânea.
- Escolher LinkedIn para busca não autoriza Gupy para envio: são permissões diferentes. Um redirecionamento conhecido é mostrado como transição para outro portal, com sessão separada. Se ainda exige ação manual, fica pendente.

## Formulários experimentais

O envio por SMTP e o formulário direto InHire continuam disponíveis. Para tentar os assistentes de múltiplas etapas em LinkedIn/Gupy/Indeed, habilite **Usar formulários automáticos experimentais**, autorize o destino e prepare respostas exatas no perfil.

O assistente reconhece formulários semânticos, usa dados de contato confirmados e o banco de respostas, anexa um PDF novo, percorre até 15 etapas com botões conhecidos e exige um botão final explícito. Um botão inicial ambíguo não é tratado como autorização para enviar um perfil antigo. Não cria automaticamente novas contas. Experiências detalhadas, certificação, salário anterior, disponibilidade e consentimentos não são adivinhados.

Antes de compartilhar dados nesses formulários, leia a política do portal e salve a pergunta `Autorizar envio de dados para DOMINIO` com resposta `Sim`, usando o domínio efetivo, por exemplo `www.linkedin.com` ou `empresa.gupy.io`. Confirmações obrigatórias exigem também respostas explícitas próprias. Login, código de acesso, verificação, perguntas desconhecidas e layouts diferentes geram pendência.

Há testes de Chromium com formulários controlados; **não há validação de candidaturas reais nesses três portais**. As imagens de referência ainda não mostram todas as etapas após login na Gupy nem o recibo final do LinkedIn. Um conector experimental não garante funcionamento em qualquer empresa.

Só se registra recebimento automático com uma nova confirmação explícita do portal e comprovante em imagem. O banco registra a tentativa, perfil e PDF antes do clique final. Falha após iniciar o envio vira resultado incerto, bloqueando repetição automática. Limites contam tentativas, inclusive incertas.

## Busca e custo da IA

A coleta no navegador não usa IA para clicar ou navegar. A extração de vagas de posts/páginas e a análise usam o modelo configurado e o limite diário. Extrações idênticas são armazenadas em cache por conteúdo, modelo e provedor. A análise atual é reutilizada quando perfil, vaga e critérios não mudam.

A busca de navegador é limitada aos resultados reconhecidos da primeira página por termo e ao máximo de vagas da execução; não promete encontrar todas as vagas existentes na internet. A rotina divide a coleta LinkedIn entre vagas e posts quando ambos estão habilitados. Publicações com múltiplos cargos sem uma posição específica não são transformadas em uma candidatura automática única.

Mudança de layout, sessão inválida ou bloqueio do portal gera aviso; ausência de resultado reconhecido não comprova que não existam vagas. As fontes desmarcadas não são consultadas. Não há solução de CAPTCHA nem testes seletivos automáticos.

## Retornos e privacidade

O histórico mantém conclusão manual separada de comprovante do portal e aceite SMTP. IMAP opcional continua sugerindo etapas conforme configuração; não responde nem aceita entrevista em nome do usuário.

Cookies, IndexedDB e armazenamento local ficam criptografados; `sessionStorage` não é restaurado. Sessões, chaves e comprovantes não são incluídos no código ou instaladores. Exportação de dados não é backup completo: preserve banco e `vault.key` juntos. O acesso remoto ao navegador exige HTTPS e autenticação da instalação.
