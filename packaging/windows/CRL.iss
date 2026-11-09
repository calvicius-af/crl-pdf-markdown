; Compilar apenas depois do ensaio do runtime completo, na máquina de preparação.
#ifndef Payload
  #error Payload is required
#endif
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef Output
  #error Output is required
#endif
[Setup]
AppId={{026193C4-73BB-46B1-A923-469A65D11285}
AppName=CRL — PDF para Markdown
AppVersion={#AppVersion}
AppPublisher=CRL
DefaultDirName={localappdata}\Programs\CRL-PDF-Markdown\{#AppVersion}
UsePreviousAppDir=no
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
OutputDir={#Output}
OutputBaseFilename=CRL-{#AppVersion}-windows-x64-offline
Compression=lzma2
SolidCompression=yes
DiskSpanning=no
WizardStyle=modern
UninstallDisplayName=CRL — PDF para Markdown {#AppVersion}
CloseApplications=yes
SetupLogging=yes

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\Abrir CRL"; Filename: "{app}\python\pythonw.exe"; Parameters: "-I -X utf8 -B -m crl_markdown.desktop"; WorkingDir: "{app}\recursos"
Name: "{userprograms}\Abrir CRL"; Filename: "{app}\python\pythonw.exe"; Parameters: "-I -X utf8 -B -m crl_markdown.desktop"; WorkingDir: "{app}\recursos"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-I -X utf8 -B -m crl_markdown.desktop"; WorkingDir: "{app}\recursos"; Description: "Abrir CRL"; Flags: nowait postinstall skipifsilent
