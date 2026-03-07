# Repo Wiki (AI Quick Onboarding)

代码结构规范以 `docs/code-structure.md` 为唯一准则。

## 1. 这个仓库是做什么的

`teambot-mvp` 是一个 TeamBot 风格后端 Agent MVP，核心是自研 ReAct 运行时：

- 主循环：`reason -> act -> observe -> (loop | compose_reply)`
- `reason` 是 reasoner + deterministic guards（输出 native tool call 或 final text）
- `tools`/`event_handlers`/`skills` 分层，其中 `skills` 只提供 reasoner context，不进入可执行 action surface
- 内部 runtime 采用 CoPaw 风格：tool profile + namesake 策略 + active-only skills + MCP 注入
- 线程路由与事件幂等是硬约束

## 2. 先看这 4 个文件（最快理解路径）

1. `src/teambot/agent/runtime.py`
2. `src/teambot/agent/graph.py`
3. `src/teambot/agent/reason.py`
4. `src/teambot/agent/execution.py`

看完这四个文件，基本就能理解“怎么决策 + 怎么执行 + 模型在哪里调用”。

## 3. 单次请求执行链

1. 入口接收事件（HTTP/CLI）
2. `AgentService.process_event` 构建初始状态并调用 `TeamBotRuntime`
3. runtime 进入 ReAct 循环
4. `reason` 用固定优先级选 action 或结束
5. `act` 执行动作（event_handler/tool + policy）
6. `observe` 更新 step 与 trace，然后回到下一轮 `reason`
7. `compose_reply` 产出最终 `reply_text`
8. 写入 store（会话历史 + 幂等缓存）

## 4. 目录地图（按职责）

目标结构名词定义以 `docs/code-structure.md` 为准。

- `src/teambot/app/main.py`
  FastAPI 入口（`/events/slack`, `/skills`, `/health`）

- `src/teambot/app/cli.py`
  交互式 CLI 调试入口（主路径消费 `AgentService.stream_event(...)`，按 `Step N · Thinking/Tool/Result/Final` 渲染 transcript，同时支持把 reasoning token 流进 `Thinking`，把 answer token 流进 `Final (live)`）

- `src/teambot/app/tui.py`
  Textual TUI 入口（Claude Code 风格单列 workbench，顶部状态栏尽量弱化，底部输入框采用 Claude-like composer，空态 welcome 不强制滚动，消费同一条 `AgentService.stream_event(...)` 数据流，默认只展示更淡的 tool/result 摘要和更强的 final answer 视觉层级）

- `src/teambot/app/slash_commands.py`
  CLI/TUI 共用的 slash command 定义与分发入口；用户可见命令只在这里维护，`/tools` 不对外暴露

- `src/teambot/app/bootstrap.py`
  统一 composition root（API/CLI 都从这里构建 service）

- `src/teambot/agent/runtime.py`
  ReAct runtime owner（组装 tools/skills/mcp + 构建 graph + invoke）

- `src/teambot/agent/service.py`
  应用层 service，负责 `process_event`、`stream_event`、会话存储和回复组装

- `src/teambot/agent/*`
  核心 ReAct 节点与循环控制（`graph.py` / `reason.py` / `execution.py` / `state.py` / `policy.py` / `service.py`）

- `src/teambot/actions/tools/*`
  tool registry 与 builtin tool surface（profile 驱动）

- `src/teambot/actions/event_handlers/*`
  deterministic event handler registry（`create_task` / `handle_reaction`）

- `src/teambot/agent/orchestrator.py`
  runtime orchestrator（只做 registries + tools + MCP wiring）

- `src/teambot/mcp/*`
  MCP 配置、manager、tool bridge

- `src/teambot/skills/*`
  skill docs lifecycle + reasoner skill-context assembly

- `src/teambot/providers/*`
  provider manager + client 实现（含 LangChain 适配）

- `src/teambot/actions/registry.py`
  `PluginHost`：唯一统一 action surface（tool / event_handler）

- `src/teambot/agent/runtime.py`
  runtime owner，负责把 registries 绑定成 `PluginHost` 后再交给 graph

- `src/teambot/domain/store/memory_store.py`
  内存态会话存储与幂等缓存

- `src/teambot/domain/models.py`
  核心输入输出模型与 transcript event contract（`InboundEvent` / `OutboundReply` / `RuntimeEvent`）

- `tests/*`
  行为与边界测试（包含核心分层约束）

## 5. Prompt 在哪里

当前核心流程里，model prompt 在 reason/planner 阶段：

- `src/teambot/agent/prompts/system_prompt.py`
  - 从工作目录读取 `AGENTS.md`（required）+ `SOUL.md` + `PROFILE.md`
- `src/teambot/actions/tools/builtin.py`
  - 读取 `TOOLS_PROFILE` / `TOOLS_NAMESAKE_STRATEGY`
  - 调用 `runtime_builder` 组装 builtin tool surface
- `src/teambot/actions/tools/catalog.py`
  - external-operation 工具定义（manifest + handler）
- `src/teambot/actions/tools/runtime_builder.py`
  - profile 选集 + namesake 冲突策略
- `src/teambot/actions/tools/external_operation_tools.py`
  - `read_file` / `write_file` / `edit_file` / `execute_shell_command` / `browser_use` / `get_current_time`
  - `desktop_screenshot` / `send_file_to_user`（full profile）
- `src/teambot/mcp/manager.py` + `bridge.py`
  - MCP tools 加载并桥接到同一 tool registry

`observe/compose` 是确定性代码阶段，没有 LLM prompt。

> 说明：旧的 planner/model-adapter 路径已移除，不再作为运行时路径或兼容层维护。
> 当前命名统一为 `reasoner`（保留兼容参数别名 `planner`）。

## 6. LangChain 在哪里

LangChain 只在 provider client 层使用，不在 core runtime 层：

- `src/teambot/providers/clients/langchain.py`
  - `langchain_core.messages`
  - `langchain_openai.ChatOpenAI`
  - `langchain_anthropic.ChatAnthropic`

调用链：`reason reasoner -> provider_manager.invoke_role_tools -> provider_client(langchain bind_tools)`

## 7. 关键行为规则（当前实现）

- `reason` 优先级：`max-step` -> deterministic direct routes -> reasoner
- `react_done=true` 会直接走 `compose_reply`
- `observe` 阶段只记录 tool observation；是否继续由下一轮 reasoner 是否继续发 tool call 决定
- `observe` 产出的 `execution_trace` 现在包含 action input，供 CLI/API reply 做展示
- runtime 还会发 `RuntimeEvent`，给 CLI/TUI 这种 transcript 客户端按 step 渲染
- provider live token 也会在 `AgentService.stream_event(...)` 里被桥接成 runtime-level delta 事件：
  - `model_reasoning_token -> thinking_delta`
  - `model_token -> final_delta`
- 当前 CLI 已经以 `RuntimeEvent` 作为主 transcript 数据源，不再主要依赖事后 `execution_trace` 拼接
- tool surface 由 `TOOLS_PROFILE` 决定（`minimal|external_operation|full`）
- CLI 支持 `--tools-profile` 与 `--tools-config <json>` 做 session 级覆盖（profile + per-tool enable/disable）
- CLI 始终使用 transcript 视图；`debug` 和 `stream` 是可见性开关，不是 mode
- 当 provider 能流式返回 reasoning token 时，CLI 会在 `Thinking` 段里持续渲染
- 当 provider 能流式返回最终文本时，CLI 会在 `Final (live)` 段里持续渲染，再避免把同一段 final answer 重复打印一遍
- TUI 也消费同一条 event stream，但呈现层不暴露 `Step N` 标题，也不默认渲染 thinking；它只显示更接近 Claude 的 tool/result 摘要和 final answer
- skills 来自 active_skills；只注入 reasoner context；不会自动 sync 初始化
- CLI/TUI 共用 slash command surface：`/help`、`/skills`、`/skills sync [--force]`、`/skills enable <name>`、`/skills disable <name>`、`/newthread`、`/stream on|off`、`/reaction <name>`、`/exit`
- `/tools` 已从用户可见 slash surface 移除
- MCP 开启时通过 bridge 注入同一 action surface（`MCP_ENABLED=true`）
- 高风险 action（`write_file` / `edit_file` / `execute_shell_command` / `exec_command`）必须经过 policy gate
- 流式输出是否“细粒度”，取决于 provider chunk 粒度
- `AgentService.stream_event(...)` 是给 TUI/CLI 这种实时 transcript 客户端的接口；`process_event(...)` 保持最终 reply 兼容接口

## 8. 常用调试入口

- API 启动：`PYTHONPATH=src uvicorn teambot.app.main:app --reload`
- CLI：`PYTHONPATH=src python -m teambot.app.cli`
- TUI：`PYTHONPATH=src python -m teambot.app.tui`
- API/CLI 都会在 bootstrap 阶段自动加载当前工作目录可见的 `.env`，但不会覆盖 shell 里已设置的环境变量
- ReAct 全链路调试：`PYTHONPATH=src python -m teambot.app.react_loop_demo`
- Provider 冒烟：`PYTHONPATH=src python -m teambot.app.provider_smoke_test --pretty`

## 9. 文档优先级（必须遵守）

1. `docs/README.md`
   文档入口索引（先看 canonical 列表与路径）
2. `docs/agent-core-algorithm.md`
   Agent 核心算法唯一事实来源（流程、prompt、规则）
3. `docs/architecture-boundaries.md`
   模块边界与依赖方向
4. `AGENTS.md`
   仓库协作与命名规范

## 10. 维护约定

- 改了核心算法（reason/act/observe/compose、tool prompt、provider streaming 等），必须同步更新 `docs/agent-core-algorithm.md`
- 改了模块依赖方向，必须同步更新 `docs/architecture-boundaries.md`
- 新人或 AI 上手，优先读本文件 + 第 9 节文档


