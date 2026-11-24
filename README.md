# Intranet

Intranet 是面向两台个人 Windows 电脑的局域网双向文件同步工具。两台设备配对后，在受信任网络中自动同步指定目录，文件不经过云端存储。

## 已实现

- 一次性配对码、设备证书和双向 TLS。
- 新增、修改、删除、重命名、排除项和并发冲突副本。
- 大文件分块、内容校验和断点续传。
- 历史文件恢复、30 天/20 GB 默认清理策略。
- 自动发现、静态设备地址、暂停与恢复。
- 苹果简约风主界面（浅灰背景、白色卡片、侧栏导航）、系统托盘、Windows 登录自启动。
- 当前用户安装、卸载和安装后启动的 Windows 安装包。

## 安装与首次使用

安装包位于：

```text
dist/installer/IntranetSetup.exe
```

安装只需当前用户权限，不需要管理员账户。两台电脑分别执行：

1. 安装并启动 Intranet，选择同一组需要同步的本地目录。
2. 一台在“设备配对”中选择“生成配对码并等待”，另一台输入其 `IP:端口` 和配对码。
3. 回到“同步”，点击“信任此网络”和“启动同步”。
4. 关闭主窗口会隐藏到托盘；可在托盘暂停、恢复、打开目录或退出。

默认不会自动选择或同步任何目录。不要直接指向需要保留唯一副本的目录，首次使用建议先用测试目录熟悉删除和冲突规则。

## 从源码运行

```powershell
python -m pip install -r requirements.txt
python main.py
```

后台启动：

```powershell
python main.py --background
```

## 验证与构建

```powershell
python -m validation.run_checks
python -m validation.product_smoke --gui
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

`build.ps1` 使用 PyInstaller 和 Inno Setup，生成 `dist/Intranet/Intranet.exe` 与 `dist/installer/IntranetSetup.exe`。

## 文档

- [项目概览](PROJECT.md)
- [产品需求](docs/prd.md)
- [技术验证计划](docs/validation.md)
- [路线图](docs/roadmap.md)
- [当前进度](docs/progress/current.md)
- [统一领域语言](CONTEXT.md)

第三阶段计划通过 Tailscale 提供按需“文件传输助手”，与当前持续目录同步模式独立。
