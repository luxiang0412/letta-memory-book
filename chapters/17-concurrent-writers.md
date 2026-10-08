# 第 17 章 并发写者：锁、worker 与冲突修复

> 本章目标：列清楚一个记忆仓库可能有哪些写者，理解 letta-code 用什么组合（一把“谁死了才能抢”的锁 + 私有 worktree + 只暂存自己的文件 + 冲突修复 worker）让它们不互相踩踏。前置：第 16 章。对应代码：mini-letta `v0.5` `src/utils/file-lock.ts`、`src/reflection/{launcher,worktree}.ts`。

## 17.1 谁会写记忆仓库

| 写者 | 在哪写 | 何时 |
|---|---|---|
| 主 agent | 主检出 | 对话中，用 Bash/Edit + git |
| `memory` 子 agent（memory worker） | **私有 worktree** | 主 agent 委派的后台记忆更新 |
| 反思子 agent | **私有 worktree** | 回合后、后台 |
| 反思集成（merge） | 主检出 | 反思结束时 |
| 冲突修复 worker | **主检出本身** | 同步发现冲突/校验失败后 |
| 回合后同步 | 主检出 | 每回合结束：pull --rebase / push |
| 其他机器 | 远端 → 拉到主检出 | 任意时刻（第 18 章） |
| 用户 | 主检出 | 任意时刻 |

还可能有**多个 letta-code 进程**同时对着同一个 agent（比如 TUI 和桌面端）。

## 17.2 一把锁，但不锁主 agent

```ts
// src/agent/memory-operation.ts:16-34（节选）
/**
 * The lease is a file lock that is reaped only when its holder process is
 * gone (pid plus start time), so a paused holder keeps the checkout and
 * waiters keep waiting; the abort signal is the way to give up.
 */
const LEASE_OPTIONS: FileLockOptions = { reapOnlyDeadOwner: true, retryMs: 100 };

/**
 * Serialize the harness-owned writers of a memory checkout across local
 * processes: memory workers, conflict repair, reflection integration, and
 * post-turn sync. The primary agent's own edits are not routed through this
 * lock; the prompts ask it to wait for a worker it launched, and workers stage
 * only the files they change so concurrent edits degrade to a Git conflict.
 */
```

三个关键设计：

1. **只锁 harness 自己的写者**。主 agent 不走这把锁——你没法让一个 LLM 在敲 `git commit` 之前去拿锁。对主 agent 只能靠提示词（“等你派出去的 worker 结束”、“只暂存你改的文件”）和 git 本身（并发改同一处会变成冲突，而不是静默覆盖）。
2. **锁只在持有者进程死亡时才会被回收**（pid + 进程启动时间，防 pid 复用）。不设超时：一个慢的持有者（比如在等模型）继续持有，等待者继续等；想放弃就用 `AbortSignal`。超时回收看似稳妥，实际上会让两个写者同时进入临界区。
3. **锁文件放在这个检出自己的 git 目录里**（`getMemoryOperationPath()` 用 `getMemoryGitDir()`），所以主检出和各个 worktree 的锁互不干扰（第 7 章我们正是因为忽略了这一点，把 mini-letta 的反思弄坏了一次）。

回合后同步用的是**不等待**的版本：`claimMemoryOperation(memoryDir)`（`:35`，`wait` 默认 false）拿不到就跳过这一回合的同步（`src/reminders/memory-git-sync.ts` 里 `release !== null` 的判断）——下一回合再说，不阻塞用户。

## 17.3 memory worker：委派出去的记忆更新

主 agent 忙着干活时，可以把“记下这件事”委派给 `memory` 子 agent（`src/agent/subagents/builtin/memory.md`）。它的描述写得很直接：“Background memory upkeep during another task; when memory is the user's main request, edit it directly instead. Runs silently with no notification or result, so continue immediately.”

`runMemoryWorker()`（`src/agent/subagents/memory-worker.ts`）的注释概括了它的协议：

> An update worker edits a private worktree of the memory repository, so the primary agent's own edits to the checkout are never touched: a cancelled worker is discarded outright, and a finished worker's commits are merged back before the lease is released. A merge that conflicts with the primary's changes keeps the worker's branch and reports it instead of guessing. A repair worker must work on the checkout itself, where the unfinished Git operation lives.

和反思相比（第 16 章练习 2）：worker 的合并（`integrateMemoryWorkerWorktree()`，`src/agent/memory-worktree.ts:685`）**不**因主检出脏而拒绝——git 只在改动重叠时才会拒绝，那会表现为冲突；冲突时**保留**分支，不丢工作。合并之后同步、重编译系统提示。

memory worker 的提示词里也写着同样的纪律（`memory.md:26`）：“stage them by explicit path, never with `git add -A` or `git add .`, because the primary agent may be editing other files in this checkout at the same time.”

## 17.4 冲突修复

回合后同步（第 18 章）可能留下两种“需要人或模型来判断”的状态：`conflict`（rebase 冲突）和 `invalid`（第 7 章的审计没通过）。letta-code 不让主 agent 在前台处理它们，而是启动一个**修复 worker**：

- `claimMemoryConflictRepair()`（`src/agent/memory-conflict-repair.ts:161`）在锁内记录一次“修复尝试”（带一个 token、冲突签名、进程身份），防止重复启动；同一个冲突修过一次还没修好，就标记为 `attempted`，不再自动重试；
- 修复 worker 在**主检出本身**工作，因为未完成的 git 操作（`MERGE_HEAD`、`REBASE_HEAD`…）就在那里；
- 修复进行中，主 agent 收到的提醒是：

```text
MEMORY REPAIR RUNNING: A background worker is repairing the memory repository.
...
Continue the current task. Do not inspect, edit, or run Git commands in the memory repository
while the background repair is active.
```

（`formatMemoryRepairInProgressReminder()`，`src/reminders/memory-git-sync.ts:40`。）修复失败，主 agent 收到的是“报告给用户，不要在前台改”的提醒（`:58` 起的 `conflict`、`invalid` 分支）。

`memory.md` 里给修复 worker 的规则值得一读：“If a merge or rebase is already in progress, resolve it first by reading both sides and preserving the intended memory. Never prefer one side wholesale… Do not abort, reset, stash, amend, discard, or commit unrelated changes. If the intended resolution is unclear, leave the unresolved state intact and describe the blocker”。

## 17.5 mini-letta 的实现

mini-letta 实现了锁和反思的串行化，没有实现 memory worker 和修复 worker（练习 2、3）。

**锁**（`src/utils/file-lock.ts`）：`openSync(path, "wx")` 原子创建，内容是持有者的 pid；已存在时检查持有者是否还活着（`process.kill(pid, 0)`，`EPERM` 也算活着），死了才回收：

```ts
// code/mini-letta @ v0.5  src/utils/file-lock.ts（节选）
export function tryAcquireLock(path: string): (() => void) | null {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const fd = openSync(path, "wx");
      writeSync(fd, JSON.stringify({ pid: process.pid, acquiredAt: new Date().toISOString() }));
      closeSync(fd);
      return () => rmSync(path, { force: true });
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
      if (ownerAlive(path)) return null;
      rmSync(path, { force: true }); // reap a dead owner's lock, then retry once
    }
  }
  return null;
}
```

比 letta-code 简化的地方：只用 pid，没有进程启动时间（pid 复用时可能误判为“还活着”——偏保守，不会误回收）。

两把锁的用途：

- `agents/<id>/reflection.lock`：每个 agent 同一时间只能有一个反思（对应 letta-code 的 `tryReserveReflectionLaunch()`，`reflection-launcher.ts:286`，那是进程内的保留 + 排队；mini-letta 用文件锁，所以跨进程也成立）；
- `<主检出>/.git/mini-letta-memory-operation.lock`：反思收尾（合并）在它里面进行。

测试：

```ts
// test/v05-reflection.test.ts
const release = tryAcquireLock(join(agentDir(agent.id, home), "reflection.lock"));
expect(await launchReflection({ home, agent, conversationId: "c1", provider: new MockProvider() })).toEqual({
  launched: false,
  reason: "already_active",
});
release?.();
```

## 17.6 一个并发场景的完整推演

用户在对话里说“以后用 tabs”，主 agent 去改 `human.md`；与此同时，上一回合触发的反思正在 worktree 里也改 `human.md`。

1. 反思在 worktree 的分支上提交了“- 我更喜欢用 tabs 缩进”；
2. 主 agent 在主检出上提交了“- edited by primary”（同一位置）；
3. 反思收尾：拿锁 → 主检出干净 → 合并 → **冲突** → `merge --abort` → `merge_conflict`，清理 worktree，水位线不动；
4. 下一次触发时，反思基于**新的** HEAD（已含主 agent 的改动）重新创建 worktree，读到的父记忆快照里已有“edited by primary”，这次合并成功。

这正是第 16 章那个“冲突后重试”测试做的事。没有谁的工作被覆盖，代价是反思多跑了一次。

## 17.7 练习

1. **巩固**：在两个终端里同时对同一个 agent 执行 `bun src/cli.ts reflect`（可以先在 mock 里加一个 `sleep`），确认第二个得到 `already_active`。然后 `kill -9` 第一个进程，再执行一次，锁会被回收吗？
2. **扩展**：实现 memory worker：给主 agent 一个 `delegate_memory({ instruction })` 工具，它在 worktree 里运行一个子 agent，结束后按 letta-code 的规则合并（主检出脏不阻止；冲突保留分支并报告）。
3. **扩展**：实现冲突修复：`syncAfterTurn` 返回 `conflict` 时，不再只提醒主 agent，而是启动一个修复子 agent 在主检出上 `git pull --rebase` 并解决冲突。参照 `memory.md` 的 Git 一节写它的提示词。
