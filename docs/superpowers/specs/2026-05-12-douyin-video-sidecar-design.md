# 抖音视频 Sidecar 接入设计

日期：2026-05-12

## 一、设计目标

这份设计的目标，不是接入抖音发布，而是先验证一条链路：

`上游比赛信息 -> 抖音视频内容判断 -> 生成视频任务 -> 拿回视频结果`

当前阶段只做“测试从头到生成视频”的流程，不做：

- 抖音开放平台发布
- 抖音草稿上传
- 真实比赛高光视频剪辑
- 复用微信/小红书长文章直接做视频

这一版的重点是先验证：

1. 现有比赛数据是否足够支撑抖音视频生成
2. 传给 Pixelle 的 payload 是否合理
3. Pixelle 是否能顺利产出视频
4. 哪一步最容易卡住，或者产出效果哪里不理想

## 二、核心结论

建议采用本地 sidecar 方案，而不是把 Pixelle 直接塞进主项目环境。

也就是说：

- 主系统继续负责比赛选择、数据补全、内容模式判断
- 抖音链路自己决定这场比赛做什么视频
- Pixelle 单独启动，作为本机本地服务运行
- 主系统通过 `localhost API` 调 Pixelle
- Pixelle 只负责生成视频，不负责判断足球业务逻辑

这套方式的好处是：

- 不污染主项目环境
- 不把重依赖塞进 `auto_football`
- 抖音视频模块和主链路解耦
- 后面如果换视频生成工具，只需要换适配层

## 三、这一版做什么视频

这一版不做真实高光集锦，只做“稳定型资讯卡点视频”。

支持两种模式：

### 1. 赛前预热 `pre_match`

时长建议：

- 15 到 25 秒

内容结构建议：

1. 开场钩子卡
2. 对阵和比赛时间卡
3. 2 到 3 张稳定信息卡
4. 收尾卡

### 2. 赛果快讯 `result_flash`

时长建议：

- 15 到 25 秒

内容结构建议：

1. 最终比分卡
2. 一句话快讯卡
3. 1 到 2 张稳定信息卡
4. 收尾卡

这里强调一点：

抖音视频使用的是“共享比赛 facts”，不是“共享其他平台的文章成稿”。

也就是：

- 比赛事实层共享
- 抖音脚本和视频结构单独生成

## 四、整体架构

建议的整体结构如下：

`共享比赛事实 -> 抖音视频判断 -> 抖音视频 payload 构造 -> PixelleClient -> 查询任务结果 -> 保存视频结果`

各层职责如下：

### 1. 现有主系统

继续负责：

- 比赛抓取
- 选场
- 数据补全
- 内容模式判断
- 图片资产生成

### 2. 抖音视频模块

负责：

- 判断这场比赛要不要生成抖音视频
- 决定是 `pre_match` 还是 `result_flash`
- 把上游 facts 整理成抖音视频输入结构

### 3. Pixelle

只负责：

- 接收视频生成请求
- 渲染视频
- 返回任务状态
- 返回视频地址

Pixelle 不负责：

- 判断选哪场比赛
- 判断视频模式
- 足球内容策略
- 平台运营逻辑

### 4. 结果保存层

负责：

- 记录任务 ID
- 记录状态
- 记录视频地址
- 记录错误信息

## 五、为什么选 sidecar，而不是直接嵌进去

推荐 sidecar 的原因：

1. Pixelle 依赖重
2. 主项目当前以 Python 内容流水线为核心
3. 你现在只是想测试视频链路，不想因为视频能力把整个系统搞重
4. 后面抖音发布接口还没申请，现在没有必要把视频和发布绑在一起

不推荐两种做法：

### 1. 直接嵌进主环境

问题：

- 主环境会变重
- 依赖冲突概率更高
- 后续替换成本高

### 2. 直接上远端服务器

问题：

- 现在阶段太重
- 运维成本高
- 对“先测试链路”来说不划算

所以当前最合适的是：

- 同一台机器
- 两个进程
- 主系统调本地 Pixelle API

## 六、组件设计

### 1. DouyinVideoPlanner

作用：

- 判断某场比赛是否可以生成抖音视频

输入：

- 上游比赛 facts
- 视频模式

输出：

- `generate`
- `skip`
- `skip_reason`

规则建议：

#### `pre_match` 最少必需字段

- `home_team`
- `away_team`
- `match_time`
- `league`

#### `result_flash` 最少必需字段

- `home_team`
- `away_team`
- `home_score`
- `away_score`

其余字段如：

- 排名
- 伤停
- 赔率
- 近期战绩

都作为可选字段处理，缺了不阻塞视频生成。

### 2. DouyinVideoPayloadBuilder

作用：

- 把上游 facts 整理成 Pixelle 可用的抖音视频输入结构

输入：

- 模式
- 比赛 facts
- 已有图片资产

输出建议：

```python
DouyinVideoJobRequest(
    match_id: int,
    video_mode: Literal["pre_match", "result_flash"],
    title: str,
    caption_cards: list[str],
    facts: dict[str, object],
    assets: dict[str, object],
    duration_target_sec: int,
)
```

字段说明：

- `match_id`
  当前比赛 ID
- `video_mode`
  视频模式，赛前或赛果
- `title`
  视频标题或封面标题
- `caption_cards`
  视频中的 4 到 6 条卡点短句
- `facts`
  比赛事实信息
- `assets`
  图片、海报、队徽等素材
- `duration_target_sec`
  目标视频时长

构造规则：

- `caption_cards` 必须是短句，不是长文章段落
- 没有把握的数据不写
- 不允许编造排名、伤停、赔率
- 需要把原始 facts 压缩成适合短视频卡片的内容

### 3. PixelleClient

作用：

- 屏蔽 Pixelle 的具体 HTTP 细节

建议提供两个核心方法：

- `submit(payload) -> task_id`
- `poll(task_id) -> status, video_url, error_message`

主系统只需要知道：

- `task_id`
- `status`
- `video_url`
- `error_message`

这样以后换视频工具时，主系统其他部分基本不用动。

### 4. DouyinVideoService

作用：

- 串起 planner、payload builder、Pixelle client 和结果保存

建议方法：

- `submit(match, mode)`
- `sync(task_id)`
- `run_once(match, mode)`

它应该是测试命令和未来扩展链路的唯一入口，不要让其他地方直接到处调用 Pixelle。

## 七、数据流设计

### 当前推荐：先做测试命令流

V1 不建议直接强耦合到主 pipeline 里同步等待视频完成。

建议先做成测试命令流：

1. 本地命令选择一场比赛和一个模式
2. `DouyinVideoPlanner` 判断是否能生成
3. `DouyinVideoPayloadBuilder` 生成 Pixelle payload
4. `PixelleClient.submit()` 提交任务
5. 系统保存 `task_id` 和当前状态
6. 后续通过同步命令轮询任务结果
7. 成功后保存 `video_url`

### 未来可扩展的方式

未来如果你要把它挂到主 pipeline，可以这样接：

1. 主流程完成 enrichment 和内容模式判断
2. 抖音支线读取共享 facts
3. 提交 Pixelle 任务
4. 不阻塞主链
5. 之后用单独同步步骤拉结果

但这一版先不建议这么做，先把测试链路跑通。

## 八、结果保存设计

这一版只需要非常小的结果模型。

建议保存字段：

- `match_id`
- `video_mode`
- `provider`
- `provider_task_id`
- `status`
- `video_url`
- `error_message`
- `payload_snapshot`
- `created_at`
- `updated_at`

建议状态值：

- `queued`
- `running`
- `succeeded`
- `submit_failed`
- `render_failed`
- `timeout`
- `skipped_insufficient_data`

对于这一版来说，最终最核心的 4 个字段其实就是：

- `task_id`
- `status`
- `video_url`
- `error_message`

## 九、错误处理

原则只有一个：

**抖音视频生成失败，不能拖垮主链。**

建议规则：

1. 缺少最小必需字段
   - 标记 `skipped_insufficient_data`
2. 提交 Pixelle 失败
   - 标记 `submit_failed`
3. 查询超时
   - 标记 `timeout`
4. Pixelle 渲染失败
   - 标记 `render_failed`
5. Pixelle 返回成功但没有 `video_url`
   - 仍按失败处理

这样以后排查问题时，你可以直接看出卡在哪一层。

## 十、测试方案

当前阶段只考虑测试，不考虑抖音发布。

建议分两层测试：

### 第一层：FakePixelleClient

先做一个假的 Pixelle client，用来模拟：

- 提交成功
- 任务运行中
- 任务成功
- 任务失败

这层主要验证：

- planner 是否判断正确
- payload 是否构造正确
- 缺字段时是否合理 skip
- 状态流转是否正确

### 第二层：真实本地集成测试

再接真实本机 Pixelle sidecar，验证：

- payload 能不能被正常接收
- 任务能不能成功提交
- 能不能轮询到结果
- 最终能不能拿回 `video_url`

### 推荐测试样本

至少准备 4 类：

1. `pre_match` 完整样本
2. `pre_match` 缺少可选字段样本
3. `result_flash` 完整样本
4. `result_flash` 最小必需字段样本

### 通过标准

当前不看“爆款感”，只看链路是否稳：

- 能区分赛前和赛果模式
- 缺少可选字段时不崩
- 不编造数据
- Pixelle 成功时能拿回视频地址
- Pixelle 失败时能留下清晰错误状态
- 产出的视频结构符合资讯卡点视频预期

## 十一、本地命令建议

为了先测试链路，建议先增加本地命令，不进正式发布链。

建议命令：

- `douyin-video-submit --match-id <id> --mode pre_match|result_flash`
- `douyin-video-sync --task-id <id>`

可选增加：

- `douyin-video-run --match-id <id> --mode ...`

这个命令可以本地一次性完成：

- 提交任务
- 轮询结果
- 拿回视频地址

这样最方便你人工验片。

## 十二、当前这份设计解决什么，不解决什么

### 这份设计解决的事情

- 如何在现有系统里加一条抖音视频测试支线
- 如何不污染主环境
- 如何只共享 facts，不共享文章成稿
- 如何先验证从上游到视频生成的链路

### 这份设计暂时不解决的事情

- 抖音 API 上传
- 抖音自动发布
- 真实比赛高光视频
- 最终视频长期存储策略
- 是否要加 AI 补图

这些都不是当前验证链路的阻塞项。

## 十三、最终建议

建议按下面顺序推进：

1. 保持 Pixelle 独立运行
2. 不接抖音发布
3. 先做 `pre_match + result_flash` 的资讯卡点视频
4. 先做测试命令链路
5. 先验证从共享 facts 到 `video_url` 的完整闭环

这是当前最小、最稳、最符合你现阶段目标的方案。
