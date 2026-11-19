; Instalador de Minecraft Server Manager para Windows 10 y 11 (en español).
#define AppName "Minecraft Server Manager"
#define AppVersion "1.0.0"
#define AppExe "MinecraftServerManager.exe"

[Setup]
AppId={{B7C0E3D2-5A4F-4C8E-9E21-3D6F0A1B2C3D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Minecraft Server Manager
DefaultDirName={autopf}\MinecraftServerManager
DefaultGroupName={#AppName}
OutputDir=..\dist-installer
OutputBaseFilename=MinecraftServerManager-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
MinVersion=10.0
WizardStyle=modern
SetupIconFile=..\assets\icono.ico
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un icono en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\MinecraftServerManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent