@wiki id=intranet-network-connectivity type=progress domain=projects state=draft
@summary CUHK1x 下双机 WLAN 的 Ping、SMB 和自定义 TCP 双向均失败，Tailscale 仅通过新加坡 DERP 以约 90ms 连通，当前网络不满足直接联测条件。
@terms Intranet, CUHK1x, 连通性, AP 隔离, DERP
@links intranet-v0-environment, intranet-validation-plan

# 双机网络连通性证据

测试日期：2026-11-23。两端均连接 CUHK1x。

- 手提端 Victor：WLAN 10.13.176.36。
- 台式端 Victor-Desktop：WLAN 10.13.59.242，前缀 /16。

| 方向与检查 | 结果 |
|---|---|
| 手提 → 台式 WLAN Ping | 手提自身返回 DestinationHostUnreachable |
| 手提 → 台式 TCP 445 | 失败 |
| 台式 → 手提 WLAN Ping | 台式自身返回 Destination host unreachable，另一次超时 |
| 台式 → 手提 TCP 445 | False |
| 台式 → 手提临时 TCP 47630 | False |
| 台式 → 手提 Tailscale | 经 DERP(sin) 收到 3 个 pong，89–94 ms，未建立 direct |
| 手提 → 台式 Tailscale | 三次均超时，无回复 |

临时 TCP 47630 服务只接受并关闭连接，不传输文件，测试后已停止。两端未修改防火墙、路由器、共享、路由或 VPN 设置，未执行文件同步。

## 结论与限制

当前 CUHK1x 下，两端无法通过 WLAN 直接建立测试所需的 IP/TCP 连接。现象符合设备隔离或校园网路由限制，但仅凭这些结果不能确认具体机制。Tailscale 的 DERP 中继路径不满足 Intranet 局域网直连和性能验收条件。

下一步应把两端切换到同一个用户可控的私有热点或家庭路由器，重新登记 IP 并执行双向 Ping、TCP 445 和自定义 TCP 测试。新网络连通前，不进入 SMB 或同步性能验收。
