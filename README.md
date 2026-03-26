# Customer Support Agent MVP

一个最小可运行的智能客服 MVP，包含：

- 知识库文档录入与全文检索
- 会话创建与消息收发
- 基于知识库的客服回答
- 可选 OpenAI 增强回答

## 微信客服最小测试模块

新增了一个最小化的企业微信客服测试服务，覆盖：

- 创建客服帐号
- 接收并解密微信客服回调
- 使用 `sync_msg` 拉取消息
- 发送文本消息

微信通信代码已集中到：

- `app/src/wecom/client.py`
- `app/src/wecom/demo_app.py`

启动方式：

```bash
source .venv/bin/activate
pip install -r requirements.txt
./scripts/run_wecom_kf_demo.sh
```

默认监听 `http://127.0.0.1:8010`。

需要配置的环境变量：

```bash
export WECOM_CORP_ID=wwxxxx
export WECOM_KF_SECRET=xxxx
export WECOM_CALLBACK_TOKEN=xxxx
export WECOM_CALLBACK_AES_KEY=xxxx
export WECOM_CALLBACK_RECEIVE_ID=wwxxxx
export WECOM_AUTO_REPLY_ENABLED=true
```

最常用的测试接口：

```bash
# 1. 创建客服帐号
curl -X POST http://127.0.0.1:8010/wecom/kf/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试客服",
    "media_id": "MEDIA_ID"
  }'

# 2. 查看最近收到的回调
curl http://127.0.0.1:8010/wecom/kf/callbacks

# 3. 用回调里拿到的 token/open_kfid 主动拉消息
curl -X POST http://127.0.0.1:8010/wecom/kf/messages/sync-latest

# 4. 发送文本消息
curl -X POST http://127.0.0.1:8010/wecom/kf/messages/send-text \
  -H "Content-Type: application/json" \
  -d '{
    "touser": "EXTERNAL_USERID",
    "open_kfid": "OPEN_KFID",
    "content": "你好，这是一条测试消息"
  }'

# 5. 用最近一次回调自动拉消息并回复
curl -X POST http://127.0.0.1:8010/wecom/kf/messages/auto-reply-latest
```

自动回复说明：

- 当 `WECOM_AUTO_REPLY_ENABLED=true` 时，收到 `POST /wecom/kf/callback` 的 `kf_msg_or_event` 回调后，服务会自动调用 `sync_msg`
- 仅处理未处理过的文本消息，按 `msgid` 做内存去重
- 收到的文本会进入现有 LangGraph 智能体，再通过 `send_msg` 回发给客户
- 当前版本不会处理图片、语音等非文本消息

## Django 与微信云托管

当前项目已经整合到微信云托管 Django 模板，主要入口在：

- `manage.py`
- `wxcloudrun/settings.py`
- `wxcloudrun/urls.py`
- `wxcloudrun/views.py`

云托管部署时会使用：

- `Dockerfile`
- `container.config.json`
- `scripts/start_wxcloudrun.sh`

其中启动脚本会先执行 `python manage.py migrate --noinput`，再启动 Django 服务。

### 本地启动 Django

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8020
```

常用接口：

```bash
curl http://127.0.0.1:8020/health

curl -X POST http://127.0.0.1:8020/api/agent/answer \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "demo",
    "content": "25考情汇总"
  }'
```

### 微信云托管部署说明

1. 把代码仓库连接到微信云托管服务。
2. 使用项目根目录下的 `Dockerfile` 构建镜像。
3. 服务端口配置为 `80`。
4. 在云托管控制台补齐环境变量，示例可直接参考项目根目录 `.env.example`。

建议必填项：

```bash
DJANGO_SECRET_KEY=替换成一段随机字符串
DJANGO_DEBUG=false

MYSQL_ADDRESS=云托管MySQL地址:端口
MYSQL_USERNAME=云托管MySQL用户名
MYSQL_PASSWORD=云托管MySQL密码
MYSQL_DATABASE=agent_kf

WECOM_CORP_ID=企业ID
WECOM_KF_SECRET=微信客服Secret
WECOM_CALLBACK_TOKEN=回调Token
WECOM_CALLBACK_AES_KEY=回调EncodingAESKey
WECOM_CALLBACK_RECEIVE_ID=企业ID
WECOM_AUTO_REPLY_ENABLED=true
```

变量来源：

- `DJANGO_SECRET_KEY`
  自己生成一段随机字符串即可
- `MYSQL_*`
  来自微信云托管控制台里的 MySQL 实例
- `WECOM_CORP_ID`
  企业微信企业 ID
- `WECOM_KF_SECRET`
  企业微信客服 API 的 Secret
- `WECOM_CALLBACK_TOKEN`
  企业微信回调配置页里自定义填写
- `WECOM_CALLBACK_AES_KEY`
  企业微信回调配置页里生成的 43 位密钥
- `WECOM_CALLBACK_RECEIVE_ID`
  通常直接填企业 ID

部署后建议按这个顺序验收：

1. `GET /health`
2. `POST /api/agent/answer`
3. `GET /wecom/kf/callback` 回调地址校验
4. 企业微信实际发一条消息，验证自动回复

## 原 FastAPI 本地调试方式

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

服务默认监听 `http://127.0.0.1:8000`。

## 环境变量

可选配置：

```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4.1-mini
export OPENAI_BASE_URL=https://api.openai.com/v1
export APP_DB_PATH=./data/support_agent.db
export APP_TOP_K=4
```

如果未配置 `OPENAI_API_KEY`，系统会退化为“基于知识片段拼接”的本地回答模式，方便先验证接口与流程。

如果使用 Qwen 的 OpenAI 兼容接口，可设置为：

```bash
export OPENAI_API_KEY=你的百炼Key
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export OPENAI_MODEL=qwen-plus
```

## API

### 1. 创建会话

```bash
curl -X POST http://127.0.0.1:8000/conversations
```

### 2. 写入知识库

```bash
curl -X POST http://127.0.0.1:8000/kb/documents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "退款规则",
    "source": "help-center/refund",
    "content": "用户在支付后7天内可以申请退款，虚拟商品一经发货不支持退款。"
  }'
```

### 3. 发送消息

```bash
curl -X POST http://127.0.0.1:8000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "替换成上一步返回的ID",
    "content": "订单付款之后多久可以退款？"
  }'
```

### 4. 拉取消息

```bash
curl http://127.0.0.1:8000/messages/替换成会话ID
```

### 5. 搜索知识库

```bash
curl "http://127.0.0.1:8000/kb/search?q=退款"
```

## 设计说明

- 数据存储：SQLite
- 检索：SQLite FTS5 + bm25 排序
- 并发：FastAPI 异步接口，单机 MVP 可支撑一定并发
- 系统提示词：`app/prompts/role_prompt.md`
- LangGraph 服务入口：`app/src/langgraph_service.py`
- 回复策略：
  - 优先检索知识库
  - 有 OpenAI Key 时调用模型生成回复
  - 无 Key 时返回本地规则化回答

## 下一步可扩展

- 接入向量库与 embedding 检索
- 加入 Redis 会话缓存
- 增加人工转接与工单系统
- 做消息流式输出
- 接入企业微信、飞书、WebSocket
