# Linux x64

Distribuições com glibc 2.28 ou superior, ambiente gráfico para abrir a interface local e bibliotecas do Chromium. O pacote é preparado com CPython portátil, dependências Python e Chromium. A validação disponível usa Debian 13 x64; outras distribuições precisam do primeiro teste. Alpine/musl e ARM não são suportados por este artefato.

1. Extraia `ApplicationAssistant-0.6.0-Linux-x64.tar.gz` em uma pasta pessoal.
2. Na pasta extraída, execute `./Iniciar.sh`.
3. Abra `http://127.0.0.1:8765`, crie uma senha e siga o guia da versão 0.6.0.
4. Opcional: `./Instalar.sh` copia para `~/.local/share/ApplicationAssistant` e adiciona um atalho ao menu. Não exige administrador para copiar o aplicativo.

Mantenha o terminal aberto e o computador sem suspensão. Os dados ficam em `~/.application-assistant`, separados da instalação.

## Dependências do navegador

Se a mensagem indicar biblioteca ausente, use o gerenciador de pacotes da sua distribuição. O próprio Playwright incluído pode instalar as dependências oficiais em distribuições compatíveis; isso usa o administrador/sudo e deve ser executado conscientemente:

```sh
./runtime/bin/python3.14 -m playwright install-deps chromium
```

Não é preciso instalar outro Python, Node.js ou Chrome. O sandbox do Chromium permanece habilitado. Se o host bloquear namespaces/sandbox, ajuste o host; não há opção de desativar o sandbox no aplicativo.

## Servidor próprio

Use o Dockerfile e compose do código-fonte. A imagem instala dependências do Chromium e roda sem root. O host/container precisa permitir o sandbox. Para acesso remoto, configure proxy HTTPS, `AA_ALLOWED_HOSTS`, `AA_SECURE_COOKIES=1` e código aleatório de primeiro acesso. Não publique a porta diretamente na internet. O navegador roda no servidor; a imagem é controlada na aplicação por WebSocket.

## Backup e remoção

Encerre o processo antes de copiar `~/.application-assistant`, incluindo banco e `vault.key`. Remover os arquivos da aplicação preserva esses dados. Para remover o atalho, exclua `~/.local/share/applications/application-assistant.desktop`. Remova a pasta de dados separadamente somente quando desejar apagar perfil, histórico e sessões.
