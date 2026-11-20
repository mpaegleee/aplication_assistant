# Atualização 0.1.1 — configuração guiada de IA

## Aplicar na instalação já existente
Este ambiente de desenvolvimento Linux não acessa diretamente o disco D: do seu Windows. A entrega é um ZIP de atualização local.

1. Encerre o Application Assistant pela janela que abriu com Iniciar.cmd (Ctrl+C). Fechar só a aba do navegador não encerra o processo.
2. Extraia **o conteúdo** de ApplicationAssistant-Atualizacao-0.1.1.zip diretamente em `D:\Pessoal\ApplicationAssistant-Windows-Local`, aceitando substituir os arquivos existentes. Não crie outra subpasta com o nome do ZIP.
3. Abra Iniciar.cmd novamente e recarregue a página do navegador.

O ZIP de atualização contém somente `app`, `frontend`, `Ajuda`, manifesto da versão e estas instruções. Não contém runtime, banco, senha, chave de criptografia ou credenciais. Nenhuma migração de banco é necessária. As configurações ficam em `%LOCALAPPDATA%\Application Assistant` e são preservadas.

Para permitir retorno à versão anterior, você pode copiar as pastas app e frontend antes de aplicar. Não substitua nem exclua a pasta de dados.

## Nova configuração
- Escolha o serviço onde criou sua chave. O endereço é preenchido automaticamente.
- Informe a chave correspondente e clique Carregar modelos disponíveis.
- Escolha um identificador real na lista; não há modelo pago selecionado automaticamente.
- Autorize o uso do perfil e teste a conexão.
- Ollama/LM Studio são locais e exigem os programas abertos e modelos instalados. Uma chave de serviço online não os configura.
- Para outro servidor/porta, use Outro serviço compatível; se a API não listar modelos, há opção manual.

Uma configuração antiga é reconhecida pelo endereço salvo. O modelo anterior continua visível; se ele não aparecer na lista, escolha um disponível. Ao trocar de endereço, a chave antiga não é reaproveitada automaticamente para outro endpoint.

## Verificação
45 testes automatizados passaram em Python 3.12 e 3.14, incluindo regressões da versão anterior e:
- catálogo autenticado, sem perfil no payload e sem consumir o limite diário de análises;
- uso de chave salva restrito ao mesmo endereço; troca de endpoint limpa a associação;
- deduplicação de modelos e exclusão de entradas inválidas ou explicitamente sem saída de texto;
- erros 401/402/403/404/429/5xx com orientação, sem repetir segredos/respostas privadas;
- orientação específica quando Ollama não conecta;
- adaptação de parâmetros explicitamente recusados pelo provedor, com limite de tentativas e contagem diária;
- exigência de JSON válido mesmo na adaptação.

Build TypeScript/Vite aprovado. As dependências do runtime não mudaram. O pacote foi preparado em Linux; a execução nativa no Windows e a inspeção visual desta atualização precisam ser confirmadas no seu computador. Nenhuma chave pessoal foi fornecida ao desenvolvedor ou usada em testes pagos.

## Fontes dos endereços
- DeepSeek: https://api-docs.deepseek.com/en/
- OpenAI: https://developers.openai.com/api/reference/resources/models/methods/list
- OpenRouter: https://openrouter.ai/docs/api/api-reference/models/get-models
- Groq: https://console.groq.com/docs/openai
- Ollama: https://docs.ollama.com/api/openai-compatibility
- LM Studio: https://lmstudio.ai/docs/developer/openai-compat
