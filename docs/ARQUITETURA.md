# Arquitetura e operação

## Componentes
- React 19/TypeScript/Vite: interface estática sem CDNs, analytics ou armazenamento de segredos no navegador.
- FastAPI: validação Pydantic, sessão de 12 horas em cookie HttpOnly/SameSite Strict, origem e cabeçalho exigidos em mutações, hosts explícitos e CSP.
- SQLite WAL: objetos criptografados Fernet; hash scrypt para senha; sessões guardadas apenas por hash. Migração inicial via `user_version=1`; recusa esquema mais novo.
- Uma thread de agenda e uma de execução, um processo por diretório de dados. FileLock impede múltiplos processos; RLock serializa análise/edição/envio. Contadores reservados em transações `BEGIN IMMEDIATE`.
- Chamadas IA: HTTP com timeout e sem redirecionamentos, payload somente com dados necessários. HTTP apenas para endpoints locais explicitamente suportados; HTTPS para externos.
- Coleta pública: lista de domínios exatos, HTTPS, limite de tamanho, IP público validado e fixado na conexão TLS, verificação por salto de redirecionamento, sem cookies de contas.
- Currículo: ReportLab seleciona trechos confirmados por IDs. A IA não escreve qualificações no documento.
- SMTP: TLS validado; estado persistido antes do envio; erro incerto não é reprocessado. Quit falho após DATA aceito não invalida o aceite.

## Reinício e parada
Estados `sending` no reinício passam a `uncertain`; execuções interrompidas passam a `failed`. A agenda não recupera horários perdidos. Aprovações e análises têm fingerprint do perfil, vaga e política; mudanças relevantes exigem nova análise. Envio mantém PDF e perfil do momento.

## Configuração de ambiente
- `AA_DATA_DIR`: diretório de dados; padrão por usuário.
- `AA_PORT`: porta; padrão 8765.
- `AA_NO_BROWSER=1`: não abrir navegador automaticamente.
- `AA_SERVER=1`: bind 0.0.0.0. Sem essa opção, somente 127.0.0.1.
- `AA_SETUP_TOKEN`: código secreto para primeiro acesso; obrigatório em servidor novo.
- `AA_ALLOWED_HOSTS`: nomes de host separados por vírgula, sem esquema/porta. Padrão localhost/127.0.0.1; `testserver` é acrescentado apenas em testes.
- `AA_SECURE_COOKIES=1`: obrigatório em servidor HTTPS.
- `AA_STATIC_DIR`: diretório do build da interface quando usado via factory; launcher usa o build junto ao programa.

## Servidor próprio
Não é necessário para o primeiro teste Windows. Posteriormente: `docker compose up --build -d`, com `.env` próprio e volume persistente. O compose publica 127.0.0.1:8765. Para acesso pela rede, use reverse proxy HTTPS, configure o domínio em AA_ALLOWED_HOSTS e cookies seguros. Não exponha HTTP sem TLS na internet. Não execute múltiplos workers nem réplicas usando o mesmo banco. `AA_SETUP_TOKEN` deve permanecer privado e pode ser removido depois de criar a senha. Considere backup do volume com container parado.

## Evolução
Conectores devem declarar capacidades e só habilitar envio automático após testes de aceitação específicos. Pendências: OAuth de e-mail, sincronização periódica, adaptadores ATS por navegador, respostas estruturadas de formulários, template de currículo por seção, notificações, atualização automática, assinatura digital Windows e instalador validado em máquinas limpas. Não resolver testes seletivos, CAPTCHA ou aceitar termos automaticamente.

## Fontes da decisão de integração
- https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2
- https://www.linkedin.com/help/linkedin/answer/a1341543
- https://developers.gupy.io/v2.0/docs/autentica%C3%A7%C3%A3o-recrutamento-sele%C3%A7%C3%A3o
- https://developers.gupy.io/docs/fluxo-de-capta%C3%A7%C3%A3o-de-pessoas-candidatas-em-plataformas-externas-candidatura-rapida
