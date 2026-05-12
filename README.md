# Auto Football

基于 LangGraph 的足球比赛自动内容生成系统骨架，覆盖：

- 每日比赛抓取
- 3 场比赛筛选
- 数据补全与 Pydantic 校验
- 全量赛程、选场结果、原始源数据、融合上下文入库
- Redis 热缓存
- ClubElo / StatsBomb / FBref / WhoScored 多源知识补充
- 微信 / 小红书内容生成
- 自动生成对阵海报和预测图
- PostgreSQL 持久化
- 小红书内容生成与待发布队列
- 小红书 Playwright 发布适配器待接入
- 微信公众号草稿创建适配器

## 快速开始

1. 复制 `.env.example` 为 `.env`，填入你自己的配置。
2. 在 `auto_football` conda 环境安装依赖。
3. 初始化数据库表。
4. 先用 dry-run 跑通，再按平台接入真实发布。

```powershell
D:\code_app\annconda_use\envs\auto_football\python.exe -m pip install -e .
D:\code_app\annconda_use\envs\auto_football\python.exe -m auto_football.cli doctor
D:\code_app\annconda_use\envs\auto_football\python.exe -m auto_football.cli init-db
D:\code_app\annconda_use\envs\auto_football\python.exe -m auto_football.cli run --date 2026-04-22
```

## 演示脚本

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo_preview.ps1
```

## 当前默认假设

- PostgreSQL 在本机 `localhost:5432`
- 数据库名默认使用 `auto_football`
- 也支持通过 `DATABASE_URL` 临时切到 SQLite 做本地 dry-run 验证
- `688zb40` 可作为公开赛程与队徽素材补充源
- `TheSportsDB` 可作为球队 artwork 兜底源
- `ClubElo` 可作为球队 Elo 排名补充源
- `StatsBomb` 适合作为历史事件/风格补充源，默认关闭
- `FBref` 适合作为近期赛程与基础/进阶统计补充源，默认关闭；运行时建议指定浏览器路径
- `WhoScored` 适合作为赛前伤停与预览信息补充源，默认关闭；运行时建议指定浏览器路径
- 选场默认优先覆盖五大联赛；非五大联赛仅保留涉及头部豪门球队的比赛
- 发布模块先以 dry-run 为主；微信发布沿用现有公众号适配，小红书发布后续接 Playwright
- 图片模块当前会落地本地 PNG 海报，后续还可继续接 DALL·E / Flux / 即梦等服务
