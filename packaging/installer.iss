; Installeur Windows : `iscc /DAppVersion=X.Y.Z packaging\installer.iss` depuis la racine,
; après `pyinstaller packaging/vto.spec` et `packaging/fetch_redist.ps1`.
; Installation par utilisateur (aucun UAC) ; les données du client (%LOCALAPPDATA%\VirtualTryOn)
; ne sont jamais touchées, ni à l'installation ni à la désinstallation.

#ifndef AppVersion
  #error Passer la version : iscc /DAppVersion=X.Y.Z
#endif

#define AppName "Virtual Try-On"
#define AppExe "VirtualTryOn.exe"
#define HelpUrl "https://github.com/Jacques-herrmann/virtual-try-on/blob/main/docs/aide/installation.md"

[Setup]
; Ne jamais changer AppId : c'est lui qui relie les versions entre elles.
AppId={{E50E1158-DCC6-4FD5-B832-E269B65A2915}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
AppSupportURL={#HelpUrl}
VersionInfoVersion={#AppVersion}
PrivilegesRequired=lowest
DefaultDirName={autopf}\VirtualTryOn
DisableDirPage=yes
DisableProgramGroupPage=yes
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
SetupIconFile=icon.ico
OutputDir=Output
OutputBaseFilename=VirtualTryOn-Setup-{#AppVersion}
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

[Files]
Source: "..\dist\VirtualTryOn\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
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
