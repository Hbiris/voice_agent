# 语音 AI 访客登记系统

工业园区电话访客自动登记：访客来电 → Voice Agent 拟人对话采集信息 → 企业微信推送保安确认放行。

**硬指标**：接通到微信消息发出 ≤ 25 秒 · 全程拟人，不机械问答

---

## 架构图

```mermaid
flowchart LR
    Visitor(["📞 访客来电"])
    SIP["SIP Trunk\n可插拔\nTwilio / 阿里云"]
    Agent["LiveKit Agent\n对话大脑 + Tools\n语音栈可换"]
    DB[("访客数据库\nSQLite / PostgreSQL")]
    WeChat["企业微信\nWebhook 推送"]
    Guard(["👮 保安确认放行"])

    Visitor -->|"电话"| SIP
    SIP -->|"音频流"| Agent
    Agent <-->|"回访读取 / 新访写入"| DB
    Agent -->|"结构化访客信息"| WeChat
    WeChat --> Guard
```

---

## 两套配置对照

| 接缝 | `demo` | `china_landing` |
|------|--------|-----------------|
| **SIP Trunk** | LiveKit Phone Numbers 或 Twilio | 阿里云语音 SIP |
| **STT** | OpenAI Realtime API | 国内 ASR（阿里云/讯飞） |
| **LLM** | GPT-4o | Qwen / DeepSeek / GLM（OpenAI 兼容端点） |
| **TTS** | OpenAI TTS | Qwen3-TTS |
| **数据库** | SQLite | PostgreSQL |

> 切换方式：修改 `VOICE_PROFILE` 环境变量，Agent 业务逻辑零改动。

---

## 目录结构

```
src/agent/          # LiveKit worker 入口、session 组装、对话 prompt
src/telephony/      # SIP 接入：inbound 处理、dispatch、trunk 配置说明
src/voice/          # 语音栈 factory + demo / china_landing profiles
src/tools/          # function tools：visitor / wechat / guard（加功能只加文件）
src/data/           # ORM 模型、db 连接工厂、schema.sql
src/config/         # 环境变量加载、profile 选择
scripts/            # SIP trunk 配置脚本、本地启动脚本
tests/              # tools / session / telephony 测试
docs/               # 架构决策记录
```

---

## 部署步骤

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 VOICE_PROFILE 及对应 provider 密钥

# 3. 初始化数据库
# TODO: python scripts/init_db.py

# 4. 配置 SIP Trunk
# TODO: python scripts/setup_sip_trunk.py

# 5. 启动 Agent Worker
bash scripts/start_dev.sh
# 或：voice-agent
```

> **TODO**：补充 Docker Compose 一键启动、生产环境 PostgreSQL 迁移步骤、阿里云 SIP 完整配置流程。

---

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `VOICE_PROFILE` | ✅ | 语音栈配置：`demo` \| `china_landing` |
| `LIVEKIT_URL` | ✅ | LiveKit server WebSocket 地址 |
| `LIVEKIT_API_KEY` | ✅ | LiveKit API Key |
| `LIVEKIT_API_SECRET` | ✅ | LiveKit API Secret |
| `OPENAI_API_KEY` | demo | OpenAI API Key |
| `TWILIO_ACCOUNT_SID` | demo | Twilio 账号 SID |
| `TWILIO_AUTH_TOKEN` | demo | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | demo | Twilio 接入号码 |
| `ALIYUN_SIP_ACCESS_KEY` | china | 阿里云 AccessKey |
| `ALIYUN_SIP_ACCESS_SECRET` | china | 阿里云 AccessSecret |
| `ALIYUN_PHONE_NUMBER` | china | 阿里云接入号码 |
| `CHINA_LLM_BASE_URL` | china | 国内 LLM OpenAI 兼容端点 |
| `CHINA_LLM_API_KEY` | china | 国内 LLM API Key |
| `CHINA_LLM_MODEL` | china | 模型名称（如 `qwen-plus`） |
| `CHINA_ASR_APPKEY` | china | 国内 ASR AppKey |
| `CHINA_TTS_APPKEY` | china | 国内 TTS AppKey |
| `DATABASE_URL` | 可选 | 留空用 SQLite；填 PostgreSQL DSN 用于生产 |
| `WECHAT_WEBHOOK_URL` | ✅ | 企业微信 Webhook 地址 |

完整示例见 [.env.example](.env.example)。
