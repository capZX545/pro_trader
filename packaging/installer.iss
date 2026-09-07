; Inno Setup script — Windows installer (built by CI; or open in Inno Setup 6 and press Compile)
#define AppName "ProTrader Academy"
#define AppVersion GetEnv("PT_VERSION")
#if AppVersion == ""
  #define AppVersion "1.0.0"
#endif
[Setup]
AppId={{7B1E7D9A-5C1E-4F63-9E47-PROTRADER0001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=capZX545
DefaultDirName={autopf}\ProTrader
DefaultGroupName={#AppName}
OutputDir=..\release
OutputBaseFilename=ProTrader-Setup-{#AppVersion}-windows-x64
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
PrivilegesRequired=lowest
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\ProTrader.exe
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
[Files]
Source: "..\dist\ProTrader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\ProTrader.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\ProTrader.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\ProTrader.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
