; Inno Setup script — builds Tarjem-Setup.exe from dist\Tarjem
#define AppName "Tarjem - مترجم الشغل"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6C1E7C2B-5D0B-4E7F-9A43-7A2F1C0B9E11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Tarjem
DefaultDirName={autopf}\Tarjem
DefaultGroupName=Tarjem
OutputDir=..\dist
OutputBaseFilename=Tarjem-Setup-{#AppVersion}
Compression=lzma2/normal
SolidCompression=yes
DiskSpanning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Install per user (no admin) so the program folder stays writable and the
; downloaded model + my terms live next to the program (copy the folder = copy everything).
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\Tarjem.exe

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Tarjem\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Tarjem - مترجم الشغل"; Filename: "{app}\Tarjem.exe"
Name: "{autodesktop}\Tarjem - مترجم الشغل"; Filename: "{app}\Tarjem.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Tarjem.exe"; Description: "{cm:LaunchProgram,Tarjem}"; Flags: nowait postinstall skipifsilent
