# DeepSearch · 多智能体深度检索与文档生成系统

基于 **FastAPI + deepagents** 的企业级多智能体应用。系统由主智能体统一编排 **网络搜索、数据库查询、RAGFlow 知识库** 三个专业子智能体，结合 Markdown / PDF 文件生成能力，实现「检索 → 分析 → 生成文档」的一站式服务。

## 功能特性

- **多智能体编排**：主智能体协调三个专家子智能体并行/串行完成复杂任务
  - 🔍 **网络搜索助手**：基于 Tavily 检索互联网公开信息
  - 🗄️ **数据库查询助手**：直接对接 MySQL，查询企业商品/库存/销售数据
  - 📚 **RAGFlow 助手**：对接 RAGFlow 知识库，检索企业内部专有知识
- **文件生成**：Markdown 生成、Markdown→PDF 转换、上传文件内容解析（Word / Excel / PDF / MD / TXT）
- **实时进度推送**：WebSocket 定向推送工具调用、子智能体委派、最终结果等运行状态
- **会话隔离**：每个任务独立工作目录 `output/session_{id}`，上下文变量隔离多用户并发请求
- **文件管理**：上传文件自动迁移到工作目录，生成文档可在线预览与下载

## 技术栈

| 层面 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 智能体框架 | deepagents + LangChain |
| LLM | 通义千问 Qwen（OpenAI 兼容接口） |
| 向量知识库 | RAGFlow SDK |
| 网络搜索 | Tavily |
| 数据库 | MySQL（mysql-connector-python） |
| 前端 | Vue 3 + TypeScript + Vite |
| 文档处理 | python-docx / pypdf / pandas / markdown |

## 项目结构

```
DeepSearch/
├── main.py                    # 服务启动入口
├── api/
│   ├── server.py              # FastAPI 路由层（任务/上传/文件/WebSocket）
│   ├── monitor.py             # 进度上报与 WebSocket 连接管理
│   └── context.py             # 上下文变量（会话目录、线程 ID 隔离）
├── agent/
│   ├── main_agent.py          # 主智能体编排与流式执行
│   ├── llm.py                 # LLM 模型初始化
│   ├── load_prompt.py         # Prompt 配置加载
│   └── sub_agents/            # 三个子智能体
│       ├── internet_sub_agent.py
│       ├── db_sub_agent.py
│       └── rag_sub_agent.py
├── tools/                     # Agent 可用工具
│   ├── internet_search_tool.py  # 网络搜索
│   ├── mysql_tools.py           # 数据库查询
│   ├── ragflow_tools.py         # RAGFlow 提问
│   ├── markdown_tools.py        # Markdown 生成
│   ├── pdf_tools.py             # MD → PDF
│   └── upload_file_read_tool.py # 上传文件解析
├── prompt/prompts.yaml        # 主/子智能体 Prompt 配置
├── utils/                     # 日志、路径解析、文档转换工具
├── sql/company_data.sql       # 示例数据库初始化脚本
├── ui/                        # 前端（Vue 3 + Vite）
├── output/                    # 会话生成文档（运行时自动创建）
└── upload/                    # 用户上传文件（运行时自动创建）
```

## 快速开始

### 1. 环境准备

```bash
# Python >= 3.12，推荐使用 uv
uv sync
```

### 2. 配置环境变量

复制 `.env_example` 为 `.env` 并填入实际配置：

```bash
cp .env_example .env
```

```ini
# RAGFlow 配置
RAGFLOW_API_URL=http://your-ragflow-host
RAGFLOW_API_KEY=your-key

# LLM 配置（通义千问 OpenAI 兼容接口）
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=your-key
LLM_QWEN_PLUS=qwen-plus

# Tavily 搜索
TAVILY_API_KEY=your-key

# MySQL 配置
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=pharma_db
MYSQL_HOST=localhost
MYSQL_PORT=3306
```

### 3. 初始化数据库（可选）

导入 `sql/company_data.sql` 创建示例数据：

```bash
mysql -u root -p < sql/company_data.sql
```

### 4. 启动服务

```bash
python main.py
# 或
uv run python main.py
```

服务启动后：

- 后端 API：`http://localhost:8000`
- 接口文档（Swagger）：`http://localhost:8000/docs`
- 前端界面（需先启动 ui）：见下文

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/task` | 提交任务，后台异步执行 Agent，返回 `thread_id` |
| POST | `/api/upload` | 上传文件到 `upload/session_{thread_id}` |
| GET | `/api/files` | 列出指定会话目录下的生成文件 |
| GET | `/api/download` | 下载会话生成文件（仅限 output 目录内） |
| WS | `/ws/{thread_id}` | WebSocket 实时进度推送 |
| GET | `/api/health` | 健康检查 |

### WebSocket 事件类型

运行过程中服务端通过 WebSocket 推送以下事件（`event` 字段）：

| 事件 | 含义 | 示例 data |
|------|------|-----------|
| `session_created` | 会话工作目录已创建 | `{"path": "..."}` |
| `tool_start` | 工具开始执行 | `{"tool_name": "...", "args": {...}}` |
| `assistant_call` | 正在调用子智能体 | `{"assistant_name": "...", "args": {...}}` |
| `task_result` | 任务执行完成 | `{"result": "..."}` |
| `error` | 执行出错 | `{"error": "..."}` |

## 前端

```bash
cd ui
npm install
npm run dev
```

前端默认连接 `http://localhost:8000`，支持多文件上传、Markdown 渲染、生成文件侧边栏预览与下载。

## 使用示例

1. **查询数据并生成文档**：「查询数据库中的药品信息，生成一个 pdf 文件」
2. **企业内部知识问答**：「向 RAGFlow 助手询问空调安装的绝热工艺规范」
3. **公开信息检索**：「搜索最新的行业政策并整理成 Markdown」

## 说明

- `.env` 存放敏感配置，已被 `.gitignore` 排除，请勿提交到仓库。
- RAGFlow SDK 请固定使用 `0.24.0` 版本（`pyproject.toml` 中已锁定），高版本存在兼容性问题。
- 日志中的 `ModuleNotFoundError: langchain_aws / langchain_fireworks` 是 deepagents 加载可选中间件的无害提示，不影响功能。
