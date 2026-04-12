#include "TradeDangerous.version.iss.inc"

[Setup]
AppId=TradeDangerous
AppName=Trade Dangerous
AppVersion={#TDVersion}
AppPublisher=Trade Dangerous Dev Team
DefaultDirName={autopf}\TradeDangerous
DefaultGroupName=Trade Dangerous
OutputBaseFilename=TradeDangerous-Setup-{#TDVersion}
SetupIconFile=tradedangerouscrest.ico
UninstallDisplayIcon={app}\TradeDangerous.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\TradeDangerous\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Trade Dangerous"; Filename: "{app}\TradeDangerous.exe"; WorkingDir: "{app}"
Name: "{commondesktop}\Trade Dangerous"; Filename: "{app}\TradeDangerous.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKLM; Subkey: "Software\TradeDangerous"; ValueType: string; ValueName: "InstallChannel"; ValueData: "packaged"; Flags: uninsdeletekey

[Code]
function GetUserDataDir(Param: String): String;
begin
  Result := ExpandConstant('{localappdata}\TradeDangerous');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Response: Integer;
begin
  if CurUninstallStep = usUninstall then begin
    DataDir := GetUserDataDir('');
    if DirExists(DataDir) then begin
      Response := SuppressibleMsgBox(
        'Do you also want to remove your Trade Dangerous user data?' + #13#10 + #13#10 +
        DataDir,
        mbConfirmation,
        MB_YESNO,
        IDNO
      );
      if Response = IDYES then begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;