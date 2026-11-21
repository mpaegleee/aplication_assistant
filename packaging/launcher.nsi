Unicode true
Name "Application Assistant"
OutFile "../dist/ApplicationAssistant-Windows-Local/ApplicationAssistant.exe"
RequestExecutionLevel user
SilentInstall silent
AutoCloseWindow true
Section
  SetOutPath "$EXEDIR"
  Exec '"$EXEDIR\runtime\python.exe" "$EXEDIR\app\launcher.pyc"'
SectionEnd
