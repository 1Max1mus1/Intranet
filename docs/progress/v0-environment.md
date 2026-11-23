@wiki id=intranet-v0-environment type=progress domain=projects state=draft
@summary Intranet V0 已登记当前 Windows 11 本机并建立隔离测试数据生成器，另一台电脑和真实局域网基线仍待补测。
@terms Intranet, V0, 测试环境, Windows 文件共享
@links intranet-validation-plan, intranet-current-progress

# V0 环境与基线

登记日期：2026-11-23（本机）。

## 当前电脑

- 计算机名：Victor
- 系统：Windows 11，10.0.26300，AMD64
- CPU：Intel Core Ultra 9 285H，16 逻辑处理器
- 内存：31.4 GiB
- 硬盘：Samsung MZVL81T0HELB NVMe，约 954 GB
- 系统盘：931.9 GiB，剩余约 43.8 GiB
- 网络适配器：Intel Wi-Fi 7 BE201；另有 VirtualBox、Tailscale 和 Meta 虚拟适配器
- Python：3.13.2

### 当前网络（2026-11-23 复验）

- 当前 WLAN：CUHK1x，协商速率 1.2 Gbps。
- 活动局域网地址：10.13.176.36；该地址只用于本次测试协调，网络切换后需重新登记。
- Meta、Tailscale 等虚拟接口同时存在路由，双机测试须确认使用正确接口；Intranet SMB 基线不经过 Tailscale。
- 当前属于校园/企业式网络，可能存在设备隔离或 SMB 限制。未实测前不假定 AP 隔离，也不把连接失败归因于同步程序。

## 隔离测试数据

`validation/corpus.py` 可重复生成文本、代码、有效 PNG、空文件、中文与长文件名、200 个小文件和确定性伪随机大文件。默认大文件为 128 MiB，不读取或复制真实工作目录。生成位置限定为 `.validation-data`，该目录已加入 `.gitignore`。

## 尚待另一台电脑完成

- Windows、CPU、内存、硬盘、网卡和实际连接方式。
- 路由器、Wi-Fi 频段/有线速率、是否 AP 隔离和双 NAT。
- 同一批大文件通过 Windows SMB 共享传输的吞吐基线，至少三轮记录原始结果。

V0 尚不能整体判定通过；本机准备已完成，双机环境及 SMB 基线是剩余门槛。
