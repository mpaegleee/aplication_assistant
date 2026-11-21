# Guia do usuário — Application Assistant

Para fila manual, busca em publicações, automação e instaladores Windows/Linux, consulte **ATUALIZACAO-0.4.0.md**. Os guias 0.2 e 0.3 descrevem versões anteriores; as capacidades novas e limitações atuais estão no guia 0.4.

## Para que serve
Organizar sua busca de emprego no Brasil, comparar vagas com seu perfil, preparar currículos e acompanhar candidaturas. Uma pessoa por instalação. O programa é gratuito; serviços de IA escolhidos por você podem cobrar pelo uso.

## Primeiro acesso no Windows
No pacote portátil de teste, extraia o ZIP inteiro e abra **Iniciar.cmd**. Não execute de dentro do ZIP. A pasta contém o runtime: mantenha todos os arquivos juntos. Aguarde o navegador abrir em **http://127.0.0.1:8765**. Crie uma senha com pelo menos 12 caracteres. Mantenha a janela do programa aberta; Ctrl+C encerra. Fechar apenas a aba não encerra o programa. Para voltar, abra o endereço local.

Se recebeu o código para desenvolvimento em vez do pacote portátil, instale Python 3.12 x64 e Node.js 24 LTS; execute **Preparar-e-iniciar.cmd**. Isso prepara as dependências e a interface. Não é o fluxo final do instalador público.

A primeira versão inicia **pausada**, em **modo de aprovação**. Não há candidatura nem e-mail enviado só por abrir a aplicação.

## Configurar a IA
1. Abra Configurações → Inteligência artificial.
2. Em **Onde você usa a IA?**, selecione o serviço onde criou sua chave: DeepSeek, OpenAI, OpenRouter, Groq, Ollama ou LM Studio. O endereço é preenchido automaticamente.
3. Cole a chave desse serviço. Se você usa um modelo DeepSeek pelo OpenRouter, selecione **OpenRouter** e use a chave OpenRouter.
4. Clique **Carregar modelos disponíveis** e escolha na lista. Os identificadores são retornados pelo serviço, não nomes adivinhados ou fixados no programa. Em catálogos grandes, use o campo de busca.
5. Autorize o uso do perfil com esse serviço e clique **Salvar e testar conexão**. Só a lista não garante compatibilidade; o teste verifica uma resposta JSON.
6. Ajuste o limite diário conforme necessário. O teste e tentativas de compatibilidade contam nesse limite. A listagem de modelos não conta no limite de análises e não envia seu perfil.

**Ollama e LM Studio são programas locais:** precisam estar abertos, com um modelo instalado/carregado e seu servidor habilitado. Usar uma chave de um serviço online não instala esse modelo no Ollama. Se a conexão local falhar, abra o programa correspondente ou escolha o serviço online onde criou a chave.

A lista não baixa modelos e não escolhe um modelo pago automaticamente. Modelos locais podem exigir memória e processamento significativos, conforme a escolha. O funcionamento e a qualidade precisam ser avaliados no seu equipamento.

Com provedor externo, perfil e descrição da vaga saem do computador, mesmo com aplicativo local. A chave não é enviada no conteúdo da análise nem retornada pela API de configurações. Campo vazio mantém a chave anterior somente se o endereço continuar o mesmo; ao mudar o endereço, informe a chave correspondente. Há uma ação própria para remover chave salva.

**Configuração avançada:** selecione Outro serviço compatível para informar uma base diferente ou outra porta. Use Informar modelo manualmente apenas se o serviço não listar modelos ou se tiver confirmado o identificador. O protocolo precisa ser compatível com Chat Completions. A aplicação adapta os parâmetros de tokens/formato quando o provedor indica incompatibilidade, mas continua exigindo JSON válido.

**Mensagens de erro:** chave ausente/inválida (401), acesso recusado (403), saldo insuficiente informado pelo provedor (402), modelo/endereço não encontrado (404), limitação/cota (429), indisponibilidade do serviço (5xx), tempo esgotado ou serviço local fechado. Erros não exibem sua chave nem repetem o conteúdo privado retornado pelo provedor.

## Importar o PDF do LinkedIn
No LinkedIn, exporte seu perfil como PDF usando a opção disponível no seu perfil. Importe o arquivo em Meu perfil. Ele deve conter texto selecionável, ter até 10 MB e até 40 páginas. PDFs de imagens precisam de OCR em outra ferramenta; PDFs protegidos não são aceitos.

Clique **Extrair perfil com IA**. Confira nome, contato e cada fato extraído. A extração aceita apenas trechos literais do documento; correções editadas viram fatos informados por você. Você também pode cadastrar fatos manualmente. Não inclua dados de terceiros ou informação que não queira compartilhar com o provedor escolhido.

Defina cargos, áreas desejadas e excluídas, modalidades, contratos, localidades e salário mínimo, se quiser usar esses filtros. Confirme a veracidade e salve. Toda edição pede nova confirmação. A área da profissão não é o setor da empresa.

## Adicionar e analisar vagas
Em Oportunidades, adicione título, empresa, descrição completa e preferências da vaga. Confirme a área com base nas atividades. Informações ausentes não são tratadas como compatibilidade garantida.

Abra a vaga e clique **Analisar aderência**. Os filtros obrigatórios são aplicados antes da IA. Uma área excluída é bloqueada mesmo com limite baixo de aderência. A nota usa função (30%), competências essenciais (30%), senioridade (20%), desejáveis (10%) e preferências (10%). Uma nota não representa chance de contratação; a confiança também é estimada pelo modelo e precisa de avaliação no teste.

Confira evidências e lacunas. A IA pode errar; utilize aprovação no período inicial. Mudanças no perfil, vaga ou critérios invalidam a análise anterior. Baixe o currículo para conferir: ele seleciona fatos do perfil e não cria experiências.

## Fontes e links
Autorize domínios exatos em Configurações → Fontes. Adicione feeds RSS ou JSON conhecidos; páginas individuais precisam ter dados estruturados JobPosting. A autorização de um domínio não autoriza subdomínios nem redirecionamentos para outros sites. Redes privadas e HTTP são bloqueados para coleta de vagas.

Por padrão, itens importados exigem revisão da área. Em Rotina automática, a classificação por regras de cargo pode ser habilitada; casos ambíguos continuam pendentes. RSS pode não trazer empresa, modalidade ou descrição completa; complete esses dados. Use a importação manual quando o site não expuser formato suportado.

**A busca no navegador em LinkedIn/Indeed e páginas Gupy é experimental; veja o guia 0.4.** Prepare a candidatura, abra o link, finalize no portal e registre o envio. O navegador interno permite login manual e mantém a sessão local criptografada; os formulários desses portais ainda exigem interação manual. O LinkedIn restringe automação; APIs de candidatura da Gupy usam acessos de empresas, não uma conta comum de candidato.

## Candidaturas por e-mail
Configure o servidor SMTP com TLS direto (normalmente porta 465) ou STARTTLS (normalmente 587), remetente, usuário e senha de aplicativo. Use as instruções do seu provedor. Alguns provedores exigem OAuth, ainda não disponível. Nunca desative TLS para fazer funcionar.

O anúncio precisa pedir explicitamente o envio de currículo/candidatura e conter o endereço que você cadastrou como destinatário. Um endereço de contato solto não libera envio. O e-mail gerado é simples, cita cargo e empresa e anexa o PDF factual. Modelos personalizados de assunto/corpo ainda não estão disponíveis. Assuntos literais entre aspas ou em linha Assunto: podem ser preservados automaticamente. Instruções ambíguas, carta de apresentação, pretensão salarial ou portfólio seguem para finalização assistida. Instruções de não enviar e anúncios encerrados também bloqueiam SMTP.

Em modo de aprovação, aprove a candidatura e retome a rotina antes de enviar. Em automático, candidaturas elegíveis por e-mail são processadas sem aprovação individual. Os critérios, limites e configuração de envio continuam obrigatórios. Para os demais ATS, a finalização continua assistida; InHire possui o fluxo experimental descrito no guia 0.3.0.

"Aceita pelo SMTP" comprova apenas que o servidor aceitou a mensagem; não comprova entrega, leitura ou candidatura no ATS. Resultado incerto bloqueia reenvio automático. Confira manualmente o ocorrido e atualize o histórico.

## Agenda e limites
Escolha dias, horário e fuso (padrão America/Sao_Paulo). Habilite a agenda e retire a pausa. É necessário internet e computador ligado, sem suspensão, com processo aberto. Não há execução retroativa após desligamento. Pausar impede iniciar novos envios; uma operação em curso pode terminar.

Os limites contam tentativas SMTP e chamadas de IA, inclusive falhas. Só há uma execução por vez. Para rodar sem o computador pessoal, use depois a instalação em servidor próprio.

## Acompanhamento
Abra cada candidatura para registrar envio manual, recebimento, seleção, entrevista, proposta ou encerramento, com uma nota. Em Retornos, importe um `.eml` exportado do seu e-mail. A ferramenta sugere vínculo por referências da conversa ou empresa/cargo, e etapa por palavras do conteúdo. Você confirma ambos. Associação ambígua não atualiza automaticamente.

Há consulta periódica IMAP opcional quando o provedor aceita senha de aplicativo, conforme o guia 0.2.0. Não há resposta automática a recrutadores, aceite de convite nem agendamento de entrevista. Não receber resposta não equivale a rejeição.

## Dados, backup e recuperação
Windows: `%LOCALAPPDATA%\Application Assistant`. Linux: `~/.application-assistant`; Docker: volume `/data`. O diretório contém banco SQLite, chave `vault.key` e arquivos de bloqueio. Conteúdos profissionais e credenciais são criptografados; quem acessa banco e chave pode descriptografá-los. Proteja sua conta do sistema e o disco.

Encerre o programa antes de copiar a pasta inteira para backup. Sem a chave, o banco não pode ser recuperado. A exportação JSON na interface contém dados pessoais em texto claro, sem credenciais; proteja o arquivo. Ela não substitui backup e ainda não tem importação de restauração pela interface. Para restaurar backup completo, com a aplicação fechada, restaure o diretório inteiro na mesma localização.

Se esquecer a senha, o mantenedor pode usar a ferramenta local `backend/reset_password.py` com acesso à pasta de dados. Não existe recuperação remota ou envio de senha. O pacote portátil oferece `Redefinir-senha.cmd`; use somente com o aplicativo encerrado.

A desinstalação preserva a pasta de dados. Para apagar tudo, encerre o programa, faça a exportação/backup desejado e exclua essa pasta. Remova também cópias exportadas ou backups que não queira manter. Revogue credenciais junto aos provedores quando necessário.

## Problemas comuns
- Porta 8765 em uso: veja se o aplicativo já está aberto. Não execute duas cópias com o mesmo diretório de dados.
- PDF sem texto: exporte novamente pelo LinkedIn ou use um PDF com texto.
- IA falha: confirme serviço, endereço com `/v1`, identificador, chave e suporte a JSON. Aumentar o limite não corrige resposta sem evidência.
- Vaga bloqueada: revise área e preferências; não altere dados para aparentar qualificações inexistentes.
- SMTP falha: confira requisitos de autenticação do provedor. O resultado pode ser incerto; não tente reenviar automaticamente.
- Windows avisa sobre programa: este pacote de teste ainda não tem assinatura digital. Confirme a origem e o hash com o mantenedor; não desative a proteção do Windows.
