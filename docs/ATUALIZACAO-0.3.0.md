# Versão 0.3.0 — navegador interno e primeiro formulário automático

Esta versão é para teste local. Não foi publicada no GitHub. O pacote foi montado em Linux: ainda precisa ser executado e validado em Windows 10/11 x64.

## Atualizar no Windows

1. Feche a aplicação com Ctrl+C na janela do programa. Fechar a aba não basta.
2. Faça backup da pasta `%LOCALAPPDATA%\Application Assistant`, incluindo `vault.key` e banco SQLite.
3. Extraia **ApplicationAssistant-Atualizacao-0.3.0.zip** diretamente em `D:\Pessoal\ApplicationAssistant-Windows-Local`, substituindo os arquivos. Esta atualização inclui o runtime e o Chromium; a atualização antiga que contém apenas a interface não serve para esta versão.
4. Abra `Iniciar.cmd` e recarregue a página com Ctrl+F5. O rodapé deve mostrar v0.3.0.

Alternativa: extraia o pacote completo em uma nova pasta e abra `Iniciar.cmd`. Os dados continuam na mesma pasta LOCALAPPDATA, independente da pasta do programa. Não execute duas versões simultaneamente.

O Chromium aumenta bastante o tamanho do pacote. O usuário não precisa instalar Python, Node.js, extensão de navegador ou Chrome à parte.

## Login e sessão

Abra **Navegador e sessões**, escolha LinkedIn, Gupy ou Indeed e clique **Abrir portal**. Para InHire, cole o link da vaga. No Gupy também pode colar o link público da empresa, clicar em candidatar-se e entrar por esse caminho.

Clique **Assumir controle**. Clique no campo da página, digite o texto ou senha na caixa protegida abaixo da imagem e clique **Digitar no portal**. Use os botões para rolar, mudar de campo e pressionar Enter. Os campos podem exigir cliques nas opções da própria página. Use uma tela por portal de cada vez.

Conclua o login e eventuais verificações diretamente no portal. Clique **Salvar sessão e liberar controle**. Sair desta tela também libera e salva a sessão. A aplicação guarda cookies, armazenamento local e IndexedDB criptografados no banco; não grava sua senha do portal como credencial própria. Cookies dos provedores de identidade são descartados ao salvar. `sessionStorage` não é restaurado após reiniciar. Alguns logins por Google/LinkedIn podem exigir nova autenticação ou ser recusados pelo provedor no navegador automatizado.

A sessão pode vencer, ser revogada ou exigir nova verificação. Uma sessão salva não comprova que o login continua válido. Não há solução de CAPTCHA nem contorno de bloqueios. **Apagar sessão local** remove os dados deste navegador e banco; revogar a sessão no site é uma ação separada.

O navegador é Chromium isolado, controlado por WebSocket com autenticação da instalação e verificação de origem. O computador precisa estar ligado e sem suspensão. No servidor, o navegador roda no servidor e a imagem aparece na aplicação. Use HTTPS para acesso remoto; não exponha a porta local diretamente na internet. Banco e chave na mesma máquina ainda exigem proteção da conta do sistema e do disco.

## InHire: formulário direto experimental

Foi implementado o fluxo observado no caso Audaces: formulário direto, dados de contato, perfil LinkedIn, pergunta de disponibilidade, currículo PDF e pretensão salarial. Foi testado com Chromium real em formulários controlados. **Ainda não foi validado enviando candidatura ao InHire real.** Mudanças de layout, widgets diferentes, arquivos adicionais e perguntas desconhecidas geram pendência.

1. Confirme seu perfil, incluindo telefone e URL pública do LinkedIn.
2. Cadastre no banco de respostas as perguntas exatamente como aparecem no formulário. Exemplo: `Pretensão salarial como CLT` → `12000`. Não se usa salário mínimo desejado como pretensão e não se deduz disponibilidade ou certificação.
3. Leia a política do portal. Para autorizar compartilhamento com a empresa Audaces, salve a pergunta `Autorizar envio de dados para audaces.inhire.app` e resposta `Sim`. É uma autorização sua por domínio; não é uma interpretação automática da política de privacidade.
4. Habilite **InHire** em Rotina automática → Onde permitir finalizar. Mantenha **Páginas de empresas** selecionado para processar vagas InHire importadas diretamente. Vagas descobertas por outra fonte seguem a seleção da fonte original, mesmo quando o destino é InHire.
5. Importe a vaga, revise área/local/modalidade e analise. Em modo de revisão, aprove a vaga. Retire a pausa.
6. Em Navegador e sessões, use **Preencher sem enviar** para testar. O formulário é aberto numa nova página InHire, o currículo específico é anexado e nenhum clique final é feito. Leia as pendências antes de continuar.
7. **Executar candidatura** inicia novamente o fluxo completo e tenta concluir. A rotina agendada usa o mesmo fluxo, conforme modo, aprovação, aderência e limites. Não deixe o controle manual do InHire ativo enquanto a rotina trabalha.

Antes de enviar, o sistema registra a tentativa, versão do perfil e currículo. Só registra recebimento confirmado se o portal exibir uma nova mensagem explícita de sucesso; uma imagem dessa confirmação fica no comprovante da candidatura. Clique no botão sozinho não é prova. Uma falha após o início do envio vira **Resultado incerto** e não será repetida automaticamente. Confira o portal antes de atualizar o histórico manualmente.

Perguntas desconhecidas não são respondidas por adivinhação, mesmo no modo automático. Novas respostas alteram o perfil e exigem nova análise/aprovação da vaga. A análise pode consumir IA; a interação deste formulário e a exibição do navegador não chamam IA.

## Cobertura real

| Plataforma | Login no navegador interno | Busca automática autenticada | Preenchimento/envio |
|---|---|---|---|
| LinkedIn | Manual, sessão local | Pendente | Manual; Easy Apply ainda não implementado |
| Gupy | Manual, sessão local | Pendente | Manual; cadastro e etapas ainda não implementados |
| Indeed | Manual, sessão local | Pendente | Manual; conector ainda não implementado |
| InHire | Não exigido no caso documentado | Sem busca própria | Formulário direto experimental |
| E-mail | Configuração SMTP/IMAP | Conforme fontes selecionadas | SMTP e acompanhamento existentes |

Links externos entre plataformas devem ser abertos no portal correspondente; cookies de um portal não são copiados para outro. As URLs dos três casos recebidos continuam registradas em `docs/casos`.

Para fechar os conectores restantes, é necessário observar as etapas após login e seus recibos reais. As imagens de Gupy param no login e as do LinkedIn Easy Apply ainda não mostram a etapa final nem o link da vaga. Esta versão não deve ser anunciada como automação completa desses portais.

## Desenvolvimento e Linux

Depois de instalar `backend/requirements.lock`, execute `python -m playwright install --with-deps --no-shell chromium` (no Windows, sem `--with-deps`). A mesma versão de Playwright deve instalar o Chromium distribuído. Para testes reais contra formulários de teste: `RUN_BROWSER_TESTS=1 PYTHONPATH=backend .venv/bin/pytest -q backend/tests`.

O sandbox do Chromium permanece habilitado. Linux/container precisa permitir o sandbox e ter as dependências de sistema. Se o host impedir namespaces/sandbox, o navegador retorna uma mensagem de configuração: não há opção de desativar a proteção na aplicação. A imagem Docker foi ajustada para instalar o navegador, mas este lançamento não foi validado em Docker com Chromium.
