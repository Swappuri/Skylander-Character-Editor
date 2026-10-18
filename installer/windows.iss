#ifndef AppVersion
#define AppVersion "0.0.0"
#endif

[Setup]
AppId={{e67eb5a1-2e42-49ae-8c33-2f43f034b19d}
AppName=Skylander Character Editor
AppVersion={#AppVersion}
AppPublisher=Skylander Character Editor
DefaultDirName={autopf}\Skylander Character Editor
DefaultGroupName=Skylander Character Editor
UninstallDisplayIcon={app}\Skylander Character Editor.exe
OutputDir=..\dist
OutputBaseFilename=Skylander-Character-Editor-windows-x86_64-Setup
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Skylander Character Editor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Skylander Character Editor"; Filename: "{app}\Skylander Character Editor.exe"
Name: "{autodesktop}\Skylander Character Editor"; Filename: "{app}\Skylander Character Editor.exe"; Tasks: desktopicon
