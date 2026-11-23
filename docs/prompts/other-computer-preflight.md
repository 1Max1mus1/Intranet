@wiki id=intranet-other-computer-preflight type=runbook domain=projects state=draft
@summary 给另一台 Windows 电脑 Agent 的完整隔离预验证 Prompt，包含仓库地址、代码前提、环境、命令、证据格式和安全边界。
@terms Intranet, Agent Prompt, 双机验证, V0, GitHub
@links intranet-validation-plan, intranet-v0-environment

# 另一台电脑 Agent 预验证 Prompt

将以下代码块完整交给另一台电脑的 Agent：

```text
你正在用户的另一台 Windows 电脑上协助 Intranet 做 V0 环境登记和本机隔离预验证。另一台电脑由主 Agent 操作，你只负责当前这台电脑。不要开始双机连接。

一、项目身份与代码来源

项目：Intranet
用途：两台个人 Windows 电脑之间的局域网双向文件同步，目前只做技术验证，不是已完成产品。
GitHub：https://github.com/1Max1mus1/Intranet.git
默认分支：main
主 Agent 的本机路径：C:\Users\Victo\Desktop\Project\Intranet
用户的 Wiki：https://github.com/1Max1mus1/Victor-llm-wiki.git
主 Agent 的 Wiki 路径：C:\Users\Victo\Desktop\Project\Victor-llm-wiki

重要：GitHub main 的初始提交
4b87fcc489edfbb56447c1cc73ae7bd77a183338 只有 README，不能用于验证。
主 Agent 已将当前完整进度推送到 main。请获取 main 的最新提交，不要使用上述初始提交。

在准备存放项目的位置执行：
git clone https://github.com/1Max1mus1/Intranet.git
cd Intranet
git log -1 --format="%H%n%ci%n%s"

如果目录已经存在，则在 Intranet 目录执行：
git fetch origin
git status --short --branch
git log -1 --format="%H%n%ci%n%s"

如果工作树有本地修改，不要 reset、清理或覆盖，停止并报告。
克隆或更新后必须检查下述文件；缺失时执行 git pull --ff-only origin main 后再检查一次。
仍缺失则停止并报告实际 commit，不要从其他来源下载代码，不要重新实现验证脚本，不要 commit 或 push。

二、必须存在的文件

进入用户提供的 Intranet 目录，确认以下文件存在：
- AGENTS.md
- PROJECT.md
- CONTEXT.md
- docs/validation.md
- validation/__init__.py
- validation/engine.py
- validation/transport.py
- validation/security.py
- validation/corpus.py
- validation/run_checks.py
- validation/requirements.txt

如果缺少任何一个，停止并报告“缺少当前验证代码：<具体路径>”。

三、阅读与限制

先阅读 AGENTS.md、PROJECT.md、CONTEXT.md 和 docs/validation.md。

只允许：
- 登记当前电脑环境。
- 安装 validation/requirements.txt 中的验证依赖。
- 在项目内生成隔离测试数据。
- 运行已有的本机验证。
- 输出原始结果。

禁止：
- 不开发产品或修改同步算法。
- 不启动旧 intranet/ 产品原型。
- 不访问、复制、删除或同步 Desktop、Documents、真实代码项目等目录。
- 不连接另一台电脑，不创建 SMB 共享，不修改防火墙、路由器、VPN 或网络配置。
- 不创建或暴露真实凭据，不输出密码、配对码、私钥、BSSID 或真实文件内容。
- 不自行修复失败。出现失败时保留完整错误并报告。

四、环境要求

目标系统：Windows 10/11 x64。
推荐 Python：3.13.2；最低支持 3.10。
验证依赖见 validation/requirements.txt，当前为 cryptography>=48,<49。
默认测试语料约 128 MiB、206 个文件，只包含合成数据。
确保项目所在磁盘至少有 2 GiB 可用空间，避免测试期间磁盘写满。

五、需要登记的环境信息

使用系统自带工具或 Python 获取并报告：
1. 计算机名、Windows 版本和 build、系统架构。
2. CPU 型号、逻辑处理器数、内存容量。
3. 物理硬盘型号、系统盘总容量与剩余容量。
4. Python 的完整路径和版本。
5. 当前物理网络适配器、无线或有线、链路速率。
6. 当前 WLAN SSID；有线连接则注明“有线”。
7. 当前局域网 IPv4、默认网关和接口名称。
8. 是否存在 Tailscale、VPN、虚拟机或其他虚拟网络接口。
9. 当前是否连接 CUHK1x 或其他可能具有设备隔离的校园/企业网络；只记录事实，不自行修改网络。

主电脑当前参考环境：
- Windows 11 10.0.26300，Intel Core Ultra 9 285H，31.4 GiB 内存，NVMe。
- Python 3.13.2。
- 当前 SSID 为 CUHK1x，WLAN 链路约 1.2 Gbps。
- 主电脑当前测试 IP 为 10.13.176.36；网络变化后可能失效。
这些信息只用于后续协调，本阶段不要连接该地址。

六、执行命令

在已确认完整的 Intranet 项目根目录依次运行：

python --version
python -m pip install -r validation/requirements.txt
python -m validation.corpus --root .validation-data/corpus
python -m validation.run_checks

路径边界：
- corpus 只能写入项目内的 .validation-data/corpus。
- run_checks 只能操作项目内的 .validation-data、docs/evidence/local-results.json 和隔离临时目录。
- 如果命令、配置或路径指向项目外的真实工作目录，停止并报告。
- 不要以管理员权限运行，除非用户另行明确授权；本预验证不需要管理员权限。

七、预期结果与判定

V1、V2、V3、V5 应为 pass。
V4 应为 informational，不得把本机性能数字标记为双机验收通过。
如果出现 failed、异常或命令失败，原样返回错误，不修改代码。

各项含义：
- V1：新增、修改、删除、重命名、排除项和删除记录。
- V2：并发冲突、冲突副本、历史恢复和清理。
- V3：回环 TCP 分块续传、中断恢复和损坏校验。
- V4：本机信息性性能测量，不是 SMB 或双机结果。
- V5：配对码、设备证书、未知网络策略和 TLS 双向认证。

八、最终返回格式

请按以下结构返回，不要只回复“成功”：

1. 项目路径与代码检查
   - 实际 Intranet 路径。
   - 所有必需文件是否齐全。
   - 代码来自用户复制的完整目录还是 GitHub；如果是 Git，给出 commit。

2. 本机环境
   - 上述第五节的全部信息。

3. 执行命令
   - 实际运行的命令及是否成功。

4. 完整验证输出
   - 原样附上 validation.run_checks 的完整 JSON。
   - 分别列出 V1/V2/V3/V4/V5 的状态。

5. 文件变更
   - 列出实际生成或修改的项目文件。
   - 通常只应涉及 .validation-data 和 docs/evidence/local-results.json。
   - 说明是否安装过 Python 依赖。

6. 网络摘要
   - IP、SSID、链路速率、默认网关和虚拟接口。
   - 不输出 BSSID 或任何秘密。

7. 最终声明
   - “本机隔离预验证已完成/未完成。”
   - “双机联测、SMB 基线和真实局域网性能验收尚未执行。”

完成后停止，等待用户把结果交给主 Agent。不要自行发起双机连接或进入第二阶段。
```

## 返回后的核对

另一台 Agent 返回后，需要与本机 `docs/evidence/local-results.json` 对照 Python 和验证代码版本，再协调双方同时在线的双机测试。预验证通过不代表双机验收通过。
