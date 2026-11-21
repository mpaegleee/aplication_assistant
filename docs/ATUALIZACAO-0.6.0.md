# Instalação e atualização — 0.6.0

## Mantenha seus dados

Feche a aplicação antes de atualizar. Use o instalador da nova versão no Windows, ou extraia o novo pacote no Linux e execute `./Instalar.sh` se já usa o atalho. Se preferir não instalar, rode `./Iniciar.sh` a partir da nova pasta extraída.

A atualização troca os arquivos do programa. A aplicação continua usando a mesma pasta de dados do usuário:

| Sistema | Dados | Aplicação instalada |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%\Application Assistant` | `%LOCALAPPDATA%\Programs\Application Assistant` |
| Linux | `~/.application-assistant` | `${XDG_DATA_HOME:-~/.local/share}/ApplicationAssistant` |

Se configurou `AA_DATA_DIR`, continue a apontá-la para a mesma pasta. Preserve também o usuário do sistema que executa o aplicativo. Para copiar ou fazer backup, encerre o processo e copie a pasta de dados inteira, incluindo a chave `vault.key` e o banco SQLite. A chave do banco é necessária para ler a chave de IA, o currículo, as sessões e os registros criptografados. A versão 0.6.0 reutiliza o formato de dados da 0.5.0.

Uma futura distribuição para macOS deverá guardar dados fora do pacote da aplicação, manter um caminho de dados estável para cada usuário e testar a atualização de uma versão anterior antes da publicação.

## Configuração guiada

Abra **Configuração guiada** no menu. Nas instalações novas, ela aparece depois de criar a senha.

1. **Inteligência artificial.** Escolha o provedor e o modelo, informe a chave quando necessária e autorize o uso. Use **Salvar e testar conexão**.
2. **Currículo e perfil.** Importe um PDF com texto selecionável. O nome do arquivo e o download do original ficam visíveis. Contatos identificáveis preenchem campos vazios sem consultar IA. Revise as sugestões e use **Extrair perfil com IA** para propor fatos. Selecione a área, informe os cargos, confirme e salve.
3. **Fontes e rotina.** Habilite onde pesquisar. Cadastre o endereço para feeds e páginas de empresas. LinkedIn e Indeed usam a pesquisa do navegador integrado. Para Gupy, cadastre a página pública da empresa e habilite Gupy na rotina.
4. **Sessões e envio.** Entre nos portais selecionados e libere o controle do navegador. Configure SMTP apenas se quiser enviar candidaturas por e-mail.
5. **Teste de coleta.** Rode uma busca sem envio e veja o total de vagas e as pendências. Configure a agenda quando quiser executar em horários definidos.

A busca manual **Buscar e consolidar agora** funciona mesmo com a agenda pausada. O modo de envio e os critérios de candidatura continuam configuráveis em [Rotina automática](AUTOMATICO-0.5.0.md).

O instalador Windows desta prévia ainda não tem assinatura Authenticode. O Microsoft Edge pode mostrar o aviso de reputação. Os hashes SHA-256 ficam junto dos arquivos no GitHub Releases.

## Datas e versões de currículo

Em **Fontes e rotina**, selecione os últimos 7, 15 ou 30 dias. Vagas antigas ou com inscrições encerradas segundo os dados da fonte ficam fora da análise automática. Se a fonte não expõe uma data verificável, escolha se quer incluir o anúncio. Desmarcar a opção evita chamadas de IA para esses anúncios. Vagas já armazenadas continuam no histórico e podem entrar novamente na janela se a opção mudar. O filtro usa metadados que o portal ou feed disponibiliza.

Em **Meu perfil**, classifique registros como experiência, formação, cursos e certificações, competências e idiomas ou outras qualificações. A extração por IA sugere essas categorias a partir do PDF. Confira o conteúdo e confirme o perfil. Os formulários integrados aproveitam dados de contato, respostas salvas e registros confirmados em campos de texto reconhecidos.

Use **Versões do currículo** para registrar focos como Python ou LLMs. A IA seleciona e ordena os registros confirmados. Cada versão fica disponível em PDF e Word (`.docx`). A vaga analisada também tem seu próprio PDF e Word. Nos conectores validados, o PDF da vaga é o mesmo gerado para anexar automaticamente. As versões focadas criadas manualmente ficam separadas da seleção automática feita para cada vaga.
