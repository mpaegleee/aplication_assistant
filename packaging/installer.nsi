Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!define VERSION "0.6.3"
Name "Application Assistant"
OutFile "../dist/ApplicationAssistant-Setup-${VERSION}-Windows-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\Application Assistant"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "Application Assistant — gratuito e de código aberto"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "../LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\ApplicationAssistant.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Abrir Application Assistant"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"
Function .onInit
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "Esta versão exige Windows 10 ou superior."
    Abort
  ${EndIf}
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Esta versão exige Windows 10/11 de 64 bits."
    Abort
  ${EndIf}
  MessageBox MB_OKCANCEL "Feche a aplicação e sua janela de execução antes de instalar ou atualizar. Seus dados pessoais serão preservados." /SD IDOK IDOK continue
  Abort
  continue:
FunctionEnd
Section "Application Assistant" Main
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "../dist/ApplicationAssistant-Windows-Local/*"
  WriteUninstaller "$INSTDIR\Desinstalar.exe"
  CreateDirectory "$SMPROGRAMS\Application Assistant"
  CreateShortcut "$SMPROGRAMS\Application Assistant\Application Assistant.lnk" "$INSTDIR\ApplicationAssistant.exe"
  CreateShortcut "$SMPROGRAMS\Application Assistant\Desinstalar.lnk" "$INSTDIR\Desinstalar.exe"
  CreateShortcut "$DESKTOP\Application Assistant.lnk" "$INSTDIR\ApplicationAssistant.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ApplicationAssistant" "DisplayName" "Application Assistant"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ApplicationAssistant" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ApplicationAssistant" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
SectionEnd
Section "Uninstall"
  SetShellVarContext current
  Delete "$DESKTOP\Application Assistant.lnk"
  Delete "$SMPROGRAMS\Application Assistant\Application Assistant.lnk"
  Delete "$SMPROGRAMS\Application Assistant\Desinstalar.lnk"
  RMDir "$SMPROGRAMS\Application Assistant"
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\frontend"
  RMDir /r "$INSTDIR\browsers"
  RMDir /r "$INSTDIR\Ajuda"
  Delete "$INSTDIR\ApplicationAssistant.exe"
  Delete "$INSTDIR\Iniciar.cmd"
  Delete "$INSTDIR\Redefinir-senha.cmd"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\LEIA-ME.txt"
  Delete "$INSTDIR\THIRD-PARTY-NOTICES.txt"
  Delete "$INSTDIR\FRONTEND-NOTICES.txt"
  Delete "$INSTDIR\build-manifest.json"
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ApplicationAssistant"
  MessageBox MB_OK "Aplicação removida. Os dados e sessões em $LOCALAPPDATA\Application Assistant foram preservados. Consulte a ajuda para apagá-los se desejar."
SectionEnd
