# Application Assistant

Assistente gratuito e de código aberto para organizar a busca por emprego no Brasil. Uma pessoa por instalação, com dados locais e IA escolhida pelo usuário. **Windows e Linux x64; macOS não faz parte desta versão.**

## Dois caminhos para a candidatura

**Manual:** a aplicação consolida vagas e publicações em uma fila. Consulte a descrição, filtre a aderência, analise as evidências, gere o currículo específico e abra o destino da candidatura. Nos portais integrados, a página abre no navegador da própria aplicação, com login, sessão e anexo do currículo. O usuário conclui o envio e registra a confirmação.

**Automático:** a rotina agendada busca, consolida, analisa e tenta candidatar nas fontes e destinos habilitados. Há modo de aprovação prévia, limites diários, critérios por área/modalidade/localidade, percentual mínimo e pausa. A ação **Buscar e consolidar agora** nunca envia, mesmo no modo automático.

O currículo destaca e ordena fatos confirmados do perfil; a IA não cria certificações ou experiências para aumentar a aderência.

## Versão 0.6.1

A etapa Conectar contas informa quais portais exigem login. A busca avisa quando uma fonte está bloqueada e continua nas fontes disponíveis.

A configuração guiada reúne IA, perfil, fontes, sessões e coleta de teste. O PDF importado fica disponível para download e pode preencher contatos em branco. A coleta manual funciona com a agenda pausada. A atualização preserva os dados da versão anterior.

A rotina recupera o horário perdido no mesmo dia, alterna vagas já processadas e acompanha links de candidatura para Gupy e InHire. A área Projetos e Agilidade reconhece cargos como Scrum Master e PMO. É possível autorizar de uma vez o compartilhamento com empresas dos portais selecionados.

- Fila **Vagas consolidadas**, filtros, descrição de publicações, currículo por posição e histórico.
- Fontes RSS/JSON/JobPosting, Greenhouse e Lever; busca experimental no navegador em LinkedIn (vagas e publicações), Indeed e páginas Gupy configuradas pelo usuário.
- Navegador Chromium próprio, sessões criptografadas, transição entre portais conhecidos e anexo manual sem extensão do navegador pessoal.
- SMTP TLS; InHire direto; formulários de múltiplas etapas experimentais em LinkedIn, Gupy e Indeed. Os formulários experimentais começam **desabilitados** e só atuam em controles reconhecidos, com respostas exatas e currículo novo.
- Sessão vencida, CAPTCHA, criação de conta, botão ambíguo e perguntas desconhecidas geram pendência. Não existe automação universal de qualquer site. Um resultado incerto nunca é repetido automaticamente.
- Acompanhamento por histórico e IMAP opcional.

**Validação.** Os workflows compilam os pacotes em Windows e Linux e verificam a atualização da versão anterior com dados preservados. Os testes de navegador usam formulários controlados. A automação em portais reais continua em validação. O instalador Windows ainda não tem assinatura Authenticode.

## Instalar

Os downloads ficam em [GitHub Releases](https://github.com/mpaegleee/aplication_assistant/releases).

| Sistema | Arquivo | Como usar |
|---|---|---|
| Windows 10/11 x64 | `ApplicationAssistant-Setup-0.6.1-Windows-x64.exe` | Executar o instalador e abrir pelo atalho |
| Linux x64 | `ApplicationAssistant-0.6.1-Linux-x64.tar.gz` | Extrair e executar `./Iniciar.sh`; `./Instalar.sh` cria o atalho |
| Desenvolvimento | `ApplicationAssistant-Codigo-0.6.1.zip` | Código, testes e scripts de build |

Python, driver e Chromium acompanham os pacotes de uso. No Linux, bibliotecas de sistema do Chromium ainda podem ser necessárias. O computador deve permanecer ligado, sem suspensão, com o processo aberto. Para servidor próprio, há instalação Docker.

- [Guia da versão: fila manual, rotina, busca em posts e limitações](docs/ATUALIZACAO-0.6.1.md)
- [Configuração para usuários](docs/GUIA-DO-USUARIO.md)
- [Instalar no Linux](docs/LINUX.md)
- [Verificação e testes](docs/VERIFICACAO.md)
- [Contribuir](CONTRIBUTING.md)
- [Preparar e publicar uma versão](docs/PUBLICACAO.md)

## Desenvolver

Requer Python 3.12+ e Node.js 24 LTS. No Windows, `Preparar-e-iniciar.cmd` prepara as dependências e abre a aplicação. No Linux:

```sh
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r backend/requirements.lock
.venv/bin/python -m playwright install --with-deps --no-shell chromium
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python backend/launcher.py
```

Acesse `http://127.0.0.1:8765`. A instalação inicia pausada, sem contas nem dados de exemplo.

```sh
.venv/bin/pip install -r backend/requirements-dev.txt
RUN_BROWSER_TESTS=1 PYTHONPATH=backend .venv/bin/pytest -q backend/tests
npm --prefix frontend run build
```

## Servidor próprio

Copie `.env.example` para `.env`, defina um código aleatório de configuração e execute `docker compose up --build -d`. O acesso remoto exige proxy HTTPS e ajuste dos hosts e cookies seguros. O host precisa permitir o sandbox do Chromium. Use uma instância e um volume por pessoa; não use múltiplos workers.

## Licença e dados

[MIT](LICENSE.txt): uso, estudo, adaptação e redistribuição permitidos, preservados os avisos. Dependências e Chromium mantêm suas próprias licenças. O aplicativo é gratuito; os provedores de IA podem cobrar.

Credenciais e sessões ficam criptografadas nesta instalação. Perfil e anúncio são enviados ao provedor de IA quando o usuário autoriza; contatos digitados no navegador são enviados ao portal. Proteja o banco e sua chave. Não publique `.env`, contas, cookies, currículos ou a pasta de dados.
