# 慧吃（原食光助手）

AI 健身营养助手微信小程序。支持食物拍照识别、营养成分查询、智能食谱推荐、健身打卡和数据看板。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | 微信小程序 |
| 后端 | Python FastAPI |
| AI | LangChain + DeepSeek Agent（6 个自定义工具） |
| 视觉 | Qwen-VL（食物识别） |
| 数据库 | SQLite + aiosqlite |
| 部署 | 微信云托管（Docker 容器） |

## 项目结构

```
├── miniapp/              # 微信小程序前端
│   ├── pages/            # 页面（首页/聊天/食谱/健身/我的/设置）
│   └── utils/            # api.js（请求封装）、auth.js（登录）
├── backend/              # FastAPI 后端
│   └── app/
│       ├── agent/        # LangChain Agent + 6 个 tools
│       │   └── tools/    # 食物识别/营养搜索/食谱推荐/健身打卡/看板/联网搜索
│       ├── api/          # 路由（auth/chat/fitness/food/recipe/upload/settings）
│       ├── models/       # SQLAlchemy 模型
│       ├── schemas/      # Pydantic 校验
│       ├── services/     # 业务逻辑
│       └── utils/        # 工具函数（加密/微信/安全）
├── database/             # SQL 初始化脚本
├── Dockerfile            # 云托管容器构建
└── docker-compose.yml    # 本地开发环境
```

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 前端

用微信开发者工具打开 `miniapp/` 目录。

### Docker 本地开发

```bash
docker-compose -f docker-compose.dev.yml up
```

## 环境变量

复制 `.env.example` 为 `.env` 并填写：

| 变量 | 说明 |
|---|---|
| `WECHAT_APPID` | 微信小程序 AppID |
| `WECHAT_SECRET` | 微信小程序 AppSecret |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `QWEN_API_KEY` | Qwen-VL API 密钥（食物识别） |
| `JWT_SECRET` | JWT 签名密钥 |

## 部署

```bash
python pack.py                          # 打包后端
tcb run deploy -s aifood --path ./backend --dockerfile Dockerfile --noConfirm
```

## License

MIT
