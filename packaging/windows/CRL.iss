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

[Code]
function IsAscii(const Value: String): Boolean;
var
  I: Integer;
begin
  Result := True;
  for I := 1 to Length(Value) do
    if Ord(Value[I]) > 127 then
    begin
      Result := False;
      Exit;
    end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Folder: String;
  Existed: Boolean;
begin
  Result := '';
  Folder := ExpandConstant('{app}');
  Existed := DirExists(Folder);
  if not ForceDirectories(Folder) then
  begin
    Result := 'Não foi possível criar a pasta. Volte atrás e escolha uma pasta local onde possa guardar ficheiros.';
    Exit;
  end;
  if not IsAscii(GetShortName(Folder)) then
    Result := 'Esta pasta não é compatível com as bibliotecas de conversão nesta unidade. Volte atrás e escolha uma pasta local sem acentos. Se não tiver permissão, contacte o apoio informático.';
  if not Existed then
    RemoveDir(Folder);
end;

procedure SaveSupportLog(Sender: TObject);
var
  Filename: String;
begin
  Filename := 'CRL-instalacao-apoio.txt';
  if GetSaveFileName('Guardar relatório para o apoio', Filename, '',
    'Relatório de apoio (*.txt)|*.txt', 'txt') then
  begin
    Log('Guardar relatório de instalação para o apoio.');
    if FileCopy(ExpandConstant('{log}'), Filename, False) then
      MsgBox('Relatório guardado. Entregue o ficheiro ao apoio informático.', mbInformation, MB_OK)
    else
      MsgBox('Não foi possível guardar. Escolha outra pasta onde possa guardar ficheiros.', mbError, MB_OK);
  end;
end;

procedure InitializeWizard;
var
  SupportButton: TNewButton;
begin
  SupportButton := TNewButton.Create(WizardForm);
  SupportButton.Parent := WizardForm;
  SupportButton.Left := ScaleX(8);
  SupportButton.Top := WizardForm.CancelButton.Top;
  SupportButton.Width := ScaleX(220);
  SupportButton.Height := WizardForm.CancelButton.Height;
  SupportButton.Caption := 'Guardar relatório para o apoio';
  SupportButton.OnClick := @SaveSupportLog;
end;
