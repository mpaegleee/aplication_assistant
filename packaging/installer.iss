#define AppName "Application Assistant"
#define AppVersion "0.6.1"
[Setup]
AppId={{E694006C-89B5-4A84-B7DD-4D3AE88FB02E}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Application Assistant
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ApplicationAssistant-Setup-0.6.1-Windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\frontend\public\favicon.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE.txt
[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
[Files]
Source: "..\dist\ApplicationAssistant\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Application Assistant"; Filename: "{app}\ApplicationAssistant.exe"
Name: "{autodesktop}\Application Assistant"; Filename: "{app}\ApplicationAssistant.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; Flags: unchecked
[Run]
Filename: "{app}\ApplicationAssistant.exe"; Description: "Abrir Application Assistant"; Flags: nowait postinstall skipifsilent
