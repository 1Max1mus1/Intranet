@index scope=projects generated=true

## Knowledge

@ref id=intranet-architecture type=module state=draft path=architecture/overview.md
  Intranet 当前只定义同步引擎、传输、安全和历史等逻辑边界及数据安全不变量，具体技术栈等待验证决定。

@ref id=intranet-current-progress type=progress state=draft path=progress/current.md
  Intranet 已完成本机隔离预验证，V1/V2/V3/V5 通过，V0 双机环境和 V4 网络性能仍待真实双机验收。

@ref id=intranet-data-flow type=module state=draft path=architecture/data-flow.md
  Intranet 的数据从本地完整文件变化出发，经版本协调、加密分块传输和校验替换，在另一端形成文件或冲突与历史记录。

@ref id=intranet-other-computer-preflight type=runbook state=draft path=prompts/other-computer-preflight.md
  给另一台 Windows 电脑 Agent 的完整隔离预验证 Prompt，包含仓库地址、代码前提、环境、命令、证据格式和安全边界。

@ref id=intranet-overview type=project-overview state=draft path=../PROJECT.md
  Intranet 是在两台个人 Windows 电脑之间提供云盘式体验的局域网双向文件同步工具，目前处于立项与技术验证前阶段。

@ref id=intranet-prd type=module state=draft path=prd.md
  Intranet 首版限定两台个人 Windows 电脑和一组目录，提供自动双向同步、冲突副本、历史恢复和受信任网络下的安全直连。

@ref id=intranet-roadmap type=runbook state=draft path=roadmap.md
  Intranet 按立项、同步引擎验证、完整产品落地和七日真实试用推进，每阶段由证据而非代码量决定是否继续。

@ref id=intranet-v0-environment type=progress state=draft path=progress/v0-environment.md
  Intranet V0 已登记当前 Windows 11 本机并建立隔离测试数据生成器，另一台电脑和真实局域网基线仍待补测。

@ref id=intranet-validation-plan type=runbook state=draft path=validation.md
  Intranet 第一阶段只用测试目录验证同步正确性、中断安全、性能和安全边界，通过门槛后才进入产品外壳开发。
