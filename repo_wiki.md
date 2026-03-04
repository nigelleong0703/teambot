# Repo Wiki (AI Quick Onboarding)

## 1. 这个仓库是做什么的

`teambot-mvp` 是一个 TeamBot 风格后端 Agent MVP，核心是自研 ReAct 运行时：

- 主循环：`reason -> act -> observe -> (loop | compose_reply)`
- `reason` 是确定性规则路由（不是 model planner）
- skills/tool 显式注册，统一到一个 action surface
- `general_reply` 是默认 message tool（可走模型，也可本地回退）
- 线程路由与事件幂等是硬约束

## 2. 先看这 4 个文件（最快理解路径）

1. `src/teambot/agents/core/graph.py`
2. `src/teambot/agents/core/router.py`
3. `src/teambot/agents/core/executor.py`
4. `src/teambot/agents/tools/builtin.py`

看完这四个文件，基本就能理解“怎么决策 + 怎么执行 + 模型在哪里调用”。

## 3. 单次请求执行链

1. 入口接收事件（HTTP/CLI）
2. `AgentService.process_event` 构建初始状态并调用 runtime
3. runtime 进入 ReAct 循环
4. `reason` 用固定优先级选 action 或结束
5. `act` 执行动作（skill/tool + policy）
6. `observe` 更新 step 与 trace，判断是否继续
7. `compose_reply` 产出最终 `reply_text`
8. 写入 store（会话历史 + 幂等缓存）

## 4. 目录地图（按职责）

- `src/teambot/main.py`
  FastAPI 入口（`/events/slack`, `/skills`, `/health`）

- `src/teambot/cli.py`
  交互式 CLI 调试入口

- `src/teambot/interfaces/bootstrap.py`
  统一 composition root（API/CLI 都从这里构建 service）

- `src/teambot/agents/core/*`
  核心 runtime 节点与循环控制

- `src/teambot/agents/tools/*`
  tool registry 与 builtin tools（含 `general_reply`）

- `src/teambot/agents/skills/*`
  skill registry、builtin skills、active skills 生命周期

- `src/teambot/agents/providers/*`
  provider manager + client 实现（含 LangChain 适配）

- `src/teambot/plugins/registry.py`
  skill + tool 的统一 action surface

- `src/teambot/store.py`
  内存态会话存储与幂等缓存

- `tests/*`
  行为与边界测试（包含核心分层约束）

## 5. Prompt 在哪里

当前核心流程里，model prompt 在 message tool，而不是 reason 阶段：

- `src/teambot/agents/prompts/system_prompt.py`
  - 从工作目录读取 `AGENTS.md`（required）+ `SOUL.md` + `PROFILE.md`
- `src/teambot/agents/tools/builtin.py`
  - `_GeneralReplyTool.__call__` 里直接使用 `build_system_prompt_from_working_dir()`
  - `user_message` 直接取 `state.user_text`
  - 返回自然语言文本（JSON 非必须）

`reason/observe/compose` 是确定性代码阶段，没有 LLM prompt。

> 说明：`src/teambot/agents/planner.py` 与 `src/teambot/agents/model_adapter.py` 已移除，不再作为运行时路径或兼容层维护。

## 6. LangChain 在哪里

LangChain 只在 provider client 层使用，不在 core runtime 层：

- `src/teambot/agents/providers/langchain_client.py`
  - `langchain_core.messages`
  - `langchain_openai.ChatOpenAI`
  - `langchain_anthropic.ChatAnthropic`

调用链：`general_reply tool -> provider_manager -> provider_client(langchain)`

## 7. 关键行为规则（当前实现）

- `reason` 优先级：`max-step` -> `next_skill` -> `default action` -> `first available`
- `react_done=true` 会直接走 `compose_reply`
- `observe` 阶段若无 `next_skill`，默认结束
- `general_reply` 是 low-risk message tool（不是 skill）
- 高风险 action 必须经过 policy gate
- 流式输出是否“细粒度”，取决于 provider chunk 粒度

## 8. 常用调试入口

- API 启动：`PYTHONPATH=src uvicorn teambot.main:app --reload`
- CLI：`PYTHONPATH=src python -m teambot.cli`
- ReAct 全链路调试：`PYTHONPATH=src python -m teambot.react_loop_demo`
- Provider 冒烟：`PYTHONPATH=src python -m teambot.provider_smoke_test --pretty`

## 9. 文档优先级（必须遵守）

1. `docs/agent-core-algorithm.md`
   Agent 核心算法唯一事实来源（流程、prompt、规则）
2. `docs/architecture-boundaries.md`
   模块边界与依赖方向
3. `AGENTS.md`
   仓库协作与命名规范

## 10. 维护约定

- 改了核心算法（reason/act/observe/compose、tool prompt、provider streaming 等），必须同步更新 `docs/agent-core-algorithm.md`
- 改了模块依赖方向，必须同步更新 `docs/architecture-boundaries.md`
- 新人或 AI 上手，优先读本文件 + 第 9 节文档
