# Preparar e publicar

O repositório público é `https://github.com/mpaeglee/Application-Assistant`. Código sob MIT; executáveis e pacotes ficam em **Releases**, separados dos arquivos Git.

## Estado desta entrega

Código e artefatos foram preparados localmente. A conexão GitHub disponível neste ambiente informou apenas leitura (`push: false`); nenhum push ou release foi criado por ela.

Se recebeu o arquivo de código ZIP, extraia e, no seu computador com acesso de escrita ao repositório, execute:

```sh
git init -b main
git add .
git commit -m "Application Assistant 0.6.0"
git remote add origin https://github.com/mpaeglee/Application-Assistant.git
git push -u origin main
```

Se já está usando um clone com commits, confira `git status`, o remoto e o histórico; não reinicialize nem force push. Atualize a branch normalmente.

## Artefatos da versão

- `ApplicationAssistant-Setup-0.6.0-Windows-x64.exe`
- `ApplicationAssistant-0.6.0-Linux-x64.tar.gz`
- `ApplicationAssistant-Codigo-0.6.0.zip`
- Hashes `.sha256` e notas da versão.

Não envie runtime, Chromium ou arquivos de dados como commits. O instalador Windows local é produzido com NSIS a partir do runtime Windows oficial e Chromium Windows. A compilação é real, mas foi feita em Linux: o teste de instalação/abertura/desinstalação em Windows ainda é obrigatório antes de marcar como estável. O workflow Windows gera também o aplicativo PyInstaller e instalador Inno Setup em Windows nativo. Nunca publique um arquivo Linux renomeado para `.exe`.

## Builds

Windows nativo: `packaging/build-windows.ps1`, depois `ISCC.exe packaging/installer.iss`. O workflow `.github/workflows/windows.yml` faz isso e guarda artefatos; não cria uma release pública automaticamente.

Windows portátil em Linux: `packaging/build_portable.py --compiler /caminho/python3.14 --browsers /pasta/chromium-windows`. O Chromium precisa corresponder ao Playwright fixado. `packaging/launcher.nsi` e `packaging/installer.nsi` podem ser compilados com NSIS 3.11 para produzir o instalador Windows a partir desse pacote.

Linux: `packaging/build_linux.py --runtime /pasta/cpython-3.14.10-linux-x86_64-gnu --site /venv314/lib/python3.14/site-packages --browsers /pasta/playwright-linux`. Use runtime portátil confiável e dependências da lock; não copie uma instalação Python que dependa de caminhos absolutos da sua máquina.

Depois de validar os artefatos, crie uma release inicialmente como **pré-lançamento**, com os limites documentados em ATUALIZACAO-0.6.0.md, e anexe os arquivos e hashes. Marque quais testes foram realizados; não descreva os conectores experimentais como compatibilidade universal.
