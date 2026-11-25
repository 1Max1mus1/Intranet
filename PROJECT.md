@wiki id=intranet-overview type=project-overview domain=projects state=draft
@summary Intranet 是在两台个人 Windows 电脑之间提供云盘式体验的局域网双向同步工具，第二阶段产品外壳和安装包已实现并通过本机验证。
@terms Intranet, 局域网同步, 双向同步, 文件历史, Windows 安装包
@links intranet-prd, intranet-validation-plan, intranet-roadmap, intranet-current-progress

# Intranet

## Purpose

让用户在自有台式电脑和手提电脑之间交替工作时，无需手动复制文件。两台电脑进入同一受信任局域网后自动同步一组指定目录，文件不经过云端。

## Scope

首版服务两台固定 Windows 电脑和一组同步根目录，包含配对、后台同步、即时文字传输、托盘、历史恢复、自启动和安装包。第三阶段通过 Tailscale 提供按需文件传输助手，详见路线图。

## Run

- 源码：`python main.py`，后台模式为 `python main.py --background`。
- 安装：`dist/installer/IntranetSetup.exe`，支持当前用户安装和卸载。
- 构建：`powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1`。
- 产品隔离验证：`python -m validation.product_smoke --gui`。

首次使用必须手动选择目录、配对并信任网络。已有验证材料和产品隔离测试不等于真实工作目录验收。

## Key entry points

- [产品需求与验收标准](docs/prd.md)
- [技术验证计划与阶段门槛](docs/validation.md)
- [后续开发路线](docs/roadmap.md)
- [架构约束与候选边界](docs/architecture/overview.md)
- [当前进展与证据](docs/progress/current.md)
- [第三阶段 Tailscale 决策](docs/adr/0001-tailscale-remote-transfer.md)

## Current state

第二阶段的主界面、配对、后台自动同步、托盘、自启动和安装包已实现。产品隔离配对与双向 TLS、暂停恢复、GUI、打包应用及安装/卸载均通过。真实双机产品试用和第二阶段七日验收尚未完成。
