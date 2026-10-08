# Lab 5 mini-letta v0.5：对话结束，后台反思

> 目标：反思水位线、两种触发器、反思子 agent（在 worktree 里运行）、收尾状态机、每个 agent 一把反思锁、仓库级 LF 配置。演示：三句话之后反思自动启动，从中挑出两条持久偏好写进 `human.md` 并合并；主对话下一回合就知道了。前置：第 14–17 章。完成后：`git checkout v0.5`。

## L5.1 改动一览

```text
$ git diff v0.4 v0.5 --stat
 package.json                 |   2 +-
 src/agent/loop.ts            |   4 +-
 src/cli.ts                   |  69 ++++++++++---
 src/llm/mock-helpers.ts      |  71 +++++++++++++
 src/llm/mock-reflection.ts   |  76 ++++++++++++++
 src/llm/mock.ts              |  83 +++-------------
 src/memory/memfs.ts          |   4 +
 src/reflection/launcher.ts   |  95 ++++++++++++++++++
 src/reflection/post-turn.ts  |  28 ++++++
 src/reflection/prompt.ts     |  36 +++++++
 src/reflection/transcript.ts |  78 +++++++++++++++
 src/reflection/worktree.ts   | 111 +++++++++++++++++++++
 src/store/agent-store.ts     |  14 +++
 src/utils/file-lock.ts       |  46 +++++++++
 test/v02-memfs.test.ts       |   8 ++
 test/v05-reflection.test.ts  | 230 +++++++++++++++++++++++++++++++++++++++++++
 16 files changed, 870 insertions(+), 85 deletions(-)
```

## L5.2 步骤

1. **设置**：`AgentRecord.reflection?: { trigger, stepCount }`，默认 `compaction-event` / 25。
2. **水位线**（`src/reflection/transcript.ts`）：`reflection-state.json`；`unreflectedMessages`、`stepsSinceLastReflection`、`buildReflectionPayload`（去掉摘要和纯提醒消息、工具结果截 1 000 字、写 JSON 数组）、`markReflected`。
3. **worktree 与状态机**（`src/reflection/worktree.ts`）：`createMemoryWorktree`、`finalizeMemoryWorktree`（在 memory-operation 锁内）、`consumesTranscript`。
4. **锁**（`src/utils/file-lock.ts`）。
5. **提示词**（`src/reflection/prompt.ts`）。
6. **启动器**（`src/reflection/launcher.ts`）：锁 → 父仓库干净 → payload → worktree → 以 `<parent>~reflection` 身份在 worktree 里 `runTurn` → 收尾 → 推进水位线。给 `runTurn` 加 `extraEnv` 参数传 `TRANSCRIPT_PATH`、`PARENT_AGENT_ID`。
7. **回合后触发**（`src/reflection/post-turn.ts`）。
8. **mock**：把规则辅助函数拆到 `mock-helpers.ts`（否则 `mock.ts` ⇄ `mock-reflection.ts` 会循环依赖——letta-code 的 CI 用 madge 检查循环依赖，我们也在 `package.json` 里加了 `check:cycles`）；`mock-reflection.ts` 实现确定性的反思者。
9. **CLI**：`reflect [--instruction]`、`sleeptime --trigger … --steps …`；每次 `chat` 之后调用 `maybeReflectAfterTurn`。交互模式下反思在后台跑、不阻塞下一次输入——注意 `chatOnce` 返回 `{ reflection: Promise }` 而不是直接返回 promise：async 函数返回的 promise 会被**展开**，调用者 `await` 时会连反思一起等。
10. **LF**：`initMemoryRepo` 钉死 `core.autocrlf=false`、`core.eol=lf`（第 16 章踩坑记录）。

## L5.3 运行

```bash
bun test test/v05-reflection.test.ts
export MINI_LETTA_HOME=$(mktemp -d)
bun src/cli.ts sleeptime --trigger step-count --steps 3
bun src/cli.ts chat -p "帮我看下这个报错"
bun src/cli.ts chat -p "我更喜欢用 tabs 缩进"
bun src/cli.ts chat -p "今天我们决定以后一律用 pnpm"
bun src/cli.ts memory log
cat "$(bun src/cli.ts memory path)/human.md"
bun src/cli.ts chat -p "你知道我什么？"
```

输出见第 15 章 15.6 节。之后看看留下了什么：

```bash
A=$MINI_LETTA_HOME/agents
ls $A                                              # agent-default  agent-default~reflection
ls $A/agent-default/memory-worktrees               # 空：worktree 已清理
git -C $A/agent-default/memory branch              # 只有 main：反思分支已删除
ls $A/agent-default/reflections/payloads           # 反思读过的 payload
cat $A/agent-default/conversations/default/reflection-state.json
cat $A/agent-default~reflection/conversations/*/messages.jsonl | jq -r '.role + ": " + (.content|.[0:80])'
```

一次真实运行的输出（节选）：

```text
agent-default
agent-default~reflection
--wt:                              ← memory-worktrees 为空
--branches:
* main                             ← 反思分支已删除
payload-1791478331028.json
{
  "lastReflectionStartedAt": "2026-10-08T16:52:11.028Z",
  "reflectedThroughMessageId": "msg-muzrxz0t295ln4i",
  "lastReflectionSucceededAt": "2026-10-08T16:52:11.517Z"
}
user: <system-reminder> Agent info: - AGENT_ID: agent-default~refl
assistant:
tool: 829 /tmp/tmp.xOnZ9i3toC/agents/agent-default/reflections/pay
assistant:
tool: 1cf1eaf chore(reflection): remember 2 user preference(s) 🔮
user: <system-reminder> <memory_update> The memory filesystem has
assistant: Summary: updated human.md. Commit: 1cf1eaf chore(reflection)
```

反思子 agent 自己的对话：任务提示、读 transcript（829 字节）、提交、报告。注意倒数第二行：反思者提交之后，**它自己**也收到了一条 `<memory_update>`——它的 `memoryDir` 是 worktree，它的提交让 worktree 的 HEAD 变了，第 9 章的机制对它一视同仁。它的系统提示里有父 agent 的记忆——用 `jq -r .content` 看第一条之前的系统提示需要另想办法（练习 1）。

## L5.4 用真模型做反思

```bash
for t in "帮我看下这个报错" "我更喜欢用 tabs 缩进" "今天我们决定以后一律用 pnpm"; do bun src/cli.ts chat -p "$t" >/dev/null; done
MINI_LETTA_PROVIDER=openai MINI_LETTA_MODEL=qwen2.5:3b bun src/cli.ts reflect
bun src/cli.ts reflect           # 再用 mock 跑一次
```

`qwen2.5:3b` 两次分别给出了空回复和“只说不做”，加了证据检查之后都被判为 `failed`，第二条命令用 mock 重试同一段对话并成功合并（第 15 章踩坑记录 2）。如果你有更强的本地模型（比如 7B 以上、支持工具调用），换上它，观察它是否遵守“有界读取”和提交格式。

## L5.5 练习

1. **巩固**：把 `ResolvedSystemPrompt` 也写进反思子 agent 的对话目录（就像主 agent 的 `system-prompt.json`），然后确认里面确实包含了父 agent 的 `<human>`、`<persona>`。
2. **扩展**：给 `reflect` 加 `--instruction`（已经有参数了）的 mock 支持：比如 `--instruction "只关注工具偏好"` 时，mock 只提取包含 `pnpm|npm|yarn|tabs` 的偏好。
3. **读源码**：letta-code 的反思是独立进程（`spawnBackgroundSubagentTask`），mini-letta 是同一进程里的 `runTurn`。列出这个差别在三方面的影响：崩溃隔离、内核沙箱（第 19 章）、CLI 一次性模式（`-p`）下的生命周期。
