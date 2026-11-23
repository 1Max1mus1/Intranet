@wiki id=intranet-current-progress type=progress domain=projects state=draft
@summary Intranet 已完成本机隔离预验证，V1/V2/V3/V5 通过，V0 双机环境和 V4 网络性能仍待真实双机验收。
@terms Intranet, progress, 技术验证, 双机待测
@links intranet-overview, intranet-validation-plan, intranet-v0-environment

# Current Progress

## Now

立项文档和隔离技术验证代码已落地。`python -m validation.run_checks` 可重复验证 V1、V2、V3、V5，并输出 V4 信息性测量。当前仍不开发产品外壳，不接入真实工作目录。

## Next

两台电脑均已完成本机预验证、真实双机配对与 TLS 小文件同步。三次 Windows SMB 基线分别为 100.53、39.93、30.91 Mbps，中位数 39.93 Mbps，哈希全部一致，显示热点性能波动明显。临时账户、共享和凭据已清理，结果见 `docs/evidence/smb-baseline-desktop.json`。先前 Intranet 单次 72.52 Mbps 不能直接与该中位数判定优劣，下一步需在相近时段完成多轮 Intranet 传输和双向同步矩阵。

## Risks

当前 V1/V2 使用同一进程中的两个隔离目录，V3/V5 使用回环 TCP，不能证明真实局域网发现、NAT/防火墙、双机时钟偏差或 SMB 相对性能。V4 本机结果不构成通过证据。已有旧 `intranet/` 原型仍不是产品，新 `validation/` 也只是一次性验证材料。

## Evidence

- [V0 本机环境](v0-environment.md)：已登记；另一台电脑与 SMB 基线待补。
- [本机原始 JSON 结果](../evidence/local-results.json)：V1、V2、V3、V5 为 `pass`，V4 为 `informational`。
- V1：新增、修改、删除、稳定重命名身份、零字节重传、排除项、删除记录和状态持久化通过。
- V2：较新版本优先、双端冲突副本、历史恢复和历史清理不删除同步元数据通过。
- V3：真实回环 TCP 断点续传、替换前后中断及损坏数据不覆盖原文件通过。
- V5：错误配对码、未配对证书、未知网络及真实 TLS 1.2/1.3 双向认证边界通过。
- V4：128 MiB 本机直接引擎同步约 0.41 秒，小文件约 0.025 秒；相对本机复制约 33.6%，不是 LAN/SMB 验收值。
