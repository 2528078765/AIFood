# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**慧吃 (原食光助手)** — WeChat mini program AI fitness nutrition assistant. Uses LangChain + DeepSeek agent with 6 custom tools (food recognition via Qwen-VL, nutrition search, recipe recommendation, fitness check-in, dashboard, web search).

- **Frontend**: WeChat mini program in `miniapp/`, uses `wx.cloud.callContainer` for API calls (WeChat Cloud Run internal network).
- **Backend**: Python FastAPI in `backend/`, deployed as Docker container to WeChat Cloud Run. SQLite database (no PostgreSQL/Redis in production).

## Common commands

```bash
# Package backend for Cloud Run deployment
python pack.py

# Deploy to Cloud Run (after tcb login)
tcb run deploy -s aifood --path ./backend --dockerfile Dockerfile --noConfirm
```

## Critical pitfalls

### `callContainer` GET params bug
`wx.cloud.callContainer` does **not** convert `data` to query string. For GET requests, params must be manually appended to `path` (`?key=value`). The `api.js` wrapper handles this automatically — always use `api.get()` rather than calling `callContainer` directly for GET requests.

### Cloud Run container SSL
The `python:3.12-slim` base image lacks CA certificates. Two mitigations are in place:
- `Dockerfile` installs `ca-certificates` via apt-get
- `wechat.py` uses `verify=False` on the httpx client as a fallback

### WeChat API network flakiness
`code2session` calls to `api.weixin.qq.com` occasionally time out from Cloud Run. The function includes 3 retries with 1s backoff and a 10s timeout per attempt.

### New DB columns on existing databases
`Base.metadata.create_all()` only creates new tables, not new columns. When adding columns to existing models, add an `ALTER TABLE` migration in `main.py` lifespan (see `exercise_details` for the pattern). SQLite only supports adding nullable columns.

## Architecture

### Login flow
1. App launches → `restoreSession()` checks stored token/userInfo
2. If no stored session → `silentLogin()` runs: `wx.login()` gets code → `POST /api/auth/login` via callContainer → backend exchanges code for openid → creates/finds User → returns JWT
3. Profile page shows "微信一键登录" button as manual fallback when not logged in
4. 401 responses clear storage and trigger `autoLogin()`
5. **No login page exists** — the old `pages/login/` was deleted; all login is silent or via profile page button

### Agent context injection
`run_agent()` now fetches the user profile from DB and builds a **dynamic system prompt** (`_build_dynamic_prompt()`) containing: gender, age, height, weight, fitness goal, daily calorie target, body fat %, FFMI, strength level, allergies, dietary restrictions, exercise details. This means the AI always knows the user's body data without needing to call tools.

### Body fat estimation
- `body_fat.py` — Deurenberg equation baseline (BMI + age + gender), adjusted by strength-to-weight ratios parsed from free-text `exercise_details` (supports 卧推/深蹲/硬拉/推举 with kg/公斤)
- **Only calculated on profile save** (`PUT /api/auth/profile`), not on every page load
- Front-end reads `userInfo.body_fat_pct` (set by save response) — shows `--` until user saves body data with all three fields: height, weight, exercise_details
- Displayed on home page (greeting card stats row) and profile page (hero stats row) with a ⓘ button explaining the formula

### Frontend API communication
All API calls use `wx.cloud.callContainer` (env `csyaifood-d0gyq6le6214959bf`, service `aifood`) with `X-WX-SERVICE` header. Exceptions:
- **File uploads** (`wx.uploadFile`) and **SSE streaming** (`wx.request` with `enableChunked`) fall back to the public URL `https://aifood-264055-6-1409000155.sh.run.tcloudbase.com`

The `api.js` wrapper handles token injection, 401 retry with race-condition guard, and GET query-string building.

### Database
SQLite via aiosqlite. `Base.metadata.create_all()` + column migrations run in lifespan. Auto-seeds 50 recipes if `recipes` table is empty. No Redis — chat history is in-memory `defaultdict(list)` in `agent.py`.

### Backend routes
| File | Prefix | Notes |
|------|--------|-------|
| `auth.py` | `/api/auth` | login, JWT, profile CRUD; body fat calculated on PUT |
| `chat.py` | `/api/chat` | Agent SSE streaming + non-streaming |
| `recipe.py` | `/api/recipe` | `/generate` must come before `/{recipe_id}` |
| `fitness.py` | `/api/fitness` | Check-in CRUD, stats, streak |
| `food.py` | `/api/food` | Food records |
| `upload.py` | `/api/upload` | Local storage at `/app/static/uploads/` |
| `settings.py` | `/api/settings` | Per-user encrypted API keys |

### Deployment
WeChat Cloud Run: env `csyaifood-d0gyq6le6214959bf`, service `aifood`, public URL `https://aifood-264055-6-1409000155.sh.run.tcloudbase.com`, port 80. AppID: `wxdc32a7e5cbea387e`.

Publishing flow: `python pack.py` → upload `backend.zip` via Cloud Run console → WeChat DevTools upload frontend → submit for review on mp.weixin.qq.com. Experience version only works for the developer and added experience members.
