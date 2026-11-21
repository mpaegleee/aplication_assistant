# Contribuir

O projeto usa licença MIT e recebe melhorias para ajudar pessoas a buscar emprego. O foco desta versão é Brasil, Windows e Linux x64.

1. Leia README e o guia 0.4.0; configure uma instalação de desenvolvimento separada da sua conta pessoal.
2. Instale dependências, Chromium e frontend. Rode os testes documentados no README.
3. Faça uma mudança pequena e explique o comportamento antes/depois e como verificou.
4. Abra um pull request. Para conectores, inclua fixtures com todos os passos, campos desconhecidos, perfil incompleto, envio incerto e comprovante realista.

Não use candidaturas reais como testes automáticos. Testes de navegador precisam de páginas controladas e dados fictícios; os testes de integração existentes interceptam as requisições. Ativar `RUN_BROWSER_TESTS=1` não deve enviar dados a um portal real.

Não inclua credenciais, cookies, CPF, currículo pessoal, pasta de dados ou `.env`. Preserve o sandbox, autenticação, limites, evidências, proteção de áreas profissionais e bloqueio de repetição após resultado incerto. Nenhum conector deve declarar sucesso apenas porque clicou em um botão.

Novos campos de perfil devem ter fonte e confirmação; respostas ausentes ficam como desconhecidas. Um modelo de IA não pode transformar requisitos da vaga em experiências do candidato.

Scripts de empacotamento ficam em `packaging/`. Binários grandes devem ir a GitHub Releases; não devem ser commitados no repositório. Windows exige teste nativo do instalador; Linux exige teste do pacote extraído. Mudanças em portais precisam de validação do layout real antes de sair da condição experimental.
