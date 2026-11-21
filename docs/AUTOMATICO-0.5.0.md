# Configuração e uso do automático 0.5.0

## Instalar ou atualizar

No Windows 10/11 x64, feche a aplicação anterior, faça uma cópia da pasta de dados e execute o instalador. Abra Application Assistant pelo menu Iniciar. O programa guarda seus dados em `%LOCALAPPDATA%\Application Assistant` por padrão. Em Linux x64, extraia o pacote e execute `./Iniciar.sh` dentro da pasta extraída. Para criar um atalho, execute `./Instalar.sh`. Consulte [Linux](LINUX.md) para dependências e uso em servidor. Abra http://127.0.0.1:8765 e defina a senha pessoal na primeira execução.

## Preparar uma vez

1. Importe o PDF exportado do LinkedIn. Confira cargo, área, modalidades aceitas, contatos, formação e experiências. Confirme o perfil. O currículo de cada vaga destaca os fatos confirmados.
2. Em Configurações, selecione o provedor e o modelo de IA. Teste a conexão, autorize o uso dos dados necessários e escolha o limite diário.
3. No navegador interno, entre nos portais que vai usar, conclua a autenticação e libere o controle. O navegador da aplicação guarda a sessão localmente. Para anúncios diretos da Gupy, configure a página pública da empresa ou da vaga em Fontes.
4. Cadastre respostas que se repetem. Por exemplo, salve “Pretensão salarial como CLT” e o valor desejado. O sistema pode reutilizar essa resposta para “Qual sua pretensão salarial CLT?”. Última remuneração, pretensão e disponibilidade são respostas distintas. Para cada domínio autorizado a receber seus dados, leia as condições e registre “Autorizar envio de dados para DOMINIO” com a resposta “Sim”.
   Se preferir autorizar de uma vez, use **Autorizar o compartilhamento com empresas nos portais de destino habilitados**. Uma resposta “Não” para um domínio prevalece. Perguntas de consentimento presentes no formulário continuam exigindo respostas próprias.
5. Em **Rotina automática**, escolha **Enviar automaticamente**. Escolha onde buscar e onde enviar, habilite os formulários experimentais para LinkedIn, Gupy e Indeed e configure termos e publicações. Para atingir uma vaga descoberta no LinkedIn e finalizada na Gupy, habilite a descoberta no LinkedIn e o destino Gupy. Se o destino só puder ser identificado após abrir o anúncio no navegador, o destino LinkedIn também precisa estar habilitado.
6. Ajuste aderência, confiança, tentativas por dia e duração. Para vagas por e-mail, configure SMTP com TLS. Para acompanhar retornos, configure IMAP. Habilite a agenda, selecione dias, horário e fuso e retire a pausa. Habilite a classificação por cargo para processar anúncios sem área revisada. Para Scrum Master, Agile Master e PMO, selecione a área **Projetos e Agilidade** no perfil.

## Durante a rotina

Com o processo aberto, as vagas aderentes entram na fila. A rotina prioriza vagas ainda não processadas e depois as verificadas há mais tempo. Se o computador acordar depois da hora programada, a agenda ainda pode executar naquele dia habilitado. Dias anteriores ficam fora da recuperação. Ao habilitar a agenda depois do horário, a execução do dia pode começar imediatamente.

Um link de candidatura identificado no anúncio do LinkedIn ou Indeed pode encaminhar para uma vaga específica da Gupy ou InHire. O aplicativo revalida permissões, critérios e duplicidade e usa a sessão do destino. Na página pública da Gupy, o conector reconhece o link de inscrição da própria vaga, inclusive quando o botão aparece várias vezes. O envio exige respostas conhecidas, currículo válido e confirmação do portal. Nos anúncios por e-mail, a aceitação pelo servidor SMTP registra o envio.

## Interpretar o resultado

No histórico da execução, confira encontradas, aderentes, enviadas e pendentes. Uma vaga com sessão expirada, autenticação adicional, cadastro novo, pergunta desconhecida ou formulário incompatível pode ficar pendente. A fila continua com as demais enquanto houver tempo e cota. Após corrigir a pendência, a vaga volta a ser considerada nas próximas rotinas. Se o envio já começou e o comprovante não apareceu, confira o portal antes de registrar o resultado manualmente. O sistema bloqueia o reenvio automático.

## Alcance da validação

O link público da Gupy fornecido para o teste exibe o cargo Scrum Master e direciona ao caminho de inscrição do mesmo identificador 12673201. As etapas autenticadas e os recibos reais de empregadores seguem sem validação ponta a ponta. Os testes de navegador utilizam formulários controlados. Contas novas, MFA, CAPTCHA e perguntas sem informação confirmada ainda podem exigir o titular. Para o fluxo manual, consulte [fila e navegação](ATUALIZACAO-0.4.0.md).
