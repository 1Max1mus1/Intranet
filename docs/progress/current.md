@wiki id=intranet-current-progress type=progress domain=projects state=draft
@summary Intranet 已完成本机隔离预验证，V1/V2/V3/V5 通过，V0 双机环境和 V4 网络性能仍待真实双机验收。
@terms Intranet, progress, 技术验证, 双机待测
@links intranet-overview, intranet-validation-plan, intranet-v0-environment

# Current Progress

## Now

立项文档和隔离技术验证代码已落地。`python -m validation.run_checks` 可重复验证 V1、V2、V3、V5，并输出 V4 信息性测量。当前仍不开发产品外壳，不接入真实工作目录。

## Next

真实双机配对、TLS 同步、SMB 基线和性能门槛已完成；Intranet 中位速率 177.31 Mbps，是 SMB 的 4.44 倍。修复后的 A2/B2 双向矩阵通过双向修改、重命名零字节重传、删除、排除项和并发冲突，最终 B2 拉取仅 2 个文件、17 字节、1 次零字节重命名、1 个删除且 0 个额外冲突。结果见 `docs/evidence/dual-matrix-result.json`。

矩阵首次运行发现 serve/sync 两进程共享旧内存状态的问题，已通过扫描前重载持久化记录修复，并加入回归验证。所有测试服务均已关闭。剩余门槛为自动发现/恢复时间、双机小文件精确延迟、断网/重启双机复测和最终证据审查。

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
