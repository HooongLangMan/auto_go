# Auto Football 项目代码地图

## 项目定位

这是一个基于 LangGraph 的足球比赛内容自动化流水线。核心目标是把“比赛抓取 -> 选场 -> 数据补全 -> 内容生成 -> 图片生成 -> 平台分发”串成一条可重复执行的流程，并把每一步的中间结果落到数据库里。

项目主实现是 Python。Node 侧当前没有运行时发布依赖；小红书发布方向已收口到后续 Playwright 适配。

## 代码主链路

一次完整运行的入口在 `src/auto_football/cli.py`：

- `doctor`：检查关键环境变量是否存在
- `init-db`：初始化数据库表
- `run --date YYYY-MM-DD`：执行完整流水线
- `preview`：从数据库读取内容并生成 HTML 预览页
- `xhs-status` / `xhs-login` / `xhs-publish-match`：单独操作小红书发布链路

真正的业务编排在 `src/auto_football/pipeline.py`，由 `AutoFootballPipeline` 构建 LangGraph：

1. `crawler`
   抓取 API-Football 和公开赛程源当天比赛，并写入缓存和原始表。
2. `selector`
   按联赛优先级、是否是头部球队、是否有时间信息等规则打分，选出默认 3 场。
3. `enrichment`
   拉取单场详情、球队数据、伤停、赔率、队徽，再融合 ClubElo / OpenFootball / StatsBomb / FBref / WhoScored 等外部知识。
4. `content`
   为微信和小红书分别生成文案；优先走 LLM，失败时回退到模板内容。
5. `image`
   基于比赛数据生成封面图和预测图。
6. `distribution`
   根据配置决定 dry-run、跳过、存草稿或真实发布。

## 目录和职责

### 源码目录

- `src/auto_football/cli.py`
  命令行入口，负责把“跑流程、预览、单平台操作”暴露出去。
- `src/auto_football/pipeline.py`
  业务主流程，系统最核心的编排文件。
- `src/auto_football/config.py`
  所有环境变量配置入口，集中管理数据库、缓存、外部 API、LLM、发布开关和图片输出目录。
- `src/auto_football/schemas.py`
  Pydantic 数据模型，约束比赛信息、生成内容、发布结果、外部知识文档等结构。
- `src/auto_football/state.py`
  LangGraph 的 `GraphState` 定义。
- `src/auto_football/clients.py`
  外部数据与 LLM 客户端封装：
  - `ApiFootballClient`：比赛、详情、积分排名、赔率、伤停
  - `PublicMatchClient`：公开赛程兜底
  - `TheSportsDBClient`：球队徽标和素材
  - `ClubEloClient`：Elo 排名
  - `OpenFootballClient`：历史比赛与近期战绩
  - `StatsBombOpenClient`：开放历史比赛补充
  - `FBrefClient`：近期赛程与基础/进阶统计补充
  - `WhoScoredClient`：赛前缺阵与预览补充
  - `ChatCompletionClient`：文案生成
- `src/auto_football/knowledge.py`
  多源知识聚合层，把外部文档合并为可直接回填到 `MatchInfo` 的上下文。
- `src/auto_football/images.py`
  用 Pillow 生成赛前/赛后图卡，支持队徽远程加载、赔率摘要和比赛结果样式切换。
- `src/auto_football/adapters.py`
  发布适配层：
  - `PublisherRegistry`：统一发布分发
  - `XiaohongshuPublisher`：Playwright 发布占位，旧小红书自动化链路已移除
  - `WechatPublisher`：调用 `wechat_oa_api_mcp`
- `src/auto_football/db.py`
  SQLAlchemy 数据访问层，负责初始化表、记录运行过程、保存内容、查询预览数据。

### 其他目录

- `scripts/`
  PowerShell 演示脚本：本地预览流程。
- `generated/`
  运行生成的图片与 HTML 预览页。
- `temp_images/`
  临时图片目录，属于运行产物。
- `node_modules/`
  当前不是业务源码；小红书旧发布依赖已从包配置中移除。

## 数据如何流动

### 输入层

- 比赛主数据：API-Football
- 赛程兜底：`688zb40`
- 队徽和素材：TheSportsDB
- 排名和强弱补充：ClubElo
- 历史赛果与近期走势：OpenFootball / StatsBomb
- 生成内容：LLM Chat Completions 接口

### 状态层

`GraphState` 在流程中传递这些核心字段：

- `fixtures`
- `selected_match_ids`
- `selection_results`
- `match_data`
- `merged_contexts`
- `contents`
- `publish_status`

### 持久化层

数据库表的职责大致如下：

- `ingestion_runs`
  每次流水线运行的主记录。
- `raw_fixtures`
  当天抓到的原始比赛数据。
- `selection_results`
  每场比赛的评分、是否被选中、选中原因。
- `source_documents`
  外部知识补充文档快照。
- `merged_contexts`
  多源知识融合后的上下文。
- `matches`
  归一化后的比赛主表。
- `contents`
  平台文案及图片关联。
- `publish_log`
  发布结果日志。

## 配置入口

项目配置几乎都来自 `.env`，样例在 `.env.example`。最重要的几类配置：

- 基础运行：`RUN_DRY`、`PUBLISH_ENABLED`、`SELECTION_COUNT`
- 数据库：`POSTGRES_*`、`DATABASE_URL`
- 缓存：`REDIS_URL`
- 比赛数据：`API_FOOTBALL_*`、`PUBLIC_FIXTURE_API_URL`
- 知识增强：`CLUBELO_ENABLED`、`OPENFOOTBALL_ENABLED`、`STATSBOMB_ENABLED`、`FBREF_ENABLED`、`WHOSCORED_ENABLED`
- 文案生成：`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`
- 平台发布：微信 / 小红书相关配置
- 图片输出：`IMAGE_OUTPUT_DIR`

## 当前仓库现状

我整理代码时确认了几个很关键的现状：

- Python 是项目主体，`package.json` 当前只保留项目工具包元信息。
- 根目录下有多个 `.db` 文件，明显属于本地运行或调试产物，不是核心源码。
- `generated/` 已经存在多份图片和预览 HTML，说明项目曾经实际跑通过生成链路。
- `scripts/*.ps1` 中写死了本机 Python 路径和一个非默认 PostgreSQL 端口，更像作者本地演示脚本，不适合直接当通用启动方式。
- 仓库里已有 `tests/` 目录，覆盖内容路由、结构化补全、内容保存和小红书发布占位行为。
- 根目录已有两份说明文档：
  - `README.md`：快速开始
  - `🧠 项目技术设计说明（足球比赛自动内容生成系统）.md`：偏设计约束和目标说明

## 建议的阅读顺序

如果后面要继续改功能，推荐按这个顺序接手：

1. `src/auto_football/config.py`
   先弄清楚有哪些开关和外部依赖。
2. `src/auto_football/cli.py`
   了解项目对外暴露了哪些命令。
3. `src/auto_football/pipeline.py`
   把主流程完整串起来。
4. `src/auto_football/db.py`
   看每一步的数据如何落库。
5. `src/auto_football/clients.py` + `knowledge.py`
   了解外部数据是怎么补进来的。
6. `src/auto_football/adapters.py` + `images.py`
   最后看输出端和发布端。

## 现在可以怎么继续

如果下一步要进入实改阶段，比较自然的切入点有三个：

- 先清理运行产物和配置，把项目启动路径统一下来
- 先补测试，优先覆盖 `selector`、`knowledge merge`、`content fallback`
- 先做功能增强，比如增加更多联赛规则、内容模板或发布平台
