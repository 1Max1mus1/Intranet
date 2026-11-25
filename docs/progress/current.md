@wiki id=intranet-current-progress type=progress domain=projects state=draft
@summary Intranet 第二阶段主界面、配对、自动同步、托盘、自启动和安装包已实现并通过隔离验证，待真实双机产品试用。
@terms Intranet, progress, 第二阶段, 产品落地, 安装包
@links intranet-overview, intranet-validation-plan, intranet-stage-1-review, intranet-tailscale-remote-transfer

# Current Progress

## Now

第二阶段产品外壳已实现：主界面、一次性配对、受信任网络、后台自动同步、即时多行文字收发、静态地址、暂停恢复、历史恢复、排除项、托盘、Windows 登录自启动和当前用户安装包。配对页同时显示并支持复制本机 IP:端口，显示已配对地址并支持断开且保留文件。

v0.2.2 修复了用户实测发现的问题：netsh/PowerShell 子进程以 CREATE_NO_WINDOW 隐藏，网络查询使用 2 秒缓存，界面实时刷新网络，通知限流，退出停止轮询。回归证据见 `docs/evidence/ui-recovery-validation.json`。

`python -m validation.product_smoke --gui` 的配对、A→B、B→A、暂停恢复和 GUI/托盘生命周期全部通过。UI 已统一为苹果简约风：浅灰背景、白色卡片、左侧导航和单一蓝色强调，四个页面已实际渲染检查。打包应用后台启动通过；最终安装器通过静默安装、安装后启动、卸载和注册表恢复。证据见 `docs/evidence/product-validation.json`。

## Next

1. 在两台真实电脑上安装 `dist/installer/IntranetSetup.exe`，用隔离目录完成产品版配对与同步。
2. 确认日常使用流程后，用真实工作目录进行至少 7 天试用，记录冲突、历史恢复、资源占用和手动兜底行为。
3. 真实热点断网仍按用户决定跳过，不把进程续传或 Windows 重启证据宣传为物理断网证据。
4. 第三阶段再按已记录方向实现 Tailscale 按需文件传输助手，不与第二阶段同步模式混淆。

## Risks

本机产品验证不等于真实双机产品验收。安装器尚未发布到 GitHub Release，当前位于本机 `dist/installer/IntranetSetup.exe`。首次接入真实目录前必须确认排除项、历史区和删除规则；第二阶段未完成七日验收。

## Evidence

- [产品验证结果](../evidence/product-validation.json)：配对、双向 TLS、暂停恢复、GUI、打包与安装卸载通过。
- [第一阶段评审](stage-1-review.md)：核心同步、性能、安全和 Windows 整机恢复证据。
- [性能比较](../evidence/intranet-performance-desktop.json)：Intranet 中位 177.31 Mbps，SMB 中位 39.93 Mbps。
- [自动发现与恢复](../evidence/auto-discovery-recovery.json)：发现 0.828 秒，小文件 1.099 秒。
- [Windows 整机恢复](../evidence/windows-reboot-result.json)：配对保留，发现 0.828 秒。
- [进程续传](../evidence/process-resume-result.json)：断点 512114688 字节，仅续传 24756224 字节，哈希一致。
