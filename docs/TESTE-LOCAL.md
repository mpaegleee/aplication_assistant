# Roteiro de teste local

## Windows sem ferramentas de desenvolvimento
1. Extraia **ApplicationAssistant-Windows-Local-0.1.0.zip** inteiro.
2. Abra **Iniciar.cmd**. O runtime e dependências estão no pacote.
3. Aguarde http://127.0.0.1:8765. Se não abrir sozinho, digite o endereço no navegador.
4. Crie a senha local. Nenhum dado demonstrativo aparece no painel.
5. Mantenha a janela do programa aberta. Para encerrar, Ctrl+C.

O pacote foi montado em Linux e precisa ser executado em Windows para validar DLLs, abertura de navegador e permissões. O instalador `.exe` final tem pipeline de build, mas não foi compilado nem validado neste ambiente Linux. Esta entrega é um pacote portátil de teste, não uma release pública.

## Preparação a partir do código
Python 3.12 x64 e Node.js 24 LTS instalados: abra **Preparar-e-iniciar.cmd**. Na primeira execução, precisa de internet para dependências. Isso inclui o código e destina-se ao mantenedor.

## Teste funcional sem enviar candidaturas reais
- Configurar IA e validar conexão.
- Importar PDF de um perfil fictício, confirmar texto e extrair fatos.
- Editar um fato e conferir que passa a ser manual e exige confirmação.
- Definir Desenvolvimento como desejada e Financeiro como excluída.
- Adicionar vaga remota de desenvolvimento, descrição completa e área confirmada; analisar.
- Conferir pesos, evidências e lacunas. Baixar o PDF e checar que não inventou informações.
- Adicionar uma vaga financeira e confirmar bloqueio antes da IA, inclusive com limite 65%.
- Adicionar a mesma URL com parâmetro `utm_source` e confirmar deduplicação.
- Alterar perfil e verificar que a candidatura precisa de nova análise.
- Conferir que rotina pausada não executa nem envia.
- Fechar e abrir o programa e verificar persistência e pedido de senha.

## Teste de e-mail com destinatário controlado
Use uma conta de remetente e uma caixa de destinatário suas. Não teste com recrutadores reais.

1. Configure SMTP com TLS e senha de aplicativo suportada pelo provedor.
2. Cadastre uma vaga fictícia com descrição "Desenvolver APIs Python. Envie seu currículo para SEU-ENDERECO-DE-TESTE" e esse destinatário no campo próprio.
3. Use modo de aprovação, limite diário baixo e critérios compatíveis.
4. Analise, aprove e retome a rotina. Só então clique Enviar por e-mail.
5. Confira destinatário, assunto, corpo e PDF na caixa de teste. Aceite SMTP não prova entrega.
6. Tente enviar de novo: deve ser bloqueado.
7. Responda ao e-mail com convite fictício para entrevista, exporte `.eml`, importe em Retornos e confirme a sugestão.
8. Pause a rotina novamente e desabilite envio de e-mail após o teste.

## Automação
Cadastre fontes RSS/JSON/JobPosting que você esteja autorizado a consumir e permita seus domínios exatos. Revise as áreas importadas; nesta versão não são liberadas silenciosamente. Para testar agenda, marque um horário futuro próximo no fuso correto e mantenha o computador ativo. O histórico deve registrar uma única execução para aquele horário.

## Relatar problemas
Informe sistema operacional, versão, ação, resultado esperado e mensagem exibida. Não publique chave, senha, currículo, arquivo de dados, e-mail privado ou `vault.key`. O painel não guarda logs com credenciais. Reportar resultado de modelos de IA exige remover dados pessoais do exemplo.

## Casos reais fornecidos para os conectores

- [PORTAL-001 — LinkedIn → Essentia Group/Gupy → autenticação](casos/PORTAL-001-linkedin-gupy-essentia.json): Scrum Master - Presencial, Palhoça/SC. Evidência recebida em 20/11/2026; fluxo documentado até o login, sem navegação de validação nem envio de candidatura. Etapas posteriores ainda não observadas.
