# Lab 4 mini-letta v0.4：长对话不撑爆，也不失忆

> 目标：token 估算与阈值、请求前压缩（滑动窗口 + 兜底）、上下文 id 列表、压缩后重编译、BM25 recall 工具。演示：在 1 200 token 的窗口里聊 17 回合，压缩 5 次，最后仍能找回第一句话里的端口号。前置：第 11–13 章。完成后：`git checkout v0.4`。

## L4.1 改动一览

```text
$ git diff v0.3 v0.4 --stat
 package.json                        |   9 ++-
 src/agent/loop.ts                   |  53 ++++++++++---
 src/cli.ts                          |  28 ++++++-
 src/context/compact-conversation.ts |  54 +++++++++++++
 src/context/compaction.ts           | 146 ++++++++++++++++++++++++++++++++++++
 src/context/tokens.ts               |  33 ++++++++
 src/llm/mock.ts                     |  49 +++++++++++-
 src/llm/openai-compatible.ts        |  15 +++-
 src/llm/types.ts                    |  10 +++
 src/recall/search.ts                | 136 +++++++++++++++++++++++++++++++++
 src/store/conversation-store.ts     |  23 ++++++
 src/tools/recall-tool.ts            |  35 +++++++++
 test/v04-context.test.ts            |  99 ++++++++++++++++++++++++
 13 files changed, 673 insertions(+), 17 deletions(-)
```

（`kind: "summary"`、`clipSummary` 和降权修复都是在 v0.4 开发过程中、打 tag 之前加上的。）

## L4.2 步骤

1. **`src/context/tokens.ts`**：`estimateTextTokens`（chars/4）、`estimateMessageTokens`（含工具调用参数）、`estimateRequestTokens`（系统提示 + 工具 JSON + 消息）。
2. **`src/context/compaction.ts`**：阈值、`planSlidingWindow`、`planAll`、摘要提示词、`formatTranscript`（去掉提醒、工具结果截 2 000 字）、`middleTruncate`、`clipSummary`、`packageSummary`。
3. **`ConversationStore`**：`context.json` 存上下文 id 列表；`inContext()`、`setContext()`；`append()` 同步追加 id。
4. **`src/context/compact-conversation.ts`**：编排（滑动窗口 → 兜底 all → 摘要 → 写入 → 重编译 → 标记压缩事件）。
5. **循环**：每一步先 `prepare()`，超阈值先压缩；调用模型时捕获 `ContextOverflowError`，压缩后重试一次。注意 `prepare()` 用的是 `store.inContext()` 而不再是 `store.all()`。
6. **mock**：超窗口抛溢出；摘要规则（每句只留 12 个字）；recall 规则；工具结果后的回答按工具名区分。
7. **recall**：`src/recall/search.ts` + `src/tools/recall-tool.ts`；CLI 加 `search`、`compact`。

## L4.3 运行

```bash
bun test test/v04-context.test.ts
export MINI_LETTA_HOME=$(mktemp -d) MINI_LETTA_CONTEXT_WINDOW=1200
bun src/cli.ts chat -p "我们的数据库端口是 5433，别用默认的 5432" >/dev/null
for i in $(seq 0 15); do
  bun src/cli.ts chat -p "第 $i 个无关话题：$(printf '今天天气不错。%.0s' $(seq 12))" | grep "compacted"
done
bun src/cli.ts chat -p "还记得数据库端口吗？"
bun src/cli.ts search 数据库端口 | head -3
```

实际输出见第 12 章 12.8 节和第 13 章 13.5 节。检查一下磁盘上的状态：

```bash
C=$MINI_LETTA_HOME/agents/agent-default/conversations/default
wc -l < $C/messages.jsonl               # 全部消息（只追加）
jq '.inContextIds | length' $C/context.json   # 在上下文里的
grep -c '"kind":"summary"' $C/messages.jsonl  # 摘要条数
cat $C/compaction-event.json            # 最近一次压缩的统计，pending 供第 14 章使用
```

## L4.4 真模型

把摘要交给 `qwen2.5:3b`：

```bash
MINI_LETTA_PROVIDER=openai MINI_LETTA_MODEL=qwen2.5:3b bun src/cli.ts compact
```

我们看到的结果（第 12 章踩坑记录）：几乎没有压缩率、内容有编造。这一步之后加上了 `clipSummary`。如果你用更大的模型，对比一下摘要是否遵守了“查找线索（lookup hints）”这一节。

## L4.5 练习

1. **巩固**：把 `MINI_LETTA_CONTEXT_WINDOW` 调到 900，重跑演示。会不会出现“地板太高、压缩也救不回来”的情况？mini-letta 此时的行为是什么？（letta-code 会直接报错并建议调大窗口，第 11 章 11.4。）
2. **扩展**：在压缩事件里记录“被摘要的消息 id 范围”，并让 `recall_search` 的结果标注“这条消息已不在上下文里”。
3. **读源码**：letta-code 压缩后会从 `context_tokens_after < context_window` 判断滑动窗口是否成功（`local-backend.ts:754-759`）。为什么比较对象是整个窗口，而不是第 11 章的阈值？
