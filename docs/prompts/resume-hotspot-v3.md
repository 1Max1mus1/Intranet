@wiki id=intranet-resume-hotspot-v3 type=runbook domain=projects state=draft
@summary 新一轮 128 MiB 热点断网续传的双端指令，要求显式 resumed_bytes 和最终哈希验证。
@terms Intranet, 热点测试, 断点续传, resumed_bytes
@links intranet-validation-plan, intranet-current-progress

# 热点断网续传 V3

## 前提

- 两端同时连接 `Victor‘s iPhone 15`。
- 主电脑 A：172.20.10.11，文件 `.validation-data/matrix-A2/resume-large-v3.bin`，大小 134217728 字节。
- 台式机 B 项目：`C:\Users\Victor\Desktop\Project\Intranet-Dual-TLS`。
- 代码提交：`ec2ee55` 或更新。
- 只使用合成文件，不停止其他应用，不删除验证数据。

## A 端

```powershell
python -m validation.auto_node --root .validation-data/matrix-A2 --metadata .validation-data/matrix-A2-meta --device MA2 --port 47630 --broadcast 172.20.10.15 --trusted-network
```

## 给 B 端 Agent 的 Prompt

```text
cd C:\Users\Victor\Desktop\Project\Intranet-Dual-TLS
git pull --ff-only origin main

在后台运行：
python -m validation.auto_node --root .validation-data/matrix-B2 --metadata .validation-data/matrix-B2-meta --device MB2 --port 47630 --broadcast 172.20.10.15 --watch resume-large-v3.bin --trusted-network

监视 .validation-data/matrix-B2 下与 resume-large-v3.bin 对应的 .intranet-spike-*.part。

当半成品超过 20 MiB 时：
1. 返回文件名和大小，保持节点运行。
2. 用户会关闭热点约 10 秒再打开。
3. 恢复后返回 SYNC_RETRY、最终 SYNC_RESULT、WATCH_SYNCED、最终大小和 SHA-256。
4. 不要手动 sync，不要删除文件。

最终必须满足：
- resumed_bytes > 0。
- resumed_bytes + downloaded_bytes = 134217728。
- 最终文件存在且 SHA-256 与 A 端一致。
- 不再有对应 .intranet-spike-*.part。
- 二进制 watch 文件应产生 WATCH_SYNCED，不再出现 UTF-8 错误。

如果仍为全量重传或出现锁等待，返回原始日志，不自行修改代码。
```

测试完成后停止两端节点，用户可切回正常网络。
