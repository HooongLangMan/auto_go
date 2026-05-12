# Stage 0 Baseline Runtime Snapshot

> 目的：冻结当前系统“已知可运行能力”和“已知运行约束”，作为后续重构阶段的回归参照。

## 1. 当前已验证的可运行入口

### 1.1 CLI 命令

当前 CLI 对外入口位于：

- `src/auto_football/cli.py`

已知有效命令：

- `doctor`
- `init-db`
- `run --date YYYY-MM-DD`
- `preview --limit N`
- `xhs-status`
- `xhs-login`
- `xhs-browser`
- `xhs-publish-match`

其中：

- 微信链路当前通过 `run` 进入 `distribution -> WechatPublisher`
- 小红书命令目前仍然是占位 / 调试入口，不构成完整发布能力

## 2. 当前已验证的关键运行模式

### 2.1 本地 dry-run 模式

适用场景：

- 验证抓取
- 验证选场
- 验证内容生成
- 验证图片生成
- 验证数据库落库
- 验证 preview 输出

典型开关：

- `RUN_DRY=true`
- `PUBLISH_ENABLED=false`
- `DATABASE_URL=sqlite:///...`

### 2.2 微信草稿模式

适用场景：

- 真正写入微信公众号草稿箱

关键开关：

- `RUN_DRY=false`
- `PUBLISH_ENABLED=true`
- `WECHAT_PUBLISH_ENABLED=true`
- `WECHAT_AUTO_PUBLISH=false`

关键前提：

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- 微信白名单 IP 生效
- 匹配到可用封面图 URL

### 2.3 Preview 模式

适用场景：

- 查看数据库中已生成内容的最终展示结果

入口：

- `preview --limit N`

输出位置：

- `generated/previews/latest_preview.html`
- `generated/previews/match_<id>.html`

## 3. 当前已冻结的最小回归事实

### 3.1 单元 / 集成回归

当前测试集合已经覆盖：

- CLI 可启动性
- 微信配置诊断
- 微信正文插图 HTML 逻辑
- 微信正文图片上传 URL 逻辑
- 小红书占位行为
- 路由规则
- 结构化补全
- 数据库存储与迁移
- TheSportsDB 队名别名兜底

### 3.2 Stage 0 Smoke Baseline

新增 baseline 测试：

- `tests/test_stage0_smoke_baseline.py`

该测试冻结的事实：

- pipeline 能完成 `run`
- `crawler -> selector -> enrichment -> content -> image -> distribution` 能在隔离 SQLite 中走通
- `contents` 能成功落库
- `preview payload` 能正常读取

## 4. 当前外部依赖状态

### 4.1 已用到的主要外部源

- `API-Football`
- `688zb40 public fixture`
- `TheSportsDB`
- `ClubElo`
- `football-data.org`
- `OpenFootball`
- `StatsBomb`
- `FBref`
- `LLM Chat Completions`
- `wechat_oa_api_mcp`

### 4.2 当前真实运行的高风险依赖

- 微信公众号白名单 IP
- 本地生成图片是否还存在
- 数据库方言差异（SQLite / PostgreSQL）
- 外部源字段完整性

## 5. 当前已知约束 / 已知坑

### 5.1 数据库层

- `db.py` 同时承担模型、迁移、查询、预览拼装
- 老 SQLite 库曾出现 `::json` 方言不兼容
- 运行中容易出现“数据库记录还在，但磁盘图片文件已缺失”

### 5.2 微信发布层

- 封面图依赖 `competition_logo_url / home_logo_url / away_logo_url`
- 正文插图依赖本地生成图片文件存在
- 微信白名单 IP 可能波动，不是单一固定出口

### 5.3 小红书层

- 目前只是占位 publisher
- 真正可复用逻辑主要留在 `shadowbot_recovery_20260428`

## 6. 当前重构阶段的硬约束

在进入结构重构时，以下能力必须尽量保持：

- `doctor` 可运行
- `run` 可运行
- `preview` 可运行
- 微信草稿链路可验证
- `tests/test_stage0_smoke_baseline.py` 通过

## 7. Stage 0 结论

当前系统虽然结构混乱，但已经具备：

- 可验证的主流水线
- 可验证的数据库落库能力
- 可验证的微信草稿能力
- 可验证的最小 smoke baseline

因此后续重构可以在“有基线保护”的前提下开展，而不是盲拆。
