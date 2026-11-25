@wiki id=intranet-architecture type=module domain=projects state=draft
@summary Intranet 产品由同步引擎、TLS 网络、配对配置、后台服务、Tkinter 界面、托盘和 Windows 安装构建组成。
@terms Intranet, architecture, 同步引擎, 产品架构, Windows
@links intranet-prd, intranet-validation-plan

# Architecture Overview

## Modules

- `intranet/engine.py`：稳定文件身份、版本、冲突、历史、排除、原子替换和断点文件。
- `intranet/security.py`：配对注册、证书、网络策略和 TLS 上下文。
- `intranet/network.py`：清单与内容协议、偏移续传、即时文字消息、双向证书校验。
- `intranet/pairing.py`：一次性配对码和证书交换。
- `intranet/config.py`：用户配置、当前网络与定向广播计算。
- `intranet/service.py`：受信任网络门禁、UDP 发现、静态地址、后台同步、暂停和历史清理。
- `intranet/app.py`：主界面、配对、历史恢复、设置与事件展示。
- `intranet/tray.py`：托盘菜单、状态和冲突/清理通知。
- `intranet/theme.py`：苹果简约风配色、字体、侧栏导航、卡片与按钮样式。
- `intranet/autostart.py`：当前用户 Run 注册表项。
- `build.ps1` / `installer.iss`：PyInstaller 与当前用户 Inno Setup 安装包。

## Interfaces

UI 和托盘只通过 `IntranetService` 的事件队列、暂停接口和历史接口控制后台，不直接修改同步记录。`ConfigStore` 管理目录、证书与配对材料，秘密不写入普通配置或日志。验证代码只使用隔离目录。

## Invariants

- 半成品绝不能成为成功版本或替换原完整文件。
- 网络请求期间不持有本地状态锁，避免双向同步相互等待。
- 并发冲突不得静默丢弃任何一方内容。
- 排除项不传播删除；未知网络不启动监听或同步。
- 未配对设备不能通过证书指纹和双向 TLS 认证。
- 关闭窗口只隐藏到托盘，退出必须从托盘明确执行。

## Failure modes

锁死文件、持续写入、磁盘不足、广播禁用、断网、进程重启、Windows 重启、时钟偏差、同名冲突和历史区满均有对应处理或明确未验收边界。真实物理断网目前按用户决定跳过。
