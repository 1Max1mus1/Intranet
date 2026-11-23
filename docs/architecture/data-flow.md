@wiki id=intranet-data-flow type=module domain=projects state=draft
@summary Intranet 的数据从本地完整文件变化出发，经版本协调、加密分块传输和校验替换，在另一端形成文件或冲突与历史记录。
@terms Intranet, data flow, 文件校验, 原子替换
@links intranet-architecture, intranet-prd

# Data Flow

## Inputs

两台电脑的完整文件变化、删除与路径变化、用户排除规则、设备证书和受信任网络状态。

## Transformations

1. 等待文件稳定并计算内容摘要，更新本地版本元数据。
2. 在受信任网络发现已配对设备并建立加密通道。
3. 协调版本：顺序变更同步，并发修改保留冲突副本，删除留下删除记录。
4. 大文件分块续传；接收内容先进入非目标临时位置并校验。
5. 替换前保留需要的旧版本到历史区，再以原子方式安装完整文件。
6. 只有内容与状态都确认后才报告成功；中断则保留可恢复状态。

## Outputs

另一端的完整文件、删除或路径变化，以及冲突副本、历史版本、同步状态和必要通知。任何输出都不得暴露明文配对秘密。
