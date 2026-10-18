; ArchiLinkAI 桌面安装器脚本（Inno Setup 6.x）
; 由 installer/build_installer.py 传入 MyAppVersion
; 安装内容：嵌入式 Python + archilinkai wheel + 客户端配置写入
; 前置准备：installer/payload/ 下放嵌入式 Python 目录与 archilinkai-*.whl

#define MyAppName "筑元智联 ArchiLinkAI"
#define MyAppId "{{B7A3E2C1-8D4F-4A1B-9C5D-7E2F1A3B5C7D}"
#define MyAppPublisher "筑元智联"
#ifndef MyAppVersion
  #define MyAppVersion "0.38.0"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\ArchiLinkAI
DefaultGroupName=ArchiLinkAI
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\python.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\dist
OutputBaseFilename=ArchiLinkAI-Setup-{#MyAppVersion}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; 嵌入式 Python（构建阶段从 python-3.12-embed-amd64.zip 解压到 payload/python/）
Source: "payload\python\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
; archilinkai wheel（python -m build 生成）
Source: "payload\archilinkai-*.whl"; DestDir: "{app}\wheel"

[Icons]
Name: "{group}\ArchiLinkAI 命令行"; Filename: "{cmd}"; Parameters: "/k archilinkai doctor"

[Run]
; 用嵌入式 Python 装 archilinkai（从本地 wheel，不依赖外网）
Filename: "{app}\python.exe"; \
  Parameters: "-m pip install {app}\wheel\archilinkai-*.whl --no-index --find-links {app}\wheel"; \
  Description: "安装 ArchiLinkAI..."; StatusMsg: "正在安装 ArchiLinkAI..."; Flags: runhidden
; 写入各客户端配置（失败不阻塞安装）
Filename: "{app}\python.exe"; Parameters: "-m archilinkai.cli install claude"; Flags: runhidden; StatusMsg: "配置 MCP 客户端..."

[UninstallRun]
; 卸载时不删除已写入的客户端配置（保留用户数据）

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
