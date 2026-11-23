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

## 另一台电脑（Victor-Desktop）

- 系统：Windows 11 专业版 10.0.26300，AMD64。
- CPU：AMD Ryzen 7 9700X，16 逻辑处理器；内存 32 GiB。
- 硬盘：Fanxiang S790 2TB NVMe，系统盘剩余约 160.40 GiB。
- Python：3.11.15；验证依赖 cryptography 48.0.1。
- 网络：Realtek 8922AE WiFi 7，CUHK1x，链路 1.2 Gbps，当前 WLAN IP 10.13.59.242，网关 10.13.63.254。
- 虚拟接口：Tailscale、VirtualBox、Hyper-V/WSL、QuickFox TAP、TAP-Windows Adapter V9。
- 同一 commit `37affde` 上 V1/V2/V3/V5 本机预验证通过，V4 仅为 informational。原始摘要见 `docs/evidence/desktop-local-results.json`。

## 双机连通性结果

双向 WLAN Ping、TCP 445 和台式端到本机临时 TCP 47630 均失败。台式端到本机 Tailscale 仅通过 DERP(sin) 收到 89–94 ms 的 pong，未建立直连；反向 Tailscale Ping 超时。临时监听器已关闭，未执行文件同步。

当前 CUHK1x 不能直接用于双机验收。现象符合设备隔离或校园网路由限制，但不能仅凭这些结果确认具体机制。完整证据见 `docs/evidence/network-connectivity.md`。

## 尚待完成

- 两端切换到同一个用户可控的私有热点或家庭路由器，重新登记 IP 并验证双向 Ping 与 TCP。
- 路由器、是否双 NAT 及可用测试网络确认。
- 同一批大文件通过 Windows SMB 共享传输的吞吐基线，至少三轮记录原始结果。

V0 尚不能整体判定通过；两台本机准备已完成，可用双机网络与 SMB 基线是剩余门槛。
