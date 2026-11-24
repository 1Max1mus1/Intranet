@wiki id=intranet-current-progress type=progress domain=projects state=draft
@summary Intranet 核心双机验证和 TLS 偏移续传已落地，热点测试按用户决定暂停，仅剩真实断网与 Windows 整机重启复测。
@terms Intranet, progress, 技术验证, 暂停, 双机待测
@links intranet-overview, intranet-validation-plan, intranet-stage-1-review, intranet-tailscale-remote-transfer

# Current Progress

## Now

第一阶段核心验证已完成：真实双机配对与双向 TLS、双向同步矩阵、重命名零字节重传、删除与排除项、冲突副本、SMB 基线、性能比较、定向广播发现、小文件延迟和进程重启恢复均已取得证据。TLS 下载已接入偏移续传，本地验证第二次仅传剩余字节。

用户决定稍后继续进行热点测试，目前暂停。A/B 两端服务均已停止，主 Agent 的 TaskList 无活动任务。真实断网测试未产生完成结果，不能记为通过。

## Next

1. 用户方便时重试 512 MiB 合成文件的热点断开/恢复，检查断点偏移、自动续传和最终 SHA-256。
2. 在保存工作后重启一台 Windows 整机，检查配对、自动发现、同步与删除记录恢复。
3. 审查第一阶段证据并由用户决定是否进入第二阶段产品外壳。

第三阶段方向已记录为通过 Tailscale 提供按需“文件传输助手”，用户主动选择文件发送，不要求持续自动同步；当前不实现。

## Risks

真实断网与 Windows 整机重启仍未完成。热点全局限播不可用，第二阶段需要自动计算定向广播地址并保留静态 IP 备用。Tailscale 路径可能为 DERP，第三阶段性能不能沿用热点结果。旧 `intranet/` 原型和 `validation/` 均不是已验收产品。

## Evidence

- [第一阶段评审](stage-1-review.md)：V0/V1/V4/V5 通过，V2 核心通过，V3 部分通过。
- [双机双向矩阵](../evidence/dual-matrix-result.json)：修复后全部断言通过，最终无额外冲突。
- [性能比较](../evidence/intranet-performance-desktop.json)：Intranet 中位 177.31 Mbps，SMB 中位 39.93 Mbps。
- [自动发现与恢复](../evidence/auto-discovery-recovery.json)：发现 0.828 秒，小文件 1.099 秒，进程重启发现 1.031 秒。
- [SMB 基线](../evidence/smb-baseline-desktop.json)：三次哈希一致，临时账户、共享和凭据已清理。
- [本机回归结果](../evidence/local-results.json)：包含共享进程状态重载回归。
- 最新 TLS 续传提交：`1c33105`；本地中断后剩余字节传输验证通过，真实热点中断待重试。
