# WeChat OA MCP Toolkit

PyPI 包 `wechat_oa_api_mcp`（安装后自动注册 CLI `wechat_oa_api_mcp`）提供一个完整的微信公众号（Official Account）内容发布 MCP 服务。

与`微信公众号API-MCP-Server` 不同之处在于本MCP程序不需要额外连接远端调用微信公众号API服务，所有服务都在本地启动。

> **核心优势：数据安全可控** 本服务支持完全**本地化部署**，您的 AppID、AppSecret 以及所有发布的草稿内容均掌握在自己手中。所有数据交互直接发生在您的本地服务器与微信接口之间，**不经过任何第三方中转**，确保数据隐私与安全。

主要组件：

- **Server**：使用 FastMCP 暴露 `get_access_token`、`create_wechat_draft`、`publish_wechat_draft`、`del_wechat_draft`、`del_wechat_material` 五个工具。
- **Client SDK**：简单的 `WeChatMcpClient`，通过 HTTP SSE 与 MCP Server 通信，让调用方像使用本地函数一样工作。

## 使用前准备

- 访问 [https://mp.weixin.qq.com](https://mp.weixin.qq.com/) 完成公众号开发者认证，申请 AppID 与 AppSecret。
- 在“设置与开发 → 开发接口管理”中把服务器出口 IP 加入白名单（详见本页末尾“IP 白名单配置”）。
- 建议使用测试号/灰度号验证流程，避免在生产号上误发布或删除内容。

## 目录结构

```
wechat_oa_api_mcp/
├─ pyproject.toml
├─ src/wechat_oa_api_mcp/
│  ├─ core/         # 功能实现：获取 token、草稿、发布、删除
│  │  ├─ access_token.py
│  │  ├─ constants.py # 共享常量
│  │  ├─ del_draft.py
│  │  ├─ del_material.py
│  │  ├─ draft.py
│  │  ├─ publish.py
│  │  ├─ rate_limit.py
│  │  └─ utils.py     # 共享工具函数
│  ├─ client/       # WeChatMcpClient SDK
│  │  └─ sdk.py
│  ├─ server/       # FastMCP 入口，提供 CLI
│  │  └─ app.py
│  └─ config.py     # 统一的运行时配置（限流、临时目录）
└─ examples/
   └─ simple_usage.py # 安装后调用 SDK 的示例脚本
```

## 安装与运行

### 安装包

```
# 从 PyPI 安装
pip install wechat_oa_api_mcp

# 或者从本地源码安装（在代码根目录下执行）
pip install -e .
```

### 启动 MCP Server

```
wechat_oa_api_mcp --help
# 显示全部可用参数

wechat_oa_api_mcp \
  --port 8000 \
  --transport sse \
  --requests-per-minute 5 \
  --temp-dir /tmp
```

参数说明：

- `--port`：服务监听端口，默认 8000。
- `--transport`：`sse` 或 `stdio`，默认 `sse`。
- `--requests-per-minute`：每分钟允许的客户端请求次数，默认 5，`-1` 表示不限流。
- `--temp-dir`：下载临时素材文件的目录，默认 `/tmp`（下载完成后会自动删除）。
- `--debug`：开启此开关后会打印详尽的 `[DEBUG]` 日志，方便排查网络请求、素材下载等问题，默认关闭。

### 启动与调用方式

1. **CLI 启动后通过 SDK/MCP 客户端调用**
   运行上面的 `wechat_oa_api_mcp --port ...` 即可，它会把命令行参数写入 `wechat_oa_api_mcp.config` 并打印“已启动”提示。随后可用 `WeChatMcpClient`、Claude MCP、Cursor 等客户端访问。 如果想观察更详细的调试信息（例如素材下载、草稿创建的中间过程），可以加上 `--debug` 参数。

2. **在 Python 中直接创建服务器（避免命令行）**

   ```
   from wechat_oa_api_mcp.server.app import create_server
   
   server = create_server(port=9000, requests_per_minute=10, temp_dir="/tmp/wechat-mcp")
   server.run(transport="sse")
   ```

   适合需要将 MCP 服务嵌入现有进程并以代码参数化的场景。

3. **跳过 MCP 协议，直接调用 core 函数复用业务逻辑**

   ```
   from wechat_oa_api_mcp.core.access_token import get_access_token
   from wechat_oa_api_mcp.core.draft import create_wechat_draft_tool
   from wechat_oa_api_mcp.core.publish import publish_wechat_draft_tool
   from wechat_oa_api_mcp.core.del_draft import del_wechat_draft_tool
   
   token = get_access_token({"appid": "YOUR_APPID", "appsecret": "YOUR_SECRET"})
   if not token["success"]:
       raise SystemExit(token["error_msg"])
   
   draft = create_wechat_draft_tool(
       {
           "access_token": token["access_token"],
           "image_url": "https://example.com/image.jpg",
           "title": "测试文章标题",
           "content": "<p>这是文章内容</p>",
           "author": "作者",
       }
   )
   
   if draft["success"]:
       publish = publish_wechat_draft_tool(
           {"access_token": token["access_token"], "draft_media_id": draft["draft_media_id"]}
       )
       print("发布结果:", publish)
       del_wechat_draft_tool({"access_token": token["access_token"], "media_id": draft["draft_media_id"]})
   ```

#### 使用 MCP Inspector 调试

```
npx @modelcontextprotocol/inspector wechat_oa_api_mcp --port 8000 --transport sse
```

按提示访问 `http://localhost:6274`，可以列出所有工具并直接在线执行。

#### 在其他 MCP 客户端中配置（示例：Cursor）

```
{
  "mcpServers": {
    "wechat_oa_api_mcp": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

- `type`：通信协议，目前为 `sse`。
- `url`：服务器地址与端口，应与启动参数一致。
- `wechat_oa_api_mcp`：客户端中的服务名称，可自定义。

### 使用 SDK 连接服务器

```
from wechat_oa_api_mcp.client.sdk import WeChatMcpClient

client = WeChatMcpClient("http://localhost:8000")
result = client.get_access_token("your_appid", "your_appsecret")
if result["success"]:
    draft = client.create_draft(
        access_token=result["access_token"],
        image_url="https://example.com/img.png",
        title="自动化测试",
        content="<p>Hello MCP</p>"
    )
```

更多示例见 `pypi/wechat_oa_api_mcp/examples/simple_usage.py`。

## 开发说明

1. **限流 & 临时目录**：通过命令行参数注入到 `wechat_oa_api_mcp.config`，所有 tool 统一读取，触达到上限时会返回“接口调用过于频繁，已达到请求上限，请稍后再试”。
2. **下载图片**：`core/draft.py` 会校验 Content-Type、大小 10MB 以内，并在临时目录创建文件上传后删除。文件夹会在使用前 `os.makedirs(..., exist_ok=True)`。
3. **SDK**：`client/sdk.py` 在一个类中管理 SSE 连接与 tool 调用逻辑，结构精简、易阅读。
4. **打包**：采用标准 `src/` 布局，`pyproject.toml` 列出依赖（fastmcp, requests）。构建时需要 Python≥3.9 和 setuptools≥59.6。

## 技术架构

整个服务围绕 FastMCP 构建：`server/app.py` 将 core 工具注册为 MCP endpoints；core 模块使用 `requests` 调用微信 HTTPS API，并实现限流、素材下载、错误码透传等通用逻辑；`client/sdk.py` 提供一个基于 SSE 的轻量 SDK，方便外部系统像调用本地函数一样使用 MCP 工具。

## 接口一览

| 工具                   | 描述                         | 关键输入                                        |
| ---------------------- | ---------------------------- | ----------------------------------------------- |
| `get_access_token`     | 获取公众号 Access Token      | `appid`, `appsecret`                            |
| `create_wechat_draft`  | 下载封面图 → 上传 → 创建草稿 | `access_token`, `image_url`, `title`, `content` |
| `publish_wechat_draft` | 发布草稿                     | `access_token`, `draft_media_id`                |
| `del_wechat_draft`     | 删除草稿                     | `access_token`, `media_id`                      |
| `del_wechat_material`  | 删除素材（图片）             | `access_token`, `media_id`                      |

每个工具均返回统一结构 `{success, errcode, error_msg, ...}`，失败时会附带微信官方错误文档链接以便排查。

### 入参与返回详情

以下所有调用均返回 JSON，可用于 SDK、MCP 客户端或 FastMCP 工具调用。

#### `get_access_token`

- 输入
  - `appid` *(string, 必填)*：公众号 AppID。
  - `appsecret` *(string, 必填)*：公众号 AppSecret。
- 返回
  - `success` *(bool)*：获取成功为 `true`。
  - `access_token` *(string|null)*：成功时的 Access Token。
  - `errcode` *(int|null)*：微信或本地错误码，成功时为 `0`。
  - `error_msg` *(string|null)*：失败原因，包含微信错误文档链接。
- 额外说明
  - 本 MCP 会对成功获取的 Token 做本地缓存，并提前 5 分钟过期（`expires_in - 300`），以减少频繁请求微信 API 的次数。相同 `appid` 在缓存有效期内再次调用时会直接返回缓存结果，既节省请求配额，也能更快得到响应。

#### `create_wechat_draft`

- 输入
  - `access_token` *(string, 必填)*：公众号接口调用凭证。
  - `image_url` *(string, 必填)*：图文封面 URL，需公网可访问，大小 ≤10MB，支持 JPG/PNG/GIF/BMP。
  - `title` *(string, 必填)*：文章标题。
  - `content` *(string, 必填)*：图文内容，允许富文本 HTML。
  - `author` *(string, 选填)*：作者名称，默认空。
  - `digest` *(string, 选填)*：摘要，默认空。
  - `source_url` *(string, 选填)*：阅读原文链接，默认空。
  - `need_open_comment` *(int, 选填)*：是否开启评论，默认 `0` 关闭。
- 返回
  - `success` *(bool)*：草稿创建流程是否成功。
  - `draft_media_id` *(string|null)*：成功时返回的草稿 `media_id`，可用于发布。
  - `image_media_id` *(string|null)*：上传成功的图片 `media_id`，便于后续删除。
  - `errcode` *(int|null)*：微信错误码，成功时为 `0`。
  - `error_msg` *(string|null)*：失败原因，包含下载/上传/创建的详细提示。

#### `publish_wechat_draft`

- 输入
  - `access_token` *(string, 必填)*：公众号接口调用凭证。
  - `draft_media_id` *(string, 必填)*：草稿 ID，由 `create_wechat_draft` 返回。
- 返回
  - `success` *(bool)*：任务是否提交成功。
  - `publish_id` *(string|null)*：微信发布任务 ID，可用于在微信端排查。
  - `msg_data_id` *(string|null)*：发布图文的 `msg_data_id`。
  - `errcode` *(int|null)*：微信错误码，成功时为 `0`。
  - `error_msg` *(string|null)*：失败原因。

#### `del_wechat_draft`

- 输入
  - `access_token` *(string, 必填)*：公众号接口调用凭证。
  - `media_id` *(string, 必填)*：草稿 `media_id`。
- 返回
  - `success` *(bool)*：删除是否成功。
  - `errcode` *(int|null)*：微信错误码，成功时为 `0`。
  - `error_msg` *(string|null)*：失败原因。

#### `del_wechat_material`

- 输入
  - `access_token` *(string, 必填)*：公众号接口调用凭证。
  - `media_id` *(string, 必填)*：素材 `media_id`（例如封面图）。
- 返回
  - `success` *(bool)*：删除是否成功。
  - `errcode` *(int|null)*：微信错误码，成功时为 `0`。
  - `error_msg` *(string|null)*：失败原因。

## 许可证

MIT Licence

## IP 白名单配置

根据微信公众号开发接口管理规定，通过开发者ID及密码调用获取access_token接口时，需要设置访问来源IP为白名单。因此需要将部署本MCP程序的节点出口 IP（如示例 106.15.125.133），添加至微信公众号-设置与开发-开发接口管理-IP白名单，并在变更出口时及时更新；否则微信会拒绝请求。