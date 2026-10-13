; Installeur Windows : `iscc /DAppVersion=X.Y.Z packaging\installer.iss` depuis la racine,
; après `pyinstaller packaging/vto.spec` et `packaging/fetch_redist.ps1`.
; Installation par utilisateur (aucun UAC) ; les données du client (%LOCALAPPDATA%\Kaloe) ne sont
; jamais touchées, ni à l'installation ni à la désinstallation. L'app déplace elle-même l'ancien
; dossier %LOCALAPPDATA%\VirtualTryOn au premier lancement (vto.core.paths).

#ifndef AppVersion
  #error Passer la version : iscc /DAppVersion=X.Y.Z
#endif

#define AppName "Kaloé"
#define AppExe "Kaloe.exe"
; Avant le sous-projet 6 : dossier, exe et raccourcis retirés à la mise à jour.
#define LegacyDir "VirtualTryOn"
#define LegacyExe "VirtualTryOn.exe"
#define LegacyName "Virtual Try-On"
#define HelpUrl "https://kaloe.fr/aide"

[Setup]
; Ne jamais changer AppId : c'est lui qui relie les versions entre elles.
AppId={{E50E1158-DCC6-4FD5-B832-E269B65A2915}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
AppSupportURL={#HelpUrl}
; Versions texte : VersionInfoVersion exige des chiffres seuls, refusant les préversions (0.3.0rc1).
VersionInfoTextVersion={#AppVersion}
VersionInfoProductTextVersion={#AppVersion}
PrivilegesRequired=lowest
DefaultDirName={autopf}\Kaloe
; Sinon Inno réinstallerait dans l'ancien dossier, retrouvé grâce à l'AppId.
UsePreviousAppDir=no
DisableDirPage=yes
DisableProgramGroupPage=yes
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
SetupIconFile=icon.ico
OutputDir=Output
OutputBaseFilename=Kaloe-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Mise à jour : l'app se ferme d'elle-même ; Inno attend ou ferme ce qui tient encore {app}.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
french.WebView2Failed=Un composant Windows (WebView2) n'a pas pu être installé. L'application risque de ne pas s'ouvrir.%n%nConsulte la page d'aide : {#HelpUrl}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Retire les fichiers de l'ancienne version (modules supprimés) avant de copier la nouvelle.
Type: filesandordirs; Name: "{app}\_internal"
; Ancienne installation « Virtual Try-On » (programme seul : les données sont ailleurs).
Type: filesandordirs; Name: "{autopf}\{#LegacyDir}"
Type: files; Name: "{autoprograms}\{#LegacyName}.lnk"
Type: files; Name: "{autodesktop}\{#LegacyName}.lnk"

[Files]
Source: "..\dist\Kaloe\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "redist\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Installation normale : case « Lancer » sur la dernière page.
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Mise à jour silencieuse lancée par l'app : on la relance.
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: WizardSilent

[Code]
const
  WebView2Key = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasVersion(Root: Integer; Key: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function WebView2Installed: Boolean;
begin
  Result := HasVersion(HKLM32, 'SOFTWARE\' + WebView2Key) or HasVersion(HKCU, 'Software\' + WebView2Key);
end;

function IsProcessRunning(Name: String): Boolean;
var
  Locator, Service, Found: Variant;
begin
  Result := False;
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('.', 'root\CIMV2');
    Found := Service.ExecQuery(Format('SELECT ProcessId FROM Win32_Process WHERE Name = ''%s''', [Name]));
    Result := Found.Count > 0;
  except
    Log('Liste des processus indisponible : ' + GetExceptionMessage);
  end;
end;

{ Mise à jour depuis « Virtual Try-On » : l'ancienne app se ferme d'elle-même après avoir lancé
  l'installeur, mais CloseApplications ne la couvre pas (elle n'est pas dans le nouveau dossier).
  On l'attend un peu pour pouvoir supprimer son dossier ; sinon il reste, sans danger. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Tries: Integer;
begin
  Tries := 0;
  while IsProcessRunning('{#LegacyExe}') and (Tries < 30) do
  begin
    Sleep(500);
    Tries := Tries + 1;
  end;
  if Tries > 0 then
    Log(Format('Attente de {#LegacyExe} : %d ms', [Tries * 500]));
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssInstall) and not WebView2Installed then
  begin
    ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '',
                SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
    begin
      Log(Format('Installation de WebView2 impossible (code %d)', [ResultCode]));
      SuppressibleMsgBox(CustomMessage('WebView2Failed'), mbError, MB_OK, IDOK);
    end;
  end;
end;
