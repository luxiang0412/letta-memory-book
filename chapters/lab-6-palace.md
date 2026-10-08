# Lab 6 mini-letta v1.0：多机同步、隔离、Palace 与部署

> 目标：远端同步（bare 仓库服务器）、跨 agent 隔离（路径守卫 + bwrap）、提交审计、Memory Palace、演示与端到端脚本、Docker Compose 部署。演示：两台“机器”共享一个 agent 的记忆，另一个 agent 的 shell 看不到它，Palace 能看到一切。前置：第 18–20 章。完成后：`git checkout v1.0`。

## L6.1 改动一览

```text
$ git diff v0.5 v1.0 --stat
 .dockerignore                 |   3 +
 Dockerfile                    |   9 +++
 README.md                     |  71 +++++++++++++++++
 compose.yaml                  |  31 ++++++++
 package.json                  |   6 +-
 scripts/demo.ts               |  79 +++++++++++++++++++
 scripts/e2e.ts                | 100 ++++++++++++++++++++++++
 src/agent/loop.ts             |  21 +++++
 src/agent/reminders.ts        |  42 ++++++++++
 src/agent/sandbox-profiles.ts |  33 ++++++++
 src/cli.ts                    |  17 ++++-
 src/llm/provider.ts           |  14 +++-
 src/memory/audit.ts           |  51 +++++++++++++
 src/memory/frontmatter.ts     |  14 +++-
 src/memory/git.ts             |  10 +++
 src/palace/data.ts            | 141 ++++++++++++++++++++++++++++++++++
 src/palace/page.ts            | 173 ++++++++++++++++++++++++++++++++++++++++++
 src/palace/server.ts          |  54 +++++++++++++
 src/reflection/launcher.ts    |   8 ++
 src/reflection/worktree.ts    |   6 ++
 src/sandbox/policy.ts         |  92 ++++++++++++++++++++++
 src/store/agent-store.ts      |  31 ++++++--
 src/sync/remote.ts            | 131 ++++++++++++++++++++++++++++++++
 src/tools/file-tools.ts       |  23 +++---
 src/tools/types.ts            |   3 +
 test/v02-memfs.test.ts        |  22 +++++-
 test/v03-compile.test.ts      |  33 ++++++++
 test/v10-isolation.test.ts    |  90 ++++++++++++++++++++++
 test/v10-palace.test.ts       |  43 +++++++++++
 test/v10-sync.test.ts         |  97 +++++++++++++++++++++++
 tsconfig.json                 |   3 +-
 31 files changed, 1419 insertions(+), 32 deletions(-)
```

`v1.0` 这个 tag 在写书过程中**移动过四次**：每次对照 letta-code、或者在写练习答案时发现 mini-letta 的缺口，都修好（大多带着回归测试）再把 tag 挪过去：

```text
$ git log --oneline v0.5..v1.0
66f6457 feat: MINI_LETTA_REFLECTION_CONTEXT_WINDOW gives the reflection subagent its own window
d213450 fix: audit HEAD once per revision at turn start and end; locate the per-checkout git dir
298a675 fix: parseFrontmatter strips BOM, normalizes CRLF and trims the body like letta-code
769555a fix: audit committed memory after turns — catches hook-bypassing (--no-verify) commits
d8cb78d v1.0: remote sync, cross-agent isolation (guard + bwrap), Memory Palace, demo/e2e scripts, Docker compose
```

它们的故事分别在第 7 章（`--no-verify` 与回合之间的提交）、第 8 章（和 letta-code 编译器对拍）和附录 D 的 Lab 4 答案（小窗口下反思永远失败）。

## L6.2 步骤

1. **同步**（`src/sync/remote.ts`，第 18 章）：`remoteUrlFor`、`attachRemote`、`cloneMemory`（带 LF 配置）、`pullMemory`、`syncAfterTurn`、`refreshFromOrigin`；`ensureMemoryCheckout` 决定“克隆还是新建”；循环在回合前拉、回合后推；反思合并前刷新、合并后推送。
2. **隔离**（`src/sandbox/policy.ts`、`src/agent/sandbox-profiles.ts`，第 19 章）：tri-state 开关、bwrap 探测与参数、两种配置、进程内守卫；`ToolContext.sandbox`；`bash` 用 `wrapCommand`。
3. **审计**（`src/memory/audit.ts`，第 7 章）：临时 `GIT_INDEX_FILE` 读 HEAD、跑同一个 validator；每个 revision 审计一次；`gitDir()`。
4. **Palace**（`src/palace/*`，第 20 章）。
5. **脚本**：`scripts/demo.ts` 生成演示状态；`scripts/e2e.ts` 跑完整故事（可选地检查一个运行中的 Palace）。
6. **部署**：`Dockerfile`（`oven/bun:1.3.11` + git）、`compose.yaml`（`seed` → `palace` → 可选的 `e2e`）。

## L6.3 本机验证

```bash
bun test                    # 50 pass
bun run typecheck
bun run check:cycles        # ✔ No circular dependency found!
bun scripts/e2e.ts
```

`e2e.ts` 的输出见第 18 章 18.5 节（本机有 bwrap，第 9 步是真正的内核隔离检查）。

Palace：

```bash
export MINI_LETTA_HOME=$(mktemp -d)
bun scripts/demo.ts
bun src/cli.ts palace --port 8787     # 打开 http://127.0.0.1:8787/
```

`demo.ts` 的真实输出（节选）：

```text
[main] <memory_update> injected
好的，我已经把这件事记进记忆里了。
[main] <memory_update> injected
[main] compaction 9→6
[main] reflection no_changes
好的，我已经把这件事记进记忆里了。 🦉
（mock）我听到了：我们的数据库端口是 5433，别用默认的 5432 🦉
[main] compaction 18→13
[main] reflection merged
[main] <memory_update> injected
...
我在过去的对话里找到了：我们的数据库端口是 5433，别用默认的 5432 🦉
我记得关于你的这些：
- 我叫小陆，主要写 TypeScript
- 我更喜欢用 tabs 缩进 🦉

* a006921 chore(reflection): remember 1 user preference(s) 🔮
* 1bb9269 feat: update persona
* 20dfc8a chore: remember user fact
* 8b545e2 feat: index projects and add release-notes skill
* 55631fc chore: initialize local memory
```

（第一版 `demo.ts` 里每一次反思都是 `failed`——反思者和主 agent 共用 1 400 token 的小窗口，把自己刚读的 transcript 压缩掉了，见第 15 章踩坑记录 3。）

## L6.4 Docker Compose 部署

```yaml
# compose.yaml（节选）
services:
  seed:   { build: ., command: ["bun", "scripts/demo.ts"], volumes: [data:/data, remote:/remote] }
  palace:
    build: .
    depends_on: { seed: { condition: service_completed_successfully } }
    ports: ["8787:8787"]
    healthcheck:
      test: ["CMD", "bun", "-e", "fetch('http://127.0.0.1:8787/healthz').then(r => process.exit(r.ok ? 0 : 1))"]
  e2e:
    build: .
    profiles: [test]
    command: ["bun", "scripts/e2e.ts"]
    depends_on: { palace: { condition: service_healthy } }
    environment: { MINI_LETTA_REMOTE_ROOT: /remote, PALACE_URL: http://palace:8787 }
```

```bash
docker compose up -d --build
curl -s localhost:8787/api/agents
docker compose --profile test run --rm e2e
```

在 `v1.0` 上实际运行的结果（提交号每次运行都不同；最后一次 tag 移动后重跑，十步全部通过）：

```text
{"ok":true}
[{"id":"agent-demo","name":"mini-letta","head":"bb00dd9","commits":5,"conversations":2}]

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
! bwrap unavailable here (e.g. inside Docker): shells run unconfined, isolation check skipped
✓  9 Palace serves the agent  — {"id":"agent-e2e","name":"mini-letta","head":"b19a5cb","commits":4,"conversations":1}
✓ 10 Palace shows a reflection commit

all good
```

e2e 容器和 Palace 容器共享 `data` 卷：e2e 新建的 `agent-e2e` 立刻出现在 Palace 的接口里（第 9、10 步）。

## L6.5 收尾

```bash
docker compose down -v      # 停掉并删除卷
```

## L6.6 练习

1. **巩固**：在 compose 里加第二个“机器”服务（另一个 `MINI_LETTA_HOME` 卷、同一个 `remote` 卷），让它对 `agent-demo` 说一句“你知道我什么？”。
2. **扩展**：把 bubblewrap 装进镜像，并用 `docker run --security-opt seccomp=unconfined --cap-add SYS_ADMIN …` 之类的方式让探测通过。哪些放宽是必须的？这对“在容器里跑多租户 agent”意味着什么？
3. **读源码**：letta-code 的 `/palace` 生成的是静态文件，mini-letta 起的是服务器。比较两者在“数据新鲜度”“安全面”“部署”上的取舍。
