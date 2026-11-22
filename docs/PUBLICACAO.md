# Preparar e publicar

Código e downloads ficam no [GitHub](https://github.com/mpaegleee/aplication_assistant). O código usa a licença MIT. Os pacotes ficam em Releases.

## Artefatos da versão 0.6.3

- `ApplicationAssistant-Setup-0.6.3-Windows-x64.exe`
- `ApplicationAssistant-0.6.3-Linux-x64.tar.gz`
- `ApplicationAssistant-Codigo-0.6.3.zip`
- Arquivos SHA-256 e notas da versão.

## Build e publicação

- Windows. `packaging/build-windows.ps1` prepara o executável e as dependências. `ISCC.exe packaging/installer.iss` gera o instalador. O workflow Windows instala a versão anterior, cria dados de teste, atualiza pelo novo instalador e confere a persistência.
- Linux. O workflow Linux prepara o runtime com o lock das dependências, roda `packaging/build_linux.py`, testa a atualização e gera o ZIP de código. O runtime, as bibliotecas Python e o Chromium ficam no pacote.
- Releases. Crie o rascunho com o SHA do commit dos dois builds. Execute **Publicar pacotes de uma versão** com a tag e os IDs dos dois builds aprovados. O workflow calcula os hashes e publica como pré-lançamento.

O instalador Windows ainda não tem assinatura Authenticode. Confira os limites da automação e as instruções de preservação de dados no [guia da versão](ATUALIZACAO-0.6.3.md).
