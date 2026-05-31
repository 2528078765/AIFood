# AIFood - 智能健身食谱助手 · 开发任务清单

> **项目定位**：部署在微信小程序上的 AI 健身食谱 Agent，基于 LangChain 构建单智能体架构，支持拍照识食、热量估算、每日三餐食谱推荐、健身打卡与统计。
> **技术栈**：LangChain 单智能体 + Python FastAPI + 微信小程序原生 + PostgreSQL + Redis + 阿里云 OSS
> **AI 能力**：LangChain Agent 编排工具调用（DeepSeek 推理 + Qwen-VL 食物识别 + Tavily 联网搜索 + 营养数据库查询 + 食谱推荐 + 健身记录），单智能体完成所有任务；如果后续需求膨胀到需要多个专业智能体协同时，用 LangGraph 升级

---

## 一、项目架构速览

```
AIFood/
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py            # 应用入口，挂载 Agent 及 API 路由
│   │   ├── config.py          # 配置管理（环境变量、密钥）
│   │   ├── agent/             # LangChain 智能体（核心大脑）
│   │   │   ├── __init__.py
│   │   │   ├── agent.py       # 单智能体定义（ReAct / Tool-calling Agent）
│   │   │   ├── prompts.py     # System Prompt 模板
│   │   │   └── tools/         # Agent 可调用的工具集
│   │   │       ├── __init__.py
│   │   │       ├── food_recognition.py   # 工具1：拍照识食（调 Qwen-VL，接收 image_url）
│   │   │       ├── nutrition_search.py   # 工具2：营养数据库查询
│   │   │       ├── recipe_recommend.py   # 工具3：食谱推荐
│   │   │       ├── fitness_checkin.py    # 工具4：健身打卡
│   │   │       ├── dashboard.py          # 工具5：仪表盘数据聚合
│   │   │       └── web_search.py         # 工具6：Tavily 联网搜索
│   │   ├── api/               # HTTP 路由层（微信小程序入口 + Agent 聊天接口）
│   │   │   ├── __init__.py
│   │   │   ├── auth.py        # 微信登录/鉴权
│   │   │   ├── chat.py        # Agent 对话接口（SSE 流式 + JSON 降级）
│   │   │   ├── upload.py      # 图片上传到 OSS，返回 URL
│   │   │   ├── food.py        # 食物记录查询
│   │   │   ├── recipe.py      # 食谱推荐 REST 接口
│   │   │   └── fitness.py     # 健身打卡 REST 接口
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── food_record.py
│   │   │   ├── recipe.py
│   │   │   ├── user_api_key.py
│   │   │   └── fitness.py
│   │   ├── services/          # 底层业务逻辑（被 Agent 工具和 API 共同调用）
│   │   │   ├── __init__.py
│   │   │   ├── calorie_service.py    # 热量/营养计算
│   │   │   ├── recipe_service.py     # 食谱推荐引擎
│   │   │   └── fitness_service.py    # 健身数据统计
│   │   ├── schemas/           # Pydantic 请求/响应 Schema
│   │   │   ├── __init__.py
│   │   │   ├── chat.py
│   │   │   ├── food.py
│   │   │   ├── recipe.py
│   │   │   └── fitness.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── wechat.py      # 微信 SDK 封装
│   │       ├── oss.py         # 阿里云 OSS 上传
│   │       └── nutrition_db.py # 营养数据库查询（USDA + 中国食物成分表）
│   ├── alembic/               # 数据库迁移
│   ├── scripts/
│   │   └── seed_recipes.py    # 预置食谱数据导入脚本
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── miniapp/                    # 微信小程序前端（部署到微信平台）
│   ├── app.js
│   ├── app.json
│   ├── app.wxss
│   ├── pages/
│   │   ├── index/             # 首页/仪表盘 + Agent 对话入口
│   │   ├── chat/              # Agent 对话页（类聊天界面，用户可自然语言交互）
│   │   ├── camera/            # 拍照识食（快捷入口）
│   │   ├── recipe/            # 食谱推荐
│   │   ├── recipe-detail/     # 食谱详情
│   │   ├── fitness/           # 健身打卡
│   │   ├── fitness-log/       # 健身记录
│   │   ├── profile/           # 个人中心
│   │   └── settings/          # API Key 配置页（用户自行填入 DeepSeek/Qwen/Tavily 密钥）
│   ├── components/            # 公用组件
│   │   ├── food-card/
│   │   ├── nutrition-chart/
│   │   └── calendar-picker/
│   ├── utils/
│   │   ├── api.js             # 网络请求封装
│   │   └── auth.js            # 微信登录工具
│   └── images/                # 图标/素材（从网上下载或用户自行收集）
├── assets/                     # 设计素材清单 & 下载来源
│   └── image-sources.md       # 各页面所需图片素材的下载链接 & 规格说明
├── database/
│   └── init.sql               # 初始数据库 DDL
├── Task.md                    # 本文件
└── README.md
```

---

## 二、技术栈选型（已决策，无需讨论）

| 层 | 选型 | 说明 |
|---|---|---|
| AI Agent 框架 | LangChain + langchain-core | 构建单智能体，统一编排所有 AI 工具调用；若未来需要多智能体协作则升级到 LangGraph |
| Agent 推理 LLM | DeepSeek V3 (`langchain-deepseek`) | 主推理引擎，处理对话、食谱推荐、健身建议等非视觉任务 |
| 视觉识别 LLM | Qwen-VL (DashScope 兼容模式) | 食物拍照识别，通义千问视觉模型在中文食物识别上表现优秀 |
| 联网搜索 | Tavily Search API | Agent 工具之一，搜索最新营养知识、食谱、健身资讯 |
| 后端框架 | FastAPI (Python 3.14) | 异步高性能，自动 OpenAPI 文档 |
| 数据库 | PostgreSQL 15 | 关系型，存用户/食谱/打卡数据 |
| 缓存 | Redis 7 | 微信 token 缓存、热门食谱缓存、Agent 对话历史缓存 |
| 对象存储 | 阿里云 OSS | 食物照片 & 打卡照片存储 |
| 营养数据 | USDA FoodData Central + 中国食物成分表 | 基础营养数据库，本地 JSON/SQLite 离线查询 |
| 微信 SDK | wechatpy | 微信登录、消息推送封装 |
| 前端框架 | 微信小程序原生 | 无需额外 UI 库，体积最小，部署到微信平台 |
| 部署 | Docker + 阿里云 ECS | 与 OSS 内网互通免流量 |
| 图片素材 | 网络下载 + 用户手动搜集 | 食谱图片、图标等素材来源见 `assets/image-sources.md` |

---

## 三、任务分解

### Phase 0：基础设施搭建（预计 1-2 天）

#### Task 0.1 — 初始化后端项目结构
- [ ] 创建 `backend/` 目录，按架构速览中的结构创建所有空文件和 `__init__.py`
- [ ] 编写 `backend/requirements.txt`，包含：
  - **Web 框架**：`fastapi`, `uvicorn[standard]`
  - **LangChain 全家桶**：`langchain`, `langchain-core`, `langchain-community`, `langchain-deepseek`, `langgraph`（预留多智能体升级）
  - **数据库**：`sqlalchemy[asyncio]`, `asyncpg`, `redis`, `alembic`
  - **认证 & 工具**：`python-jose[cryptography]`, `wechatpy`, `httpx`, `pydantic`, `pydantic-settings`, `python-multipart`, `oss2`（阿里云 OSS SDK）
  - **联网搜索**：`tavily-python`
- [ ] 编写 `pyproject.toml`（项目根目录），配置 ruff 和 pytest
- [ ] 编写 `.env.example`（仅开发/测试阶段使用；**正式上线后，API Key 由用户在微信小程序设置页自行输入，不存储在服务端 .env 中**）：
  ```
  # ============================================
  # 仅用于本地开发测试。正式环境用户自行配置。
  # ============================================

  # DeepSeek (开发测试用)
  DEEPSEEK_API_KEY="sk-xxx"
  DEEPSEEK_BASE_URL="https://api.deepseek.com"

  # Qwen - DashScope 兼容 OpenAI 模式 (开发测试用)
  DASHSCOPE_API_KEY="sk-xxx"
  DASHSCOPE_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"

  # Tavily (开发测试用)
  TAVILY_API_KEY="tvly-xxx"

  # 阿里云 OSS (服务端统一配置，不需用户提供)
  OSS_ACCESS_KEY_ID=xxx
  OSS_ACCESS_KEY_SECRET=xxx
  OSS_BUCKET=xxx

  # Database
  DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/aifood
  REDIS_URL=redis://localhost:6379/0

  # WeChat
  WECHAT_APPID=xxx
  WECHAT_SECRET=xxx

  # Encryption (用于加密用户 API Key)
  ENCRYPTION_KEY=xxx  # openssl rand -hex 32 生成 64 位 hex 字符串
  ```
- [ ] 编写 `backend/app/config.py`，用 `pydantic-settings` 加载全部环境变量，不写死任何密钥
  - OSS / Database / Redis / WeChat 仍然是服务端配置（从 .env 读取）
  - DeepSeek / Qwen / Tavily 在开发阶段从 .env 读取，正式环境从用户配置表动态加载

#### Task 0.2 — 数据库设计与初始化
- [ ] 编写 `database/init.sql`，定义全部表结构（见下方数据库 Schema）
- [ ] 配置 Alembic（`alembic init`），生成初始迁移脚本
- [ ] 编写 Docker Compose 一键启动 PostgreSQL + Redis 开发环境
- [ ] 编写 `backend/app/models/` 下全部 SQLAlchemy ORM 模型（与 DDL 一一对应）

#### Task 0.3 — 微信小程序脚手架
- [ ] 在微信开发者工具中创建项目（目录指向 `miniapp/`）
- [ ] 配置 `app.json`：页面路由、tabBar（首页/食谱/健身/我的）、窗口样式
- [ ] 编写 `utils/api.js`：封装 `wx.request`，自动注入 token，统一错误处理，baseURL 可配置
- [ ] 编写 `utils/auth.js`：`wx.login` → 后端换取 JWT → 存入 Storage

#### Task 0.4 — LangChain 单智能体框架搭建
- [ ] 编写 `backend/app/agent/prompts.py`：定义 System Prompt
  - 角色设定：你是一个专业的健身营养助手，能帮用户识别食物热量、推荐食谱、记录健身
  - 可用工具说明：列出所有 Tool 的名称和用途
  - 行为规范：回答简洁、数据准确、不确定时坦承并建议用户手动查询
  - 输出格式：对微信小程序友好（无 Markdown 表格，用 emoji 点缀，段落短）
- [ ] 编写 `backend/app/agent/agent.py`：用 LangChain 创建单智能体
  - 使用 `create_tool_calling_agent` + `AgentExecutor` 模式
  - 主推理模型：`ChatDeepSeek`（`model="deepseek-chat"`），配置 `max_tokens=2048`, `temperature=0.3`
  - 视觉模型：`ChatOpenAI` 指向 DashScope 兼容端点（`model="qwen-vl-max"`, `base_url` 从 env 读取），仅用于 `recognize_food` 工具
  - 加载 6 个自定义 Tool（见下方 Tool 清单）
  - 引入 `ConversationBufferWindowMemory`（窗口大小 K=10 轮，用 Redis 持久化）
  - 导出一个 `async def run_agent(user_id: str, message: str, image_url: str | None) -> AsyncIterator[AgentEvent]` 异步生成器，yield 每一步事件（thinking / tool_call / tool_result / final）
- [ ] 编写 `backend/app/api/chat.py`：Agent 对话接口（两个端点并存）
  - `POST /api/chat/stream` — **SSE 流式（推荐）**：接收 `{message, image_url?}` → 调 `run_agent` → 返回 `text/event-stream`，实时推送 thinking/tool_call/tool_result/final 事件
  - `POST /api/chat` — **JSON 降级**：接收 `{message, image_url?, image?}` → 调 Agent → 收集所有事件后返回完整 `{reply}`，image 字段仅用于小图片降级场景
  - `GET /api/chat/history?limit=20` — 获取用户最近对话历史
- [ ] 编写 `backend/app/api/upload.py`：图片上传接口
  - `POST /api/upload` — 接收 multipart 图片 → 上传到阿里云 OSS → 返回 `{image_url}`
  - 限制文件类型为 image/*，大小上限 10MB

### LangChain Agent Tool 清单（6 个工具）

每个 Tool 是一个 `@tool` 装饰的 Python 函数，由 LangChain Agent 自动决策调用时机：

| # | Tool 名称 | 功能 | 触发场景 |
|---|-----------|------|----------|
| 1 | `recognize_food` | 接收 OSS 图片 URL → 下载后调 Qwen-VL 识别食物 → 返回结构化营养数据 | 用户拍照询问食物热量 |
| 2 | `search_nutrition` | 接收食物名称关键词 → 查本地营养数据库 → 返回每 100g 营养成分 | 用户问"鸡胸肉多少卡"或需要校准 LLM 营养数据 |
| 3 | `recommend_recipe` | 接收用户 ID + 日期 + 餐次 → 从食谱库匹配推荐 | 用户说"帮我推荐今天的午餐" |
| 4 | `log_fitness` | 接收用户 ID + 运动参数 → 写入 fitness_checkins 表 | 用户说"我今天跑了30分钟" |
| 5 | `get_dashboard` | 接收用户 ID → 聚合今日热量/食谱/打卡/连续天数 | 用户说"我今天进展怎么样" |
| 6 | `search_web` | 接收搜索关键词 → 调 Tavily API → 返回搜索结果摘要 | 用户问"跑步后吃什么恢复快"等需要联网搜索的问题 |

### Agent 调用流程（一次典型的用户交互 — SSE 流式）

```
小程序端：
  1. wx.chooseMedia 拍照 → wx.uploadFile → POST /api/upload → {image_url}
  2. wx.request (enableChunked:true) → POST /api/chat/stream
       body: {"message": "这碗面多少热量？", "image_url": "https://oss.xxx/photo.jpg"}

服务端 SSE 事件流：
  event: thinking     data: {"text": "正在识别图片中的食物..."}
  event: tool_call    data: {"tool": "recognize_food", "input": {"image_url": "..."}}
  event: tool_result  data: {"tool": "recognize_food", "output": [{"name":"牛肉面","calories":550,...}]}
  event: thinking     data: {"text": "正在查询营养数据库校准..."}
  event: tool_call    data: {"tool": "search_nutrition", "input": {"keyword": "牛肉面"}}
  event: tool_result  data: {"tool": "search_nutrition", "output": {"calories_per_100g": 120}}
  event: thinking     data: {"text": "正在生成回复..."}
  event: final        data: {"reply": "这碗牛肉面大约 550 大卡，其中碳水 70g、蛋白 25g、脂肪 18g。"}

小程序端：根据事件类型逐步渲染 —— 先显示"正在识别..."，再显示识别出的食物卡片，最后显示完整回复。
```

---

### Phase 1：核心功能开发（预计 3-5 天）

#### Task 1.1 — 用户系统 & 微信登录
- [ ] **后端** `api/auth.py`：`POST /api/auth/login` 接收微信 code → 换取 openid → 创建/查询用户 → 签发 JWT
- [ ] **后端** `api/auth.py`：`GET /api/auth/profile` 获取当前用户信息（身高/体重/目标/过敏原）
- [ ] **后端** `api/auth.py`：`PUT /api/auth/profile` 更新用户身体数据与偏好
- [ ] **前端** `pages/profile/`：个人信息填写页（性别/出生日期/身高/体重/健身目标/过敏原/忌口）
- [ ] **前端** 全局：进入小程序时自动静默登录，后续请求带 JWT

#### Task 1.2 — 拍照识食 & 热量查询
- [ ] **Agent Tool** `agent/tools/food_recognition.py`：实现 `recognize_food` 工具
  - 接收 `image_url`（OSS 图片地址）→ 通过 HTTP 下载图片 → 转 base64 → 调 Qwen-VL（`model="qwen-vl-max"`，通过 DashScope 兼容 OpenAI 端点）
  - 使用 `ChatOpenAI` 指向 `DASHSCOPE_BASE_URL`，api_key 用 `DASHSCOPE_API_KEY`
  - Tool 的 description 中写清楚：传入 OSS 图片 URL，返回食物列表 JSON
  - System Prompt：严格要求模型返回 JSON，字段为 `[{name, calories_per_100g, estimated_weight_g, estimated_calories, protein_g, fat_g, carbs_g}]`
  - 对 LLM 返回做 Pydantic schema 校验，不合格则让 Agent 自动重试一次
  - 识别成功后自动写入 `food_records` 表（image_url 字段填 OSS 地址）
- [ ] **Agent Tool** `agent/tools/nutrition_search.py`：实现 `search_nutrition` 工具
  - 本地 USDA + 中国食物成分表数据，存为 JSON 文件或 SQLite 旁路
  - 支持模糊关键词匹配，返回每 100g 的营养成分
  - 用于校准 LLM 返回的营养数据（如果 LLM 数据与数据库偏差 >30%，以数据库为准）
- [ ] **Agent Tool** `agent/tools/web_search.py`：实现 `search_web` 工具
  - 调 Tavily Search API（`tavily-python` SDK），搜索营养知识、食谱、健身资讯
  - 返回格式化的搜索结果摘要（URL + 内容简介），限制 3 条结果
- [ ] **API** `api/upload.py`：`POST /api/upload` 接收图片上传 → 存 OSS → 返回 `{image_url}`
- [ ] **API** `api/food.py`：`GET /api/food/records` 查询用户历史记录（支持按日期筛选）
- [ ] **API** `api/food.py`：`GET /api/food/search?keyword=鸡胸肉` 营养数据库关键词搜索（直接查本地数据库，不经过 Agent）
- [ ] **前端** `pages/camera/`：调用 `wx.chooseMedia` 拍照/选图 → `wx.uploadFile` 上传 → 拿到 `image_url` → 跳转 chat 页发送 `POST /api/chat/stream`（带 `image_url`）→ SSE 实时展示识别过程和结果卡片
- [ ] **前端** `components/food-card/`：可复用的食物营养展示卡片（食物名/热量/蛋白/脂肪/碳水）

#### Task 1.3 — 食谱推荐引擎
- [ ] **后端** `services/recipe_service.py`：
  - 预置食谱库（至少 50 道中式家常菜），每条包含：名称、食材清单(g)、总热量、蛋白/脂肪/碳水、烹饪方式、图片 URL、适用场景（减脂/增肌/维持）
  - 推荐算法：根据用户目标（减脂/增肌/维持）计算每日目标热量 → 按 3:4:3 分配三餐 → 从食谱库匹配合适组合，确保三大营养素在目标范围内 ±10%
  - 增加多样性：同一餐的食谱在 7 天内不重复
  - 考虑过敏原和忌口自动过滤
- [ ] **后端** `api/recipe.py`：`GET /api/recipe/recommend?date=2025-01-01&meal=breakfast` 推荐指定日期指定餐次的食谱
- [ ] **后端** `api/recipe.py`：`GET /api/recipe/daily?date=2025-01-01` 返回一日三餐完整推荐
- [ ] **后端** `api/recipe.py`：`GET /api/recipe/{id}` 获取单个食谱详情
- [ ] **前端** `pages/recipe/`：展示当日三餐推荐，每餐 2-3 个候选食谱，用户可滑动选择
- [ ] **前端** `pages/recipe-detail/`：食谱详情页（食材清单、营养比例饼图、步骤说明）

#### Task 1.4 — 健身打卡 & 记录
- [ ] **后端** `api/fitness.py`：`POST /api/fitness/checkin` 提交打卡（运动类型/时长/强度/备注/可选照片）
- [ ] **后端** `api/fitness.py`：`GET /api/fitness/records?start_date=&end_date=` 查询时间段打卡记录
- [ ] **后端** `api/fitness.py`：`GET /api/fitness/stats?period=week|month` 统计周/月数据：总运动天数/总时长/各运动类型次数分布
- [ ] **后端** `api/fitness.py`：`GET /api/fitness/streak` 当前连续打卡天数
- [ ] **前端** `pages/fitness/`：打卡表单页（运动类型 picker / 时长 slider / 强度 1-10 / 备注输入）
- [ ] **前端** `pages/fitness-log/`：历史记录列表 + 日历热力图（用 `components/calendar-picker/`）
- [ ] **前端** `components/calendar-picker/`：可复用的日历组件，显示打卡热力图

---

### Phase 2：首页仪表盘 & 数据串联（预计 1-2 天）

#### Task 2.1 — 首页仪表盘
- [ ] **后端** `GET /api/dashboard`：聚合返回今日数据（已摄入热量/目标热量/推荐食谱/今日是否已打卡/连续打卡天数/本周运动统计）
- [ ] **前端** `pages/index/`：仪表盘页面
  - 顶上：今日热量摄入环形进度条（已摄入 vs 目标）
  - 中间：今日三餐推荐卡片（点击跳转食谱详情）
  - 今日健身打卡状态（已打卡打钩 / 未打卡引导跳转）
  - 连续打卡天数 badge

#### Task 2.2 — 用户 API Key 配置（关键：让用户自行输入 Key）
- [ ] **后端** `api/settings.py`：
  - `GET /api/settings/apikeys` — 获取用户已配置的 Key 列表（脱敏显示，如 `sk-c69f...8ad8`），返回每个 Key 是否已配置、是否启用
  - `PUT /api/settings/apikeys` — 保存/更新用户的 API Key，后端用 AES-256-GCM 加密后存入 `user_api_keys` 表，绝不记录到日志
  - `DELETE /api/settings/apikeys?provider=deepseek|qwen|tavily` — 删除某个 Key
- [ ] **后端** `utils/crypto.py`：实现 API Key 加解密工具
  - 加密：`encrypt_api_key(plaintext: str) -> str`，使用 AES-256-GCM，密钥从环境变量 `ENCRYPTION_KEY` 读取
  - 解密：`decrypt_api_key(ciphertext: str) -> str`，Agent 运行时动态解密后传入 LLM 客户端
- [ ] **后端** `services/api_key_service.py`：
  - `get_user_llm_config(user_id) -> dict` — Agent 调用前，优先查 `user_api_keys` 表，有则用用户的 Key；没有则 fallback 到 .env（开发测试用）
  - 正式上线后可移除 fallback 逻辑，强制用户自行配置
- [ ] **后端** 更新 `agent/agent.py`：`run_agent()` 调用前先通过 `get_user_llm_config()` 动态创建 LLM 客户端，而非在应用启动时全局单例
- [ ] **前端** `pages/settings/`：API Key 配置页
  - 三个配置区：DeepSeek（推理模型）/ Qwen 通义千问（食物识别）/ Tavily（联网搜索）
  - 每个配置区：输入框填入 API Key + Base URL（Base URL 提供默认值可留空）
  - 显示/隐藏 Key 的切换按钮
  - "测试连接"按钮，调用后端 `/api/settings/test-connection?provider=deepseek` 验证 Key 是否有效
  - 保存后返回脱敏显示的 Key 状态（绿色勾表示已配置且在有效期内）

---

### Phase 3：部署上线（预计 1 天）

#### Task 3.1 — 后端部署
- [ ] 编写 `backend/Dockerfile`（多阶段构建，python:3.14-slim → 安装依赖 → 复制代码）
- [ ] 编写 GitHub Actions 或手动部署脚本（rsync / SCP）
- [ ] 配置阿里云 ECS：Docker + Nginx 反向代理 + HTTPS 证书
- [ ] 配置 `/etc/nginx/sites-available/aifood`，反向代理 FastAPI（127.0.0.1:8000），上传大小限制 10MB，SSE 需关闭 proxy_buffering

#### Task 3.2 — 小程序发布
- [ ] 微信开发者工具 → 上传代码 → 提交审核
- [ ] 配置小程序服务器域名白名单（request 合法域名 + uploadFile 合法域名）
- [ ] 审核通过后发布上线

---

## 四、数据库 Schema

```sql
-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wechat_openid VARCHAR(128) UNIQUE NOT NULL,
    wechat_unionid VARCHAR(128),
    nickname VARCHAR(64),
    avatar_url TEXT,
    gender VARCHAR(8),             -- male, female
    birthday DATE,
    height_cm DECIMAL(5,1),
    weight_kg DECIMAL(5,1),
    fitness_goal VARCHAR(16),      -- lose_fat, build_muscle, maintain
    daily_calorie_target INT,      -- 后端计算，可手动覆盖
    allergies TEXT[],              -- {milk, peanut, seafood, egg, gluten}
    dietary_restrictions TEXT[],   -- {no_pork, no_beef, vegetarian, vegan}
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 食物识别记录表
CREATE TABLE food_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    image_url TEXT,                -- OSS 存储的图片 URL
    meal_type VARCHAR(10),         -- breakfast, lunch, dinner, snack
    foods JSONB NOT NULL,          -- [{"name":"米饭","calories":116,"protein":2.6,...}]
    total_calories INT NOT NULL,
    total_protein_g DECIMAL(6,1),
    total_fat_g DECIMAL(6,1),
    total_carbs_g DECIMAL(6,1),
    recorded_at DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 食谱表（预置数据）
CREATE TABLE recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    category VARCHAR(20),          -- chinese, western, japanese, salad, soup
    meal_type VARCHAR(10),         -- breakfast, lunch, dinner, snack
    cooking_method VARCHAR(20),    -- stir_fry, steam, boil, bake, raw
    prep_time_min INT,             -- 准备时间（分钟）
    cook_time_min INT,             -- 烹饪时间（分钟）
    difficulty VARCHAR(10),        -- easy, medium, hard
    image_url TEXT,
    ingredients JSONB NOT NULL,    -- [{"name":"鸡胸肉","amount_g":200},...]
    steps TEXT[],                  -- 烹饪步骤数组
    nutrition_per_serving JSONB,   -- {"calories":350,"protein_g":30,...}
    serving_size VARCHAR(30),      -- "1人份"
    tags TEXT[],                   -- {high_protein, low_fat, quick, meal_prep}
    suitable_goal VARCHAR(16),     -- lose_fat, build_muscle, maintain, all
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 每日食谱推荐记录表
CREATE TABLE recipe_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    recipe_id UUID REFERENCES recipes(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    meal_type VARCHAR(10) NOT NULL,
    is_accepted BOOLEAN,           -- 用户是否接受了推荐
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, date, meal_type, recipe_id)
);

-- 健身打卡表
CREATE TABLE fitness_checkins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    exercise_type VARCHAR(30) NOT NULL, -- running, swimming, weightlifting, yoga, cycling, hiit, other
    duration_min INT NOT NULL,
    intensity INT CHECK(intensity BETWEEN 1 AND 10),
    calories_burned INT,
    notes TEXT,
    image_url TEXT,                -- 可选打卡照片
    checkin_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 用户 API Key 配置表（用户自行输入，运行时动态加载）
CREATE TABLE user_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    deepseek_api_key TEXT,           -- AES-256 加密存储
    deepseek_base_url TEXT,          -- 默认 https://api.deepseek.com
    qwen_api_key TEXT,               -- DashScope API Key，AES-256 加密存储
    qwen_base_url TEXT,              -- 默认 https://dashscope.aliyuncs.com/compatible-mode/v1
    tavily_api_key TEXT,             -- AES-256 加密存储
    is_active BOOLEAN DEFAULT true,  -- 用户可暂停使用自己的 Key
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX idx_food_records_user_date ON food_records(user_id, recorded_at);
CREATE INDEX idx_recipe_recommendations_user_date ON recipe_recommendations(user_id, date);
CREATE INDEX idx_fitness_checkins_user_date ON fitness_checkins(user_id, checkin_date);
```

---

## 五、API 端点总览

### Agent 对话（核心入口）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/stream` | **（推荐）** SSE 流式对话，参数 `{message, image_url?}`，实时推送思考/工具调用/结果 |
| POST | `/api/chat` | 普通对话（降级兜底），参数 `{message, image_url?, image?}`，等待完整回复 |
| GET | `/api/chat/history?limit=20` | 获取最近对话历史 |

### 文件上传
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传图片到 OSS（multipart），返回 `{image_url}` |

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 微信登录，返回 JWT |
| GET | `/api/auth/profile` | 获取个人信息 |
| PUT | `/api/auth/profile` | 更新个人信息 |

### 食物记录
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/food/records?date=2025-01-01` | 查询某日食物记录 |
| GET | `/api/food/search?keyword=xxx` | 营养数据库搜索 |

### 食谱
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/recipe/daily?date=2025-01-01` | 获取某日三餐推荐 |
| GET | `/api/recipe/recommend?date=&meal=breakfast` | 获取单餐推荐 |
| GET | `/api/recipe/{id}` | 食谱详情 |

### 健身
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/fitness/checkin` | 提交打卡 |
| GET | `/api/fitness/records?start=&end=` | 查询打卡记录 |
| GET | `/api/fitness/stats?period=week` | 运动统计 |
| GET | `/api/fitness/streak` | 连续打卡天数 |

### 用户设置
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings/apikeys` | 获取已配置的 Key（脱敏显示） |
| PUT | `/api/settings/apikeys` | 保存/更新 API Key（AES-256 加密存储） |
| DELETE | `/api/settings/apikeys?provider=deepseek` | 删除某个 Key |
| POST | `/api/settings/test-connection?provider=deepseek` | 测试 Key 是否有效 |

### 首页
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard` | 仪表盘聚合数据 |

---

## 六、图片素材 & UI 资源

项目所需的图片素材、图标、食谱图片等资源，有两个获取渠道：

### 6.1 从网上下载（开发阶段优先使用）
由 Claude Code 开发时直接搜索并下载免费素材到对应目录：
- **食材图标**：食谱详情页的食材小图标 → unsplash.com / pixabay.com（免费商用）
- **食谱封面图**：50 道预置食谱的展示图片 → 同上
- **运动类型图标**：跑步/游泳/瑜伽等打卡图标 → iconfont.cn / flaticon.com
- **空状态插图**：无数据时的占位图 → undraw.co（可自定义配色）

### 6.2 用户自行搜集（正式上线前）
如果对素材质量不满意或需要定制风格，用户可自行搜集并放到 `miniapp/images/` 目录：
- **TabBar 图标**（5 个）：首页/食谱/健身/我的 的选中态和未选中态（80×80px PNG）
- **Logo / 启动图**：小程序启动闪屏图
- **品牌配色**：如有品牌要求，提供主色/辅色色值

### 6.3 素材规格速查表

| 素材 | 位置 | 规格 | 格式 |
|------|------|------|------|
| TabBar 图标 | `miniapp/images/tabbar/` | 80×80px，选中+未选中各一 | PNG |
| 食谱封面 | `miniapp/images/recipes/` | 750×500px（3:2） | JPG/WebP |
| 运动图标 | `miniapp/images/exercise/` | 64×64px | SVG/PNG |
| 空状态插画 | `miniapp/images/empty/` | 600×400px | SVG/PNG |
| 启动闪屏 | 小程序后台配置 | 750×1334px（建议） | PNG |

> **约定**：开发时 Claude Code 可直接从 Unsplash/Pixabay 等免费图库搜索下载，写入对应目录并在 `assets/image-sources.md` 中记录来源 URL。用户也可随时替换为自己的图片。

---

## 七、关键实现细节 & 决策记录

### 7.1 LangChain Agent 架构决策
- **单智能体 vs 多智能体**：当前业务场景（食物识别 + 食谱推荐 + 健身打卡）由一个 Agent + 6 个 Tool 即可覆盖，使用 `create_tool_calling_agent` 模式。如果后续需求膨胀到需要"营养规划师"+"运动教练"等多个专业 Agent 互相协作，则升级到 LangGraph，在 `agent/graph.py` 中定义多节点状态图
- **记忆管理**：使用 `ConversationBufferWindowMemory`（K=10 轮），通过 Redis 持久化。用户切换设备或重进小程序时，从 Redis 恢复最近 10 轮对话上下文
- **工具调用错误处理**：每个 Tool 内部 try/except，失败时返回清晰的错误描述给 Agent（而非抛出异常），让 Agent 能向用户解释具体哪一步出了问题
- **响应延迟 & 流式输出（关键）**：
  - 食物识别（Qwen-VL 2-5s）+ Agent 推理（1-3s）可能接近微信 10s 超时
  - 使用 **SSE（Server-Sent Events）** 流式推送 Agent 的每一步：`thinking → tool_call → tool_result → final_answer`
  - 小程序 `wx.request` 开启 `enableChunked: true` 接收 SSE 事件流，实时展示"正在识别食物 → 正在查询营养数据 → 正在生成建议"
  - 非流式 `/api/chat` 作为降级兜底（小程序端显示 loading 动画）
  - 两种端点共存：`POST /api/chat`（普通 JSON）和 `POST /api/chat/stream`（SSE 流式）

### 7.2 食物识别 Prompt 策略
识别准确率是关键指标。使用两步法：
1. **识别阶段**：将图片发给 Qwen-VL（DashScope 兼容端点），要求识别所有可见食物并估算分量（g），返回结构化 JSON
2. **校准阶段**：用 USDA/中国营养数据库校准 LLM 返回的营养数据，如果 LLM 返回的数据与数据库偏差 >30%，以数据库为准

### 7.3 LLM 职责分工
- **DeepSeek V3**：Agent 主推理引擎（对话理解、工具调用决策、食谱推荐、健身建议），成本低、中文能力强
- **Qwen-VL (DashScope)**：专门负责食物图片识别，通义千问视觉模型在中文场景和亚洲食物识别上表现优异
- **Tavily**：补充最新营养知识、食谱灵感、健身趋势等联网搜索能力，弥补 LLM 知识截止日期限制

### 7.4 API Key 管理策略（关键安全设计）
- **开发/测试阶段**：`.env` 中的 Key 仅用于本地开发调试，不部署到生产环境
- **正式上线后**：用户在微信小程序 `pages/settings/` 页面自行输入 DeepSeek / Qwen / Tavily 的 API Key 和 Base URL
- **存储安全**：API Key 用 AES-256-GCM 加密后存入 `user_api_keys` 表，加密密钥从环境变量 `ENCRYPTION_KEY` 读取，仅服务端持有
- **运行时加载**：Agent 每次调用前动态从数据库解密用户 Key，创建该用户专属的 LLM 客户端实例，不同用户使用各自的 Key 互不干扰
- **脱敏展示**：前端显示 Key 时只展示首尾 4 位（如 `sk-c6***8ad8`），完整 Key 永远不返回给前端
- **OSS / Database / WeChat** 仍为服务端配置（用户无需关心基础设施密钥）

### 7.5 食谱推荐的"不重复"策略
用 `recipe_recommendations` 表记录推荐历史。推荐时查询近 7 天同餐次（breakfast/lunch/dinner）已推荐的 recipe_id，从候选集中排除。候选集不足时从最久远的推荐开始循环。

### 7.6 热量目标计算
- BMR 用 Mifflin-St Jeor 公式
- TDEE = BMR × 活动系数（默认 1.375）
- 减脂：TDEE × 0.85；增肌：TDEE × 1.1；维持：TDEE
- 每餐分配：早餐 30% / 午餐 40% / 晚餐 30%

### 7.7 图片上传流程

采用"先上传、后识别"模式，避免 base64 在 JSON 中传输导致的体积膨胀（+33%）和微信小程序请求体限制：

1. 小程序 `wx.chooseMedia` → 获取临时路径
2. `wx.uploadFile` → `POST /api/upload` → 后端上传到阿里云 OSS → 返回 `{image_url}`
3. 小程序发 `POST /api/chat/stream`，body 传 `{"message": "这碗面多少热量？", "image_url": "https://oss.xxx/abc.jpg"}`
4. SSE 流推送 Agent 每一步：
   ```
   event: thinking → "正在识别食物..."
   event: tool_call → {tool: "recognize_food", args: {image_url: "..."}}
   event: tool_result → [{name: "牛肉面", calories: 550, ...}]
   event: thinking → "正在查询营养数据库校准..."
   event: final → "这碗牛肉面大约 550 大卡，碳水..."
   ```
5. Agent 最终回复渲染为聊天消息

> **降级方案**：如果 SSE 不可用（某些微信版本），`POST /api/chat` 仍支持传入 `image`（base64）作为兜底，此时小程序端显示 loading 动画等待完整回复。

---

## 八、开发约定

- **分支策略**：`master` 是主开发分支，每个 Phase 完成后打 tag
- **提交风格**：`type(scope): 描述`，如 `feat(food): add image recognition endpoint`
- **环境变量**：所有密钥/URL/配置均通过 `.env` 注入，代码中不出现硬编码
- **错误处理**：后端所有路由返回统一格式 `{"code": 0, "data": {...}, "message": "ok"}`，code 非 0 时报错
- **小程序端**：所有网络请求走 `utils/api.js` 统一封装，不直接调 `wx.request`

---

## 九、依赖服务 & 前置准备

以下密钥已在 `.env` 中配置完毕（DeepSeek / Qwen / Tavily / OSS），额外还需要准备：

| 服务 | 用途 | 获取方式 |
|------|------|----------|
| 微信小程序 AppID | 小程序身份 | 微信公众平台注册 |
| 微信小程序 AppSecret | OAuth 登录密钥 | 同上 |
| PostgreSQL 15 | 生产数据库 | 阿里云 ECS 或云数据库 |
| Redis 7 | 缓存 & Agent 记忆 | 同上 |
| 域名 + SSL 证书 | HTTPS API | 已备案域名 + 阿里云/腾讯云免费证书 |

> **已有密钥**（无需重复申请）：DeepSeek API Key、DashScope API Key、Tavily API Key、阿里云 OSS AccessKey — 均已在 `.env` 中。

---

## 十、开发启动命令（速查）

```bash
# 启动开发数据库
docker compose -f docker-compose.dev.yml up -d

# 启动后端（热重载）
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 数据库迁移
cd backend && alembic upgrade head

# 运行测试
pytest -v

# 导入预置食谱数据
python backend/scripts/seed_recipes.py
```
