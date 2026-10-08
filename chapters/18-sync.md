# 第 18 章 同步与多机：记忆跟着 agent 走

> 本章目标：理解 letta-code 怎样让同一个 agent 的记忆在多台机器之间保持一致——服务器托管的 git 仓库、启动时拉取、回合后推送、非快进时 rebase、反思合并前刷新——并在 mini-letta 里用一个“bare 仓库服务器”实现同样的语义。前置：第 6、16、17 章。对应代码：mini-letta `v1.0` `src/sync/remote.ts`。

## 18.1 问题

letta-code 的 README 里有一张图：一个 Letta Cloud 上的 agent，同时连着笔记本、云主机、Mac Mini、托管沙箱。系统提示也告诉 agent（`letta_root_memfs.md:147`）：“your memory (in MemFS) belongs to you and travels with you wherever you run.”

如果每台机器各有一份独立的记忆，这句话就不成立。我们需要：

1. 第一台机器创建的记忆能被第二台机器拿到；
2. 两台机器各自的改动最终合到一起；
3. 冲突时不丢任何一边；
4. 同步不能让用户等。

git 天生就是干这个的。

## 18.2 letta-code：服务器上的 git 仓库

Cloud 后端（`remoteMemfs: true`）上，每个 agent 的记忆仓库托管在 Letta 服务器上：

```ts
// src/agent/memory-git.ts:228-233
export function getGitRemoteUrl(agentId: string, baseUrl?: string): string {
  const resolvedBaseUrl = (baseUrl ?? getMemfsServerUrl()).trim().replace(/\/+$/, "");
  return `${resolvedBaseUrl}/v1/git/${agentId}/state.git`;
}
```

认证不写进 URL，也不落盘：每次 git 命令临时加 `-c http.extraHeader=Authorization: Basic …`，同时清空 `credential.helper` 和 `core.askPass`，保证 git 不会弹出交互式提示（`buildGitAuthArgs()`，`:483`）；环境里还设了 `GIT_TERMINAL_PROMPT=0`（`buildNonInteractiveGitEnv()`，`:533`）。日志里出现的 URL 和 token 都会被脱敏（`redactGitAuthInText()`，`:142`）。网络类错误（503、Cloudflare 52x）会重试（`runGitWithRetry()`，`:632`）。

生命周期：

| 时机 | 做什么 | 代码 |
|---|---|---|
| 新机器第一次用这个 agent | `git clone`，然后装 hook | `cloneMemoryRepo()`（`:1504`） |
| 启动、切换 agent | 已有检出则 `pull` | `ensureLocalMemfsCheckout({ pullOnExistingRepo })`（`memory-filesystem.ts:271`）、`pullMemory()`（`memory-git.ts:1589`） |
| 每回合结束 | 有领先的提交就 push；被拒（非快进）就 `pull --rebase` 再 push | `syncPendingMemoryCommitsAfterTurn()`（`:1837`） |
| 反思合并前 | fetch，快进或 rebase 到 `origin/main` | `refreshParentFromOrigin()`（`memory-worktree.ts:275`） |

回合后同步（第 3 章列过它的状态）推送前还会做第 7 章的审计：没有通过校验的记忆不会离开本机。冲突和校验失败交给修复 worker（第 17 章）。

## 18.3 两个附加功能

**镜像到你自己的仓库。** `/memory-repository set git@github.com:...` 把 URL 写进记忆仓库的本地配置 `letta.memoryRepository.url`。一个 post-commit hook（`src/agent/memory-git-hooks.ts:254` 起的 `POST_COMMIT_HOOK_SCRIPT`）在每次提交后**在后台**推送到这个地址，失败只写日志（`.git/memory-repository-push.log`），不阻塞提交。注意它只在 `main` 分支上推：

```bash
# Reflection and other harness worktrees commit on temporary branches; only the
# main MemFS checkout should push to the optional memory repository remote.
[ "$branch" != "main" ] && exit 0
```

这又是一个“worktree 和主检出共享 hook”带来的细节：同一个 hook 在反思 worktree 里也会被触发，必须自己判断。

**共享记忆。** 一个独立于任何 agent 的记忆仓库，可以挂到多个 agent 上（系统提示 “Shared memory” 一节）。它在本地有自己的投影根目录和远端，回合后由 harness 推送已提交的改动（`syncAttachedAgentRepositories()`、`syncPendingAttachedRepositoryCommitsAfterTurn()`）。它的 hook 用 `shared-memory` 布局策略（第 5 章）。

## 18.4 mini-letta：一个目录就是服务器

mini-letta 的“服务器”是一个目录，里面每个 agent 一个 bare 仓库：

```ts
// code/mini-letta @ v1.0  src/sync/remote.ts（节选）
export function remoteUrlFor(agentId: string, env = process.env): string | undefined {
  const root = env.MINI_LETTA_REMOTE_ROOT;
  return root ? join(root, `${agentId}.git`) : undefined;
}
```

**创建或克隆。** `ensureMemoryCheckout()`（`src/store/agent-store.ts`）：本机已有检出就什么都不做；远端已有这个 agent 的记忆就克隆；否则初始化，并在配置了远端时把初始历史推上去。`loadOrCreateAgent()` 每次都会调用它，所以“新机器第一次用”是自动的。

**回合前拉取、回合后推送**，都在 `runTurn()` 里：

```ts
// code/mini-letta @ v1.0  src/agent/loop.ts（节选）
const pulled = pullMemory(memoryDir);                 // 先拿到别的机器推上来的
...
const synced = syncAfterTurn(memoryDir);              // 再把自己的推上去
const syncProblem = formatSyncReminder(synced, memoryDir);
if (syncProblem) enqueueReminder(store, syncProblem);
```

`syncAfterTurn()` 的状态和 letta-code 的同名函数一一对应：`skipped`、`conflict`、`dirty`、`clean`、`pushed`、`push_failed`。非快进时 rebase 一次再推；rebase 冲突就 `rebase --abort`，返回 `conflict`——**本地提交保持原样**，下一回合提醒 agent。

**反思合并前刷新。** `finalizeMemoryWorktree()` 在合并前调用 `refreshFromOrigin()`（逻辑照搬 `refreshParentFromOrigin`：远端是祖先就不动；本地是祖先就快进；否则 rebase，失败就 abort 并让本次反思 `failed`）；合并成功后立刻 `syncAfterTurn()` 推上去。

## 18.5 运行与验证：两台“机器”

测试（`test/v10-sync.test.ts`）用两个 `MINI_LETTA_HOME`（laptop、desktop）共享一个 `MINI_LETTA_REMOTE_ROOT`：

```ts
test("laptop remembers → desktop knows", async () => {
  await say(laptop, "记住：我用 pnpm");
  expect(git(join(remoteRoot, "agent-sync.git"), ["log", "-1", "--format=%s", "main"]).stdout.trim())
    .toBe("chore: remember user fact");
  const answer = await say(desktop, "你知道我什么？");   // desktop 第一次用：自动 clone
  expect(answer.finalText).toContain("- 我用 pnpm");
});
```

另外三个场景：

| 场景 | 期望 |
|---|---|
| 两台机器改**不同**文件，desktop 落后 | `syncAfterTurn` 自动 rebase 后 `pushed`，desktop 的历史里有 laptop 的提交 |
| 两台机器改**同一行** | laptop `pushed`；desktop `conflict`，工作区干净、它自己的提交仍在最上面；下一回合用户消息里出现 `MEMORY GIT CONFLICT` |
| laptop 上反思时，desktop 已经推了新内容 | 反思先刷新再合并：`human.md` 同时有 desktop 的“我用 pnpm”和反思得出的“tabs”；desktop 下一回合也知道“tabs” |

### 踩坑记录：克隆下来的仓库“全都被改过”

第一次跑这组测试，desktop 刚克隆完，`git status` 就是：

```text
 M MEMORY.md
 M human.md
 M persona.md
```

而它的第一次提交被 hook 拒绝：`human.md: missing frontmatter (must start with ---)`。原因是第 16 章那个全局 `core.autocrlf=true`：`git clone` 按全局配置检出了 CRLF 文件；我们随后才设置仓库级 `core.autocrlf=false`——于是 git 认为工作区和索引不一致；而 frontmatter 校验看到的第一行是 `---\r`。修复：把配置放进 clone 本身。

```ts
// code/mini-letta @ v1.0  src/sync/remote.ts
gitOrThrow(join(memoryDir, ".."), [
  "clone", "-q", "--config", "core.autocrlf=false", "--config", "core.eol=lf", url, memoryDir,
]);
```

letta-code 的 `cloneMemoryRepo()` 用的是 `git clone url .`（`memory-git.ts:1512`），没有传这类配置；我们没有在 Cloud 环境里验证它在 `autocrlf=true` 的机器上的表现，但根据第 16 章的探针，这是一个值得检查的地方。

还有一个更小的坑：hook **不会**被克隆（`.git/hooks` 不在版本控制里），所以克隆之后必须重新安装——letta-code 在 clone、pull、init 三处都调用 `installMemoryGitHooks()` 正是为此（Lab 2 练习 3）。

### 端到端

`scripts/e2e.ts` 把整个故事串起来跑（离线、mock 模型、内核沙箱开启）：

```text
✓  1 remember → tool call → committed  — 好的，我已经把这件事记进记忆里了。
✓  2 commit is on the remote
✓  3 persona change visible next turn (same conversation)  — （mock）我听到了：你好 🦉
✓  4 long conversation compacted  — 5 compactions
✓  5 compaction-triggered reflection merged a preference  — 1 merged
✓  6 human.md now has the preference
✓  7 recall brings back an evicted detail  — 我在过去的对话里找到了：我们的数据库端口是 5433，别用默认的 5432 🦉
✓  8 the other machine cloned the memory  — 我记得关于你的这些：
- 我叫小陆，主要写 TypeScript
- 我更喜欢用 tabs 缩进 🦉
✓  9 another agent's shell cannot see agent-e2e's memory  — cat: …/agents/agent-e2e/memory/human.md: No such file or directory

all good
```

第 8 步：desktop 从没参与过任何一次对话，它第一次被问到时就知道 laptop 上的用户说过什么、laptop 上的反思总结出了什么。

## 18.6 设计取舍

- **每回合都拉、都推**：简单、延迟低；代价是每回合几次本地/网络 git 调用。letta-code 的推送拿不到锁时直接跳过（第 17 章），不阻塞用户。
- **冲突时不自动解决**：letta-code 交给修复 worker（一个 LLM，按“读两边、保留意图”的规则），mini-letta 交给主 agent 的下一回合。两者都不会自动选边——记忆冲突往往是语义冲突（“用 bun” vs “用 yarn”），没有正确的机械解法。
- **只推 main**：反思和 worker 的临时分支永远不离开本机。

## 18.7 练习

1. **巩固**：用两个终端、两个 `MINI_LETTA_HOME` 和同一个 `MINI_LETTA_REMOTE_ROOT` 手动重现“同一行冲突”，看提醒文本；然后按提醒里的命令手动解决冲突。
2. **扩展**：实现 letta-code 的“镜像仓库”：一个 post-commit hook，读取 `mini-letta.memoryRepository.url`，在后台推送到它，只推 `main`，失败写日志。
3. **读源码**：`syncPendingMemoryCommitsAfterTurn()` 在 rebase 之后会**再做一次**校验（`invalidPendingMemory`，`memory-git.ts:1943`）。为什么 rebase 之前校验过还不够？
