#define MyAppVersion "0.2.0"

[Setup]
AppId={{6E53A812-8A65-4A09-A4AB-F1634A9A7C31}
AppName=Intranet
AppVersion={#MyAppVersion}
AppPublisher=Victor
DefaultDirName={localappdata}\Programs\Intranet
DefaultGroupName=Intranet
PrivilegesRequired=lowest
OutputDir=dist\installer
OutputBaseFilename=IntranetSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Intranet.exe

[Files]
Source: "dist\Intranet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Intranet"; Filename: "{app}\Intranet.exe"
Name: "{autodesktop}\Intranet"; Filename: "{app}\Intranet.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Intranet"; ValueData: """{app}\Intranet.exe"" --background"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Intranet.exe"; Parameters: "--background"; Flags: nowait postinstall skipifsilent
