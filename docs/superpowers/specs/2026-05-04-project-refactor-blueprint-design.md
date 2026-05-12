# Auto Football 重构蓝图 v1

> 目标：在保留现有业务流水线可验证成果的前提下，拆清模块边界，建立可扩展的发布架构，为后续接入小红书 Playwright 与抖音发布能力预留统一接口。

## 1. 背景判断

当前项目的核心业务路径已经成立：

1. 抓比赛
2. 选比赛
3. 补全比赛数据
4. 生成平台内容
5. 生成配图
6. 分发到发布平台

问题不在“没有主流程”，而在“主流程与基础设施、兼容补丁、发布细节混在一起”。  
这导致系统具备可运行性，但不具备持续扩展性。

当前已经出现的典型信号：

- `pipeline.py` 同时承担流程编排、比赛构造、fallback 逻辑、内容生成策略、发布入口
- `db.py` 同时承担 ORM 模型、迁移补列、方言兼容、查询组装、预览拼装
- `adapters.py` 同时承担平台发布、正文 HTML 组装、正文插图处理、微信上传细节
- 运行时状态分散在数据库、文件系统、临时产物与平台结果之间
- 后续还要继续接入小红书与抖音，如果不先拆边界，复杂度会继续指数式上升

因此，这次不是“大重写”，而是“受控重构”：

- 不推翻现有主流程
- 不先改业务规则
- 不先追求完美抽象
- 先把职责边界拆出来
- 让系统在重构过程中始终可验证

## 2. 重构原则

### 2.1 保留主干，拆出脏逻辑

保留现有顺序流水线：

- `crawler`
- `selector`
- `enrichment`
- `content_generation`
- `image_generation`
- `distribution`

但把每一步内部混杂的逻辑逐步下沉到独立模块。

### 2.2 编排层不做业务细节

最终编排层只负责：

- 调用顺序
- 状态流转
- 错误边界
- 汇总结果

而不直接处理：

- 某个数据源的兼容逻辑
- 某个平台的发布细节
- 某种 fallback 文案策略
- 某类数据库补列与方言修复

### 2.3 平台发布必须统一接口

这是这次重构最关键的前置动作。  
因为小红书和抖音后续都会接入，如果微信、小红书、抖音继续共享一个“杂糅的发布器文件”，后续不会有清晰扩展点。

### 2.4 系统始终保持“可验证”

重构期间必须保留：

- `doctor`
- `run`
- `preview`
- 微信草稿链路

至少其中一条最小链路持续可跑。  
不能等全部拆完再验证。

## 3. 目标架构

### 3.1 目标分层

建议把项目拆成 4 层：

1. `app`
   对外入口层，只负责任务入口和组合调用

2. `domain`
   纯业务能力层，只负责“比赛如何变成内容”

3. `infra`
   基础设施层，只负责“数据从哪来、存哪去、怎么发出去”

4. `shared`
   横向共用配置、错误、工具

### 3.2 目标目录结构

```text
src/auto_football/
  app/
    cli.py
    commands/
      doctor.py
      init_db.py
      run_pipeline.py
      preview.py
      publish_match.py

  domain/
    models/
      match.py
      content.py
      publish.py
      routing.py
    services/
      fixture_selection_service.py
      match_enrichment_service.py
      content_generation_service.py
      image_generation_service.py
      distribution_service.py
    policies/
      league_priority.py
      platform_content_rules.py
      fallback_templates.py

  infra/
    db/
      models.py
      repositories.py
      migrations.py
      preview_queries.py
    cache/
      cache_store.py
    clients/
      api_football_client.py
      public_match_client.py
      football_data_client.py
      thesportsdb_client.py
      clubelo_client.py
      openfootball_client.py
      statsbomb_client.py
      fbref_client.py
      llm_client.py
    publishers/
      base.py
      registry.py
      wechat/
        publisher.py
        html_renderer.py
        media_uploader.py
      xiaohongshu/
        publisher.py
        session.py
        draft_writer.py
        selectors.py
      douyin/
        publisher.py
        draft_writer.py

  orchestration/
    pipeline.py
    state.py

  shared/
    config.py
    errors.py
    utils.py
```

注意：

- `orchestration/pipeline.py` 仍然存在，但它最后只保留状态图与编排动作
- 微信、小红书、抖音都统一挂到 `infra/publishers`
- `domain` 层不感知 SQLAlchemy、HTTP 客户端、平台接口

## 4. 模块边界定义

### 4.1 app 层

职责：

- 接命令
- 加载配置
- 调用 orchestrator / service
- 输出给终端

不负责：

- 写 SQL
- 拼平台 HTML
- 调第三方 HTTP 细节

### 4.2 orchestration 层

职责：

- 描述状态图
- 定义阶段顺序
- 在节点之间传递标准化状态

不负责：

- 复杂业务判断
- 平台策略
- 数据源补丁细节

### 4.3 domain 层

职责：

- `MatchInfo` / `GeneratedContent` / `PublishBundle` 等业务对象
- 内容路由规则
- 平台内容规则
- fallback 策略
- 资产生成策略

不负责：

- 数据库连接
- 文件系统路径兼容
- 微信 API 细节

### 4.4 infra 层

职责：

- 数据源客户端
- 数据库存储与查询
- 缓存
- 平台发布器
- 平台素材上传

不负责：

- 上层业务编排
- 跨阶段策略判断

## 5. 多平台发布接口设计

### 5.1 统一发布协议

后续微信、小红书、抖音都应当实现同一套最小接口。

建议：

```python
class Publisher(Protocol):
    platform: Platform

    def healthcheck(self) -> dict[str, object]:
        ...

    def create_draft(self, bundle: PublishBundle) -> PublishResult:
        ...

    def publish(self, bundle: PublishBundle) -> PublishResult:
        ...
```

其中：

- `healthcheck`
  用于检查平台依赖是否齐全
- `create_draft`
  用于创建草稿，不做最终发布
- `publish`
  用于最终发布

### 5.2 PublishBundle

建议增加独立发布载荷对象，而不是让平台发布器直接吃 `GeneratedContent + MatchInfo + 零散配置`。

建议：

```python
class PublishBundle(BaseModel):
    match: MatchInfo
    content: GeneratedContent
    cover_image: str | None = None
    inline_images: list[str] = []
    metadata: dict[str, object] = {}
```

这样好处是：

- 微信可以读 `cover_image + inline_images`
- 小红书可以读 `primary_media + tags`
- 抖音以后可以读 `video / cover / caption`

平台逻辑不再去数据库里自己拼上下文。

### 5.3 为小红书与抖音预留的最小边界

#### 小红书

小红书后续建议采用：

- `session.py`
  登录态 / 浏览器上下文
- `selectors.py`
  页面选择器与页面定位
- `draft_writer.py`
  上传图片、写标题、写正文、写标签、存草稿
- `publisher.py`
  实现统一 `Publisher`

#### 抖音

抖音先只预留壳：

- `publisher.py`
  先返回 `not_implemented`
- `draft_writer.py`
  未来接图文/短视频草稿写入

这样等接入时不需要再重改顶层结构。

## 6. 现有文件的去留建议

### 6.1 保留但瘦身

- `cli.py`
- `pipeline.py`
- `config.py`
- `schemas.py`
- `state.py`

这些文件不建议直接删除，但要逐步瘦身。

### 6.2 重点拆分

- `db.py`
  优先拆
- `adapters.py`
  第二优先拆
- `clients.py`
  第三优先拆
- `pipeline.py`
  在前面几层拆出后再瘦身

### 6.3 作为参考资产保留

- `shadowbot_recovery_20260428/`

不建议直接接入主代码，但它应作为：

- 小红书登录态判定参考
- 草稿写入顺序参考
- 浏览器操作细节参考

## 7. 分阶段重构方案

### 阶段 0：冻结现状

目标：

- 把现在能跑通的能力固化成回归基线

工作：

- 保持 `doctor` / `run` / `preview` / 微信草稿链路可验证
- 补 smoke tests
- 记录当前已知运行模式
- 固化一份现状架构文档

完成标准：

- 当前系统行为被测试和文档锁定

### 阶段 1：先拆发布层

目标：

- 建立统一 publisher 接口
- 微信独立成模块
- 小红书、抖音预留标准入口

工作：

- 拆 `PublisherRegistry`
- 增加 `PublishBundle`
- 微信逻辑迁移到 `infra/publishers/wechat`
- 小红书改成独立 placeholder publisher
- 抖音增加 placeholder publisher

完成标准：

- `distribution` 只依赖 registry 和统一接口
- 不再在主适配器文件里堆平台细节

### 阶段 2：拆数据库层

目标：

- 将数据库模型、迁移、查询、预览读取分开

工作：

- 拆 `models.py`
- 拆 `repositories.py`
- 拆 `preview_queries.py`
- 拆 `migrations.py`
- 逐步去除业务层中的原始 SQL 片段

完成标准：

- `db.py` 不再是巨型总入口
- 业务侧只依赖 repository 接口

### 阶段 3：瘦身 pipeline

目标：

- 让编排只剩状态流转

工作：

- 比赛构造抽到 `match_enrichment_service`
- 内容构造抽到 `content_generation_service`
- 图片构造抽到 `image_generation_service`
- 分发抽到 `distribution_service`

完成标准：

- `pipeline.py` 主要只描述节点和节点顺序

### 阶段 4：重建小红书 Playwright

目标：

- 在新架构上接回小红书草稿能力

工作：

- 登录态管理
- 草稿写入
- 图片上传
- 标签填写
- 状态回写

完成标准：

- 小红书通过统一 Publisher 接口工作

### 阶段 5：预留抖音

目标：

- 保持顶层结构已兼容抖音接入

工作：

- 增加 `douyin/publisher.py`
- 明确定义 bundle 需要的视频/封面/标题字段
- 不急着接真实实现

完成标准：

- 后续接抖音时不需要再改顶层分发架构

## 8. 风险与控制

### 风险 1：边拆边跑导致行为漂移

控制：

- 每阶段只拆一层
- 阶段结束必须跑回归测试
- 微信草稿链路保留为主回归路径

### 风险 2：拆文件太快，短期效率下降

控制：

- 不同时改业务规则
- 不同时调整平台策略
- 不同时做 UI/脚本层清理

### 风险 3：未来平台能力再次缠回主干

控制：

- 所有平台只能经由 `Publisher` 接口进入主流程
- 平台私有逻辑不得回流到 pipeline / cli / db 层

## 9. 本轮蓝图的结论

这次重构不应理解为“换一版代码”，而应理解为：

- 保留现有业务主流程
- 拆掉长期压在主流程上的杂质
- 建立统一平台发布边界
- 为小红书和抖音扩展提前留好接口

推荐执行顺序：

1. 先做阶段 0
2. 再做阶段 1
3. 再做阶段 2
4. 再做阶段 3
5. 最后进入小红书和抖音接入

也就是说：

**先让架构能承载扩展，再去做平台扩展本身。**
