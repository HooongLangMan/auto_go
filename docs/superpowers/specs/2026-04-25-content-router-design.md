# 内容路由与多模式内容入库设计

## 目标

把当前“固定赛前分析流水线”升级为“内容模式驱动流水线”，支持：

- 根据时间窗口自动判断要产出的内容类型
- 对同一场比赛生成多平台、多模式、多篇内容
- 只入库待发布，由后续发布自动化读取草稿
- 为后续接入更多图片源和 AI 生成图预留字段

## 范围

第一版聚焦四件事：

1. 增加内容路由层
2. 增加内容模式与目标账号/配额配置
3. 扩展内容存储模型，支持多条内容草稿并带状态
4. 让预览页能查看同一场比赛下的多条内容

第一版暂不做：

- 小红书发布自动化读取链路
- 即梦真实接入
- 真人赛事图专门爬取器
- 多账号独立发布适配器

## 核心设计

### 1. 内容模式

第一版支持：

- `pre_match`
- `result_flash`
- `hot_recap`

### 2. 路由策略

路由器不是按日期硬编码，而是按时间窗口与配额生成内容机会：

- 未来 6 到 30 小时的重要比赛：`pre_match`
- 完赛后 2 到 18 小时：`result_flash`
- 完赛后 12 到 48 小时：`hot_recap`

每个候选机会基于联赛权重、豪门/德比、赛果热度、时间匹配度打分，再按目标账号配额选出要生成的内容。

### 3. 数据范围

爬取范围从“只看当天比赛”扩展为：

- 前一天
- 当天
- 后一天

这样同时覆盖：

- 赛前预告
- 延迟型赛果快评
- 热点复盘

### 4. 内容存储

内容表从“每场每平台一条”扩展为“每场可存在多条内容草稿”。

新增元数据：

- 内容模式
- 目标账号
- 草稿状态
- 优先级
- 远程图片列表
- 来源链接列表

状态第一版支持：

- `drafted`
- `ready_to_publish`
- `published`
- `failed`

## 影响文件

- `src/auto_football/config.py`
- `src/auto_football/schemas.py`
- `src/auto_football/state.py`
- `src/auto_football/db.py`
- `src/auto_football/pipeline.py`
- `src/auto_football/clients.py`
- `src/auto_football/cli.py`
- `src/auto_football/images.py`
- `src/auto_football/routing.py`（新增）
- `tests/conftest.py`（新增）
- `tests/test_routing.py`（新增）
- `tests/test_db_content_storage.py`（新增）

## 验证目标

第一版完成后应能验证：

1. 路由器会在同一次运行中选出不同模式的内容任务
2. 同一场比赛能存多条不同模式/平台/账号的内容
3. 预览页能显示这些多条内容
4. 默认运行仍然可用，不要求实时发布
