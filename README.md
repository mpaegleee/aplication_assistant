# Application Assistant

Assistente pessoal para candidaturas no Brasil, com importação de currículo PDF, análise de aderência, revisão, documentos e acompanhamento. Uma pessoa por instalação. Prioridade: Windows 10/11 x64; Docker em Linux para servidor próprio.

**Versão 0.3.0 para teste local. Nenhum código ou binário foi publicado.** Navegador Chromium interno com login manual, sessões criptografadas e controle via WebSocket. InHire tem formulário direto experimental validado em testes controlados; SMTP mantém envio automático. Busca autenticada e envio automático em LinkedIn, Gupy e Indeed ainda estão pendentes.

- [Navegador, sessões e atualização 0.3.0](docs/ATUALIZACAO-0.3.0.md)

- [Rotina automática e limites da versão 0.2.0](docs/ATUALIZACAO-0.2.0.md)
- [Guia do usuário](docs/GUIA-DO-USUARIO.md)
- [Atualização 0.1.1: seleção de provedor e modelos](docs/ATUALIZACAO-0.1.1.md)
- [Especificação e regras](docs/ESPECIFICACAO.md)
- [Teste local e roteiro de aceite](docs/TESTE-LOCAL.md)
- [Arquitetura e operação](docs/ARQUITETURA.md)
- [Verificação e limitações](docs/VERIFICACAO.md)

## Executar a partir do projeto

Requer Python 3.12+ e Node.js 24 LTS apenas para preparar o projeto. No Windows, execute `Preparar-e-iniciar.cmd`. Na primeira execução serão baixadas as dependências e compilada a interface. O navegador abrirá em http://127.0.0.1:8765. Nas próximas vezes o script reutiliza a instalação.

Linux:

```sh
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python backend/launcher.py
```

Mantenha o processo aberto. A agenda não roda com computador desligado ou suspenso. Toda instalação começa pausada, sem fontes, sem credenciais e em modo de aprovação.

## Testes e empacotamento

```sh
.venv/bin/pip install -r backend/requirements-dev.txt
PYTHONPATH=backend .venv/bin/pytest -q backend/tests
npm --prefix frontend run build
```

`packaging/build-windows.ps1` gera o executável Windows via PyInstaller. `packaging/installer.iss` gera o instalador com Inno Setup. O workflow Windows também verifica a inicialização do binário antes de disponibilizá-lo como artefato privado; não cria release pública.

`packaging/build_portable.py` prepara um pacote portátil para o primeiro teste Windows, com runtime CPython embutido, dependências Windows e interface já compilada. Não requer Python ou Node na máquina do usuário. O pacote precisa ser validado em Windows antes de distribuição. Bytecode Python não é proteção contra engenharia reversa.

## Servidor próprio (opcional, depois do teste local)

Copie `.env.example` para `.env`, altere o código de configuração e execute `docker compose up --build -d`. A porta é publicada somente no loopback por padrão. Acesso externo exige proxy HTTPS, `AA_ALLOWED_HOSTS` e cookies seguros; veja o guia. Não usar múltiplos workers ou compartilhar o volume entre réplicas.

## Distribuição

Código reservado ao mantenedor. A licença proprietária gratuita e avisos de dependências devem ser revisados antes de distribuir. O repositório de código deve ser privado; downloads e documentação podem ter canal público separado.
