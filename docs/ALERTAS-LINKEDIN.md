# Coleta de alertas do LinkedIn por e-mail

O LinkedIn pode enviar alertas diários ou semanais das pesquisas salvas. A aplicação lê esses alertas durante a coleta manual ou agendada e coloca as vagas na fila.

1. Configure os [alertas no LinkedIn](https://www.linkedin.com/help/linkedin/answer/a1420165) com os termos e locais de interesse. Habilite a opção e-mail.
2. Em **Configuração guiada → Fontes e rotina**, habilite LinkedIn e selecione **Importar alertas do LinkedIn por e-mail**. Salve as preferências.
3. Em **Conectar contas → Configurar e-mail de coleta**, informe o servidor TLS, usuário, senha de aplicativo e pasta IMAP que recebe os alertas. A opção de consultar respostas é independente. Outlook.com exige autenticação OAuth e precisa de um conector próprio para este fluxo. Use uma conta compatível com o método oferecido.
4. Rode **Teste de coleta** ou use **Buscar e consolidar agora**. Em **Vagas consolidadas**, clique em **Ver alertas importados**.

A aplicação lê a caixa em modo somente leitura e busca o remetente de alertas suportado. Deduplica pelo identificador da vaga e preserva o anúncio completo quando ele já existe. O período de 7, 15 ou 30 dias limita a busca dos alertas recebidos. A data do e-mail não vira data de publicação da vaga.

Os e-mails podem trazer só uma prévia. Nesse caso, a vaga aparece com o link oficial e os dados disponíveis. A prévia não serve de base para enviar candidaturas automaticamente. O modo por alertas depende do conteúdo que o LinkedIn publica por e-mail e não inclui as postagens do feed.
