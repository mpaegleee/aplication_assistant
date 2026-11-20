# Verificação da versão 0.1 para teste local

Data: 20/11/2026. Ambiente de desenvolvimento: Linux remoto. Nenhuma publicação, candidatura real ou mensagem a terceiros foi realizada.

## História verificada
Criar instalação pessoal → entrar com senha → importar/revisar perfil → cadastrar vaga → bloquear incompatibilidade ou analisar com evidências → gerar PDF factual → aprovar → enviar por SMTP configurado → registrar acompanhamento.

## Resultados
| Verificação | Resultado e evidência |
|---|---|
| TypeScript e build da interface | `npm --prefix frontend run build`: passou; HTML, CSS e JavaScript gerados |
| Testes Python 3.12 | 30 testes passaram |
| Testes Python 3.14, mesma linha do runtime portátil | 30 testes passaram |
| Segurança de dependências Python | `pip-audit -r backend/requirements.txt`: nenhuma vulnerabilidade conhecida encontrada |
| Dependências frontend de produção | `npm audit --omit=dev --audit-level=high`: nenhuma vulnerabilidade encontrada |
| Build Docker | Passou com CA do ambiente montada temporariamente como segredo de build; verificação TLS mantida |
| HTTP real no container | Passaram: token de configuração, senha, sessão, HTML/JS, perfil, cadastro e bloqueio por área |
| Persistência no container | Passou: reinício com volume preserva conta e perfil |
| Pacote Windows | Runtime CPython x64 oficial, wheels Windows nativas, interface compilada, app em bytecode e avisos incluídos; ZIP íntegro |
| Compatibilidade de bytecode | Cabeçalho dos módulos do app coincide com o runtime CPython incluído |
| Navegador visual | Não verificado: ferramenta do ambiente falhou ao iniciar com erro de sandbox |
| Execução nativa Windows e instalador .exe | Pendente: ambiente disponível é Linux; pacote portátil precisa do primeiro teste Windows |
| Provedor de IA real com perfil do usuário | Não executado; nenhum modelo/chave pessoal fornecido. Protocolo HTTP e JSON testados com transporte controlado |
| Entrega por SMTP real | Não executada; envio, conteúdo do MIME, erros e idempotência testados com transporte controlado |

Há um aviso de depreciação do cliente de testes Starlette/httpx. Não houve falha de teste; não afeta a execução normal da aplicação.

## Regras exercitadas nos testes
Autenticação e origem; bloqueio de área apesar de nota potencial alta; perfil não confirmado; ausência de salário obrigatório; evidências falsas rejeitadas; pesos; PDF legível e fatos literais; deduplicação persistente; aprovação antes do envio; pausa; mudança de perfil invalida análise; automático configurado; falha SMTP incerta; concorrência sem envio duplicado; segredo oculto nas respostas e criptografado no banco; limites atômicos; SSRF e domínios; JobPosting fora do Brasil recusado; e-mail exige instrução explícita; instruções personalizadas e negação bloqueiam SMTP; retorno não atualiza sozinho; chave ausente não é recriada; falha e limite de IA; limite de tentativas de login; recuperação de execução interrompida; protocolo Chat Completions sem segredos no payload; recuperação offline de senha invalida sessões.

## Limites de produto para o primeiro teste
- LinkedIn e Gupy têm finalização assistida. Não há varredura autenticada ou preenchimento automático desses portais.
- Fontes disponíveis: cadastro manual, RSS/JSON e páginas públicas com JobPosting em domínios autorizados. Importações exigem revisão da área.
- Automático disponível somente para SMTP com destinatário e instrução explícitos na descrição, perfil confirmado, nota/confiança suficientes e limites respeitados.
- Currículo adaptado seleciona e ordena fatos confirmados. Ainda não reescreve texto em novas seções nem responde formulários de ATS.
- Retornos: atualização manual e arquivo .eml. Sem OAuth, leitura contínua de caixa postal ou gestão de calendário.
- Confiança do modelo é estimada; os testes não demonstram precisão estatística na classificação de perfis reais. Usar modo de aprovação no piloto e avaliar casos de áreas semelhantes antes de liberar automático para distribuição.
- Sem assinatura digital Windows, atualização automática ou instalador .exe compilado neste ambiente.

## Próximo aceite
Seguir TESTE-LOCAL.md em Windows 10/11 x64. Validar abertura do pacote, PDF real, provedor escolhido, permissões de dados e envio para caixa de teste controlada pelo mantenedor. Depois decidir distribuição e próximos conectores. O código foi mantido local; publicação está adiada conforme solicitado.
