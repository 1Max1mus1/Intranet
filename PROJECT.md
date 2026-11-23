@wiki id=intranet-overview type=project-overview domain=projects state=draft
@summary Intranet 是在两台个人 Windows 电脑之间提供云盘式体验的局域网双向文件同步工具，目前处于立项与技术验证前阶段。
@terms Intranet, 局域网同步, 双向同步, 文件历史
@links intranet-prd, intranet-validation-plan, intranet-roadmap, intranet-current-progress

# Intranet

## Purpose

让用户在自有台式电脑和手提电脑之间交替工作时，无需手动复制文件。两台电脑进入同一受信任局域网后自动同步一组指定目录，文件不经过云端。

## Scope

首版只服务两台固定的 Windows 电脑和一组同步根目录。完整范围见 [PRD](docs/prd.md)。当前只批准关键技术验证，不批准继续产品界面开发。

## Run

当前没有经完整验收的产品运行路径。仓库内已有代码仅为一次性技术验证材料，不应直接接入真实工作目录。后续验证命令、测试数据和结果必须记录在 `docs/progress/current.md`。

## Key entry points

- [产品需求与验收标准](docs/prd.md)
- [技术验证计划与阶段门槛](docs/validation.md)
- [后续开发路线](docs/roadmap.md)
- [架构约束与候选边界](docs/architecture/overview.md)
- [当前进展与证据](docs/progress/current.md)

## Current state

本机隔离预验证已完成，V1/V2/V3/V5 通过；V0 双机环境和 V4 真实局域网性能仍待补测。托盘、主界面、自启动和安装包属于第二阶段，须在双机验证结果经用户审查后实施。
