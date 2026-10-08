# 第 14 章 ★★ 睡眠时间：反思什么时候发生

> 本章目标：理解“后台反思（reflection / sleeptime）”为什么存在、由什么触发、如何记住“哪些对话已经反思过”。前置：第 9、12、13 章。对应代码：mini-letta `v0.5` `src/reflection/{post-turn,transcript}.ts`。

## 14.1 为什么需要第二个写者

到目前为止，记忆只有一个写者：agent 自己，在对话中途、在完成用户任务的间隙。这有三个问题：

1. **它在忙**。用户让它修 bug，它不会停下来整理“用户似乎偏好函数式写法”这种模糊的模式。
2. **它看不到全貌**。一条偏好可能分散在好几个对话里，单个对话里的 agent 看不出“这是个模式”。
3. **它可能很弱**。第 6、9、10 章里的 3B 模型连“提交”都做不好。

letta-code 的回答是借用人类睡眠的比喻：对话之间，另一个 agent 在后台回顾刚发生的事，把值得记住的东西整理进记忆。系统提示是这么跟 agent 解释的（`letta_root_memfs.md:167`）：“Just as human memory consolidates during sleep — strengthening important connections and discarding noise — your background agents refine your memory between active turns.” 对应的命令叫 `/sleeptime`（设置，`src/cli/commands/registry.ts:148`）、`/dream` 和 `/reflect`（手动触发，`:86`、`:92`）。

## 14.2 触发器

```ts
// src/reflection-settings.ts:1
export type ReflectionTrigger = "off" | "step-count" | "compaction-event";
```

```ts
// src/cli/helpers/memory-reminder.ts:15, 51-56
const DEFAULT_STEP_COUNT = 25;
const DEFAULT_REFLECTION_SETTINGS: ResolvedReflectionSettings = {
  trigger: "compaction-event",
  stepCount: DEFAULT_STEP_COUNT,
  merge: "auto",
  mergeInstructions: "",
};
```

- **compaction-event（默认）**：这一回合里发生过上下文压缩，就反思。理由很漂亮：压缩意味着有一段经历刚刚离开了上下文窗口，正是需要“巩固”的时候。
- **step-count**：自上次成功反思以来，累计完成的 assistant 步数达到 N（默认 25）。
- **off**。

另外有一个宿主级开关：原生 Windows 上默认关闭自动反思（`isAutoReflectionEnabled()`，`src/reflection-settings.ts:6`，可用 `LETTA_ENABLE_WINDOWS_AUTO_REFLECTION=1` 打开），手动的 `/dream`、`/reflect` 不受影响。设置按 agent 保存在全局和项目本地两级（`persistReflectionSettingsForAgent()`，`memory-reminder.ts:253`）。

## 14.3 回合后的判断

```ts
// src/cli/helpers/post-turn-reflection.ts:22-79（节选）
export async function maybeLaunchPostTurnReflection(params: {...}): Promise<boolean> {
  // Reminder restoration is client context maintenance, not reflection work.
  // Always consume compaction state even when MemFS or reflection is disabled.
  syncReminderStateFromContextTracker(params.reminderState, params.contextTracker);
  if (!params.agentId || !params.memfsEnabled) {
    params.reminderState.pendingReflectionTrigger = false;
    return false;
  }
  ...
  switch (params.reflectionSettings.trigger) {
    case "off":
      params.reminderState.pendingReflectionTrigger = false;
      return false;
    case "compaction-event": {
      if (!params.reminderState.pendingReflectionTrigger) return false;
      params.reminderState.pendingReflectionTrigger = false;
      return params.launch("compaction-event");
    }
    case "step-count": {
      params.reminderState.pendingReflectionTrigger = false;
      const transcriptState = await readTranscriptState(params.agentId, params.conversationId);
      if (!shouldFireStepCountTrigger(transcriptState.steps_since_last_successful_reflection,
                                      params.reflectionSettings)) return false;
      return params.launch("step-count");
    }
  }
}
```

注意 `pendingReflectionTrigger` 在每条路径上都被**消费掉**——不管最后有没有启动。压缩标记只在“压缩之后的那个回合结束时”有意义；如果当时设置是 `off`，以后改成 `compaction-event` 也不该补发一次。

调用它的地方在三条编排路径里各有一处（第 2 章）。在 headless 里，它紧跟在“把本回合追加到反思 transcript”之后，而且只在回合**成功、以 `end_turn` 结束**时才做（`src/headless.ts:4650-4664`）——被打断的回合不计数。

## 14.4 记住反思到了哪里：transcript 与水位线

反思需要知道“哪些对话内容还没被反思过”。letta-code 为此维护一份独立于后端存储的**客户端 transcript**：

```text
~/.letta/transcripts/<agent-id>/<conversation-id>/
├── transcript.jsonl   每个成功回合追加一段（user/assistant/reasoning/tool_call 行）
└── state.json         水位线
```

```ts
// src/cli/helpers/reflection-transcript.ts:28-38
export const REFLECTION_STATE_SCHEMA_VERSION = "v3_assistant_steps" as const;
export interface ReflectionTranscriptState {
  schema_version: typeof REFLECTION_STATE_SCHEMA_VERSION;
  reflected_through_message_id?: string;          // 水位线：反思到了哪条消息
  total_completed_steps: number;
  reflected_completed_steps: number;
  steps_since_last_successful_reflection: number;
  last_reflection_started_at?: string;
  last_reflection_succeeded_at?: string;
}
```

几个设计点：

- **水位线是消息 id，不是行号**。schema 名字里的 “v3_assistant_steps” 和旧版 “v2_message_id” 说明它演进过：计数从“回合”改成了“assistant 步”，并且有迁移代码（`migrateMessageIdState()`，`reflection-transcript.ts:792`）。
- **计数单位是 assistant 行**（`countAssistantRows()`，`:619`）：只数 `kind === "assistant"` 的条目，用户消息、工具调用都不算。
- **水位线只在成功时前进**。启动反思时只记录 `last_reflection_started_at`；只有反思结果被“消费”（合并成功或确认无需修改，第 16 章）时，`finalizeAutoReflectionPayload()`（`:1870`）才把 `reflected_through_message_id` 推进到这次切片的末尾。失败了，下一次反思会拿到**同一段**内容重来。
- **切片有快照边界**。`buildAutoReflectionPayload()`（`:1644`）记下切片结束在第几行（`endSnapshotLine`）；收尾时只看那一行之前的内容。反思进行期间新追加的回合不会被误标为“已反思”。

`buildMultiReflectionPayload()`（`:1756`）还支持一次反思多个对话：生成一个 `multi_transcript_reflection_payload` 清单，每个切片标注 `unreflected` 或 `replay`（已经反思过、为了去重和跨会话归纳再看一遍）。这对应第 14.1 节的第二个问题。

## 14.5 mini-letta 的实现

mini-letta 不单独维护 transcript：每个对话的 `messages.jsonl` 本来就是只追加的完整记录。水位线直接指向其中的消息 id：

```ts
// code/mini-letta @ v0.5  src/reflection/transcript.ts（节选）
export function unreflectedMessages(store: ConversationStore, state = readReflectionState(store)): Message[] {
  const all = store.all();
  if (!state.reflectedThroughMessageId) return all;
  const index = all.findIndex((m) => m.id === state.reflectedThroughMessageId);
  return index < 0 ? all : all.slice(index + 1);
}

export function stepsSinceLastReflection(store: ConversationStore): number {
  return unreflectedMessages(store).filter((m) => m.role === "assistant").length;
}
```

和 letta-code 的一个差别：mini-letta 的每条 assistant 消息都算一步，包括只有工具调用、没有文字的那种；letta-code 的 transcript 里工具调用是单独的 `tool_call` 行，不计数。

触发判断：

```ts
// code/mini-letta @ v0.5  src/reflection/post-turn.ts（节选）
const settings = input.agent.reflection ?? DEFAULT_REFLECTION_SETTINGS;
const store = new ConversationStore(input.agent.id, input.conversationId, input.home);
const compaction = store.readJson<{ pending?: boolean }>(COMPACTION_EVENT);
if (compaction?.pending) store.writeJson(COMPACTION_EVENT, { ...compaction, pending: false });   // 总是消费

if (settings.trigger === "off") return null;
if (settings.trigger === "compaction-event" && !compaction?.pending) return null;
if (settings.trigger === "step-count" && stepsSinceLastReflection(store) < settings.stepCount) return null;
return launchReflection(input);
```

压缩标记是第 12 章 `compactConversation()` 写下的 `compaction-event.json`。设置存在 `agent.json` 的 `reflection` 字段，CLI：

```bash
bun src/cli.ts sleeptime --trigger step-count --steps 3
```

## 14.6 运行与验证

```ts
// test/v05-reflection.test.ts
test("step-count fires once enough assistant steps accumulate", async () => {
  agent.reflection = { trigger: "step-count", stepCount: 3 };
  for (const userText of ["我更喜欢用 tabs 缩进", "嗯", "好的"]) {
    await runTurn({ ... userText });
    outcomes.push(await maybeReflectAfterTurn({ ... }));
  }
  expect(outcomes.slice(0, 2)).toEqual([null, null]);
  expect(outcomes[2]?.launched && outcomes[2].status).toBe("merged");
});

test("compaction-event (default) fires only after a compaction", async () => {
  // 1 200 token 窗口，12 个回合
  expect(compacted).toBeGreaterThan(0);
  expect(fired).toBe(compacted);       // 每次压缩恰好触发一次反思
});
```

CLI 走一遍（step-count = 3）：

```text
$ bun src/cli.ts sleeptime --trigger step-count --steps 3
{"trigger":"step-count","stepCount":3}
$ bun src/cli.ts chat -p "帮我看下这个报错"
（mock）我听到了：帮我看下这个报错
$ bun src/cli.ts chat -p "我更喜欢用 tabs 缩进"
（mock）我听到了：我更喜欢用 tabs 缩进
$ bun src/cli.ts chat -p "今天我们决定以后一律用 pnpm"
（mock）我听到了：今天我们决定以后一律用 pnpm
  ☾ reflection 20261008160658-c0ef7940: merged — Merged 1 reflection commit(s).
```

第三回合之后，反思启动、合并，`human.md` 多了两行（反思做了什么，见第 15 章）。

## 14.7 练习

1. **巩固**：设置 `step-count`、`stepCount: 2`，聊四句，查看 `reflection-state.json` 的变化；然后手动把 `reflectedThroughMessageId` 删掉，再聊一句，会发生什么？
2. **扩展**：实现 letta-code 的 multi-transcript 反思：一次反思同一个 agent 最近的 3 个对话，payload 写成清单文件，每个切片带 `mode: "unreflected" | "replay"`。收尾时只推进 `unreflected` 切片的水位线（参照 `finalizeMultiReflectionPayload()`，`reflection-transcript.ts:1905`）。
3. **读源码**：letta-code 为什么把反思 transcript 放在客户端（`~/.letta/transcripts`）而不是直接读后端的消息？想想 Cloud 后端、多台机器、以及 transcript 行里那些 `source_message_id` 是“may be synthetic”的注释。
