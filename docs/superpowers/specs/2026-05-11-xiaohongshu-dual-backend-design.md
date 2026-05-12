# 小红书双后端设计说明

## 目标

把当前“小红书存草稿自动化”改造成一个**可切换浏览器执行后端**的结构，支持：

- `playwright`
- `patchright`

同时满足下面这些约束：

- 只支持“存草稿”
- 不改正文填写流程
- 不复制两套发布逻辑
- 当你手动指定 `patchright` 时，如果运行失败，要**明确报错**
- 不允许偷偷回退到 `playwright`

## 当前状态

当前小红书自动化主要由这几个文件组成：

- [publisher.py](/D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/publisher.py:1)
- [session.py](/D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/session.py:1)
- [draft_writer.py](/D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py:1)

现在的职责大概是：

- `publisher.py`：组织整体流程
- `session.py`：负责连 BitBrowser、拿 page
- `draft_writer.py`：负责上传图片、填标题、填正文、加标签、点存草稿

需要注意的是：

- 你当前其实已经在走 `CDP`
- 也就是：现在不是“从普通 Playwright 升级到 CDP”
- 而是：**你已经在 `BitBrowser + CDP + Playwright` 这条路上**

## 问题

现在真正的问题不是“有没有 CDP”，而是：

**会话连接层和业务发布层耦合得太紧。**

导致一旦你要试 `Patchright`，就很容易碰到两个坏结果：

1. 为了换自动化引擎，连发布流程一起改乱
2. 后面即使跑通了，也很难判断到底是“页面逻辑问题”还是“反检测问题”

## 设计方向

采用“双后端可切换”的方案：

- 保留一套小红书存草稿流程
- 新增两个浏览器执行后端
- 通过配置切换后端

这不是“做两套小红书发布系统”，而是：

**同一套业务流程，下面接两种不同的浏览器执行引擎。**

## 范围边界

### 本次要做的

- 小红书浏览器后端切换
- 拆分 `playwright` / `patchright` 两个 session backend
- 增加配置项控制后端
- 补充后端选择、初始化和兼容性测试
- 在 `status / healthcheck` 里显示当前后端信息

### 本次不做的

- 不改正文生成逻辑
- 不改 selector
- 不改 humanizer 行为策略
- 不改上传逻辑
- 不做“小红书正式发布”
- 不做“Patchright 失败后自动切回 Playwright”

## 架构设计

### 保留共享业务流程

下面这两个文件仍然作为**共享业务层**：

- [publisher.py](/D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/publisher.py:1)
- [draft_writer.py](/D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py:1)

这两个文件不应该再拆成两份：

- 不要做 `playwright_publisher.py`
- 不要做 `patchright_publisher.py`

否则你等于把整条发布逻辑复制了一遍，后面维护成本会很高。

### 只拆 Session 层

当前的 [session.py](/D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/session.py:1) 要变成一个“后端选择入口”，真正的实现下沉到 backend 文件里。

建议结构：

- `xiaohongshu/session.py`
  - 只负责根据配置选择后端
- `xiaohongshu/backends/playwright_backend.py`
  - 放当前 `BitBrowser + CDP + Playwright` 的实现
- `xiaohongshu/backends/patchright_backend.py`
  - 放 `BitBrowser + CDP + Patchright` 的实现

## 后端接口

接口不要抽太大。

当前发布流程真正需要的核心能力，只有一个：

- `open_publish_page(force: bool = False) -> page`

也就是说，每个 backend 只需要负责：

- 调 BitBrowser 打开 profile
- 通过 CDP 连浏览器
- 复用已有发布页，或者新建发布页
- 返回一个可操作的 `page`

上层业务完全不关心这个 `page` 是来自：

- Playwright
- 还是 Patchright

## 为什么接口要这么小

因为现在 [draft_writer.py](/D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py:1) 已经大量使用了 Playwright 风格 API：

- `page.locator(...)`
- `page.wait_for_timeout(...)`
- `page.keyboard.press(...)`
- `set_input_files(...)`

Patchright 的定位本来就是尽量兼容 Playwright，所以大概率这层 API 可以直接复用。

如果现在你一上来就抽：

- locator
- keyboard
- click
- type
- wait

那这个项目会迅速膨胀成“浏览器框架重构”，完全没必要。

## 配置设计

新增一个配置项：

- `XHS_AUTOMATION_BACKEND`

支持值：

- `playwright`
- `patchright`

配置策略：

- 配置值合法：按它来
- 配置值缺失或非法：默认回退到 `playwright`

## 回退策略

这里必须区分两种“回退”：

### 1. 配置回退

如果你在 `.env` 里把 `XHS_AUTOMATION_BACKEND` 写错了，或者没写：

- 允许默认回退到 `playwright`

这是合理的，因为这只是配置容错。

### 2. 运行时回退

如果你明确配置了：

- `XHS_AUTOMATION_BACKEND=patchright`

但运行时 backend 初始化失败、连接失败或执行失败：

- **不允许**自动退回 `playwright`
- 必须显式报错
- 错误里要明确告诉你当前 backend 是 `patchright`

这么做的原因很重要：

你这次做 Patchright 接入，本质上是为了验证它是不是比 Playwright 更稳、更不容易被风控。

如果运行失败后系统偷偷切回 Playwright，你后面看到“成功了”，其实根本不知道成功的是谁，这样结果就没有意义。

## 状态和健康检查

小红书的 `status()` / `healthcheck()` 里应该暴露这些信息：

- 配置的 backend
- 当前激活的 backend
- 是否缺依赖
- 是否缺 BitBrowser profile id
- 是否 `draft_only`

这样你后面换窗口、换环境、切 `.env` 的时候，一眼就知道现在到底跑的是哪条线。

## 测试策略

测试不要一开始就上真浏览器。

建议分 3 层：

### 1. 后端选择测试

验证配置项会不会正确选到：

- Playwright backend
- Patchright backend

### 2. Session 后端初始化测试

用 monkeypatch 和假对象验证：

- Playwright backend 能走通 `connect_over_cdp`
- Patchright backend 也遵守同样的流程

这层不需要真浏览器。

### 3. 业务兼容性测试

验证共享的 [draft_writer.py](/D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py:1) 不依赖具体 backend 名字。

重点不是测“哪个库更强”，而是证明：

- 发布业务流程只有一套
- 不会因为双后端而分叉

## 风险说明

### 风险 1：CDP 下的行为差异

真正的技术风险，不是 `patchright` 能不能 import。

真正的风险是：

- 通过 CDP 连接后
- `browser / context / page`
- 在 Patchright 下是不是和当前 Playwright 一样稳定

### 风险 2：过度抽象

如果抽象过头，会把一个原本只需要拆 session 层的小改动，做成整套浏览器框架。

这次不应该那样做。

### 风险 3：静默回退误导判断

如果 `patchright` 失败了却偷偷切回 `playwright`，你会误以为：

- Patchright 可用
- 或者链路已经稳定

这会直接污染后续判断。

## 成功标准

这次改造成功的标准是：

- 现有 Playwright 小红书存草稿链路继续可用
- Patchright 可以通过配置切进去
- Patchright 失败时会明确报错，不会偷偷切回 Playwright
- 发布业务流程仍然只有一套
- 后面可以基于同一套流程做 A/B 对比，而不是维护两套小红书系统
