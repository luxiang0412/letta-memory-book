# 第 19 章 记忆安全：跨 agent 隔离、沙箱与密钥

> 本章目标：理解同一台机器上多个 agent 的记忆如何互相隔离——进程内路径守卫、内核沙箱（bubblewrap）、两种沙箱配置、以及为什么 agent 自己的 shell 默认**不**被沙箱化。前置：第 15–17 章。对应代码：mini-letta `v1.0` `src/sandbox/policy.ts`、`src/agent/sandbox-profiles.ts`。

## 19.1 威胁模型

一台机器上可能跑着很多 agent：一个 app server 托管几十个用户的 agent；一个实验平台批量跑 agent；或者只是你自己的“工作 agent”和“生活 agent”。每个 agent 的记忆都是一个普通目录，任何进程都能读。

要防的是：**agent A 读到或改掉 agent B 的记忆**——无论是模型自己“好奇”去翻，还是被提示注入诱导，还是 bug。letta-code 的 CLAUDE.md 用一句话定义了目标：“OS-level filesystem sandboxing prevents agents sharing one machine from reading or writing each other's memory.”

## 19.2 三个执行面

CLAUDE.md 的 “Filesystem Sandbox” 一节列出了三处需要设防的地方：

| 执行面 | 怎么防 | 默认 |
|---|---|---|
| agent 的 shell 命令（Bash） | 每条命令包一层内核沙箱：拒绝整个 agents 目录树，把自己的目录挖回来 | **关**（`LETTA_FS_SANDBOX=1` 打开） |
| 记忆子 agent（reflection、memory、init） | **整个进程**包进沙箱：广泛可读，只能写自己的记忆 | **开**（`LETTA_FS_SANDBOX=0` 关闭） |
| 进程内的文件工具（Read/Edit/Write…） | 它们不 fork，内核沙箱看不见——用静态的路径守卫 | 开 |

tri-state 的语义写在 `src/sandbox/availability.ts:52-93`：

```text
unset → memory subagents sandboxed; agent shells unconfined
1/true → both sandboxed
0/false → nothing sandboxed
```

### 为什么 agent 的 shell 默认不沙箱化？

注释给了一个很实在的理由（`availability.ts:74-81`）：

> It is **off by default**: an interactive agent's own shells walling off other agents' memory broke legitimate workflows (agents inspecting `~/.letta/agents`) with kernel `Operation not permitted` errors that no permission mode could approve through. Set `LETTA_FS_SANDBOX=1` (or `true`) to opt in — recommended for multi-tenant deployments.

安全与可用性的权衡：单用户的笔记本上，你自己的几个 agent 互相看看问题不大，而“内核拒绝、没有任何审批能放行”的错误非常让人困惑；多租户部署则必须打开。后台的记忆子 agent 无人值守、没有交互式审批可以兜底，所以默认就关进去。

## 19.3 bubblewrap：用挂载命名空间“让别人的记忆不存在”

Linux 上用 `bwrap` 构造一个挂载命名空间（`src/sandbox/bwrap.ts:38`）：

```ts
// src/sandbox/bwrap.ts:38-90（节选）
args.push(policy.restrictWrites ? "--ro-bind" : "--bind", "/", "/");   // 根：只读（记忆子 agent）或可写（跨 agent）
args.push("--dev", "/dev");
args.push("--proc", "/proc");
for (const root of policy.baseWritableRoots) args.push("--bind-try", root, root);
for (const root of policy.deniedRoots) args.push("--tmpfs", root);      // 用空的 tmpfs 盖住：不是“不可写”，是“不存在”
for (const root of policy.readonlyRoots) args.push("--ro-bind-try", root, root);
for (const root of policy.writableRoots) args.push("--bind-try", root, root);
args.push("--die-with-parent");
```

几个精妙之处（都写在那段长注释里）：

- **拒绝 = 用 tmpfs 覆盖**。其他 agent 的目录不是“读不了”，而是**根本看不见**——连目录名都枚举不到。
- **挂载顺序就是语义**：后挂的覆盖先挂的。所以先盖住整个 agents 树，再把自己的目录挂回来。
- **祖先挖洞的危险**：如果某个“挖回来”的可写路径是被拒绝目录的**祖先**（比如把 `/tmp` 设为可写，而 agents 树恰好在 `/tmp` 下），它会把整个子树重新挂上来，拒绝失效。所以记忆子 agent 的配置**故意不挖临时目录**——这就是第 15 章反思提示词里“临时文件放在 `$MEMORY_DIR/.tmp/`”那条规则的来历。
- **`-try` 变体**：可挖回的路径可能还不存在（比如懒创建的 `memory-worktrees`），普通 `--bind` 会让整个沙箱启动失败，`--bind-try` 则跳过。
- **不隔离网络**：只管文件系统。

可用性要**探测**而不是只看二进制在不在：用户命名空间可能被禁用（WSL1、某些加固过的主机、容器里），所以真的跑一次 `bwrap --ro-bind / / --unshare-user /bin/true`（`availability.ts:155`）。macOS 用 Seatbelt（`sandbox-exec`），Windows 用一个 C# 辅助程序（受限令牌 + 临时 ACL + Job Object）——同一套策略模型，三种后端。

### 两种配置

`src/permissions/sandbox-policy.ts` 里的两个构造函数：

| | `buildCrossAgentSandboxPolicy()`（`:312`） | `buildMemorySubagentSandboxPolicy()`（`:255`） |
|---|---|---|
| 用于 | agent 的 shell 命令 | 记忆子 agent 整个进程 |
| 根文件系统 | 可写（`restrictWrites: false`） | 只读 |
| agents 树 | 拒绝（读写） | 拒绝（读写） |
| 自己的目录 | 挖回可写 | agent 目录只读、记忆目录可写 |
| 其他可写 | 一切（仓库、home、tmp） | 只有 `~/.letta`（及搬到外面的 harness 目录） |

两个后端的 agents 树都要拒绝：`~/.letta/agents`（Cloud）和 `$LETTA_LOCAL_BACKEND_DIR/memfs`（本地）。

## 19.4 进程内守卫

Read/Edit/Write 是在 agent 进程里直接调用 `fs` 的，不 fork，内核沙箱管不到。`src/permissions/cross-agent-guard.ts` 给它们做静态检查，而且检查**两遍**：

```ts
// src/permissions/cross-agent-guard.ts:314-325（节选）
// The lexical pass preserves string-match behavior; the realpath pass follows symlinks so a
// link whose real target lands in another agent's memory can't slip past.
// Everything unions via the shared `agentIds` set — extra passes only add
// denials, never remove them.
const lexical = normalizePathForCompare(resolvedPath);
const real = canonicalizeRoot(resolvedPath);
```

字面路径一遍、解析符号链接后的真实路径一遍，任一命中就拒绝。被允许的只有自己和（子 agent 进程的）父 agent。文件头的注释还记录了一段历史：以前这个守卫也分析 shell 命令的文本，后来删掉了——“it was bypassable by symlinks, command substitution, globbing, and subprocesses”。**静态分析 shell 命令是守不住的，要么交给内核，要么不守。**

## 19.5 mini-letta 的实现

**策略与包装**（`src/sandbox/policy.ts`）：同样的 tri-state 开关（`MINI_LETTA_FS_SANDBOX`）、同样的挂载顺序、真实探测：

```ts
// code/mini-letta @ v1.0  src/sandbox/policy.ts（节选）
export function isBwrapAvailable(): boolean {
  bwrapAvailable ??=
    spawnSync("bwrap", ["--ro-bind", "/", "/", "--unshare-user", "/bin/true"], { timeout: 5_000 }).status === 0;
  return bwrapAvailable;
}

export function buildBwrapArgs(policy: SandboxPolicy): string[] {
  const args = [policy.restrictWrites ? "--ro-bind" : "--bind", "/", "/", "--dev", "/dev", "--proc", "/proc"];
  for (const root of policy.deniedRoots) args.push("--tmpfs", root);
  for (const root of policy.readonlyRoots) args.push("--ro-bind-try", root, root);
  for (const root of policy.writableRoots) args.push("--bind-try", root, root);
  args.push("--die-with-parent");
  return args;
}
```

**两种配置**（`src/agent/sandbox-profiles.ts`）：

- `crossAgentProfile(home, agentId)`：根可写，`<home>/agents` 盖住，`<home>/agents/<自己>` 挖回；
- `reflectionProfile(...)`：根只读，`<home>/agents` 盖住，payload 目录只读挖回，worktree 和主仓库的 `.git`（提交要写对象库和 worktree 元数据）可写挖回。

**接线**：`bash` 工具用 `wrapCommand(ctx.sandbox, command)`；`runTurn` 在 `MINI_LETTA_FS_SANDBOX=1` 时给主 agent 套跨 agent 配置；反思启动器在开关未关闭时给反思子 agent 套反思配置。和 letta-code 的区别：mini-letta 的反思子 agent 在同一进程里运行，所以“整个进程沙箱化”退化成了“它的每条 shell 命令沙箱化”，它的文件工具仍然只有进程内守卫保护。

**进程内守卫**（`assertNotOtherAgentsMemory()`）：字面路径和“最长存在前缀做 realpath”的路径各查一遍；`<parent>~reflection` 被视为替 `<parent>` 干活。

## 19.6 运行与验证

`test/v10-isolation.test.ts`（bwrap 不可用时内核相关的用例自动跳过）：

```ts
test("own memory readable, another agent's denied", async () => {
  expect(await readFileTool.run({ path: aliceHuman }, ctx())).toContain("alice's secret");
  await expect(readFileTool.run({ path: bobHuman }, ctx())).rejects.toThrow("belongs to agent 'agent-bob'");
});

test("a symlink inside my own tree cannot escape into another agent's", async () => {
  symlinkSync(bobHuman, join(agentDir(alice.id, home), "innocent.md"));
  await expect(readFileTool.run({ path: link }, ctx())).rejects.toThrow("belongs to agent 'agent-bob'");
});

bwrapTest("unconfined shell can read another agent's memory (the default trade-off)", async () => {
  expect(await bashTool.run({ command: `cat ${bobHuman}` }, ctx())).toContain("bob's secret");
});

bwrapTest("cross-agent profile: other agents are absent, own memory works", async () => {
  await expect(bashTool.run({ command: `cat ${bobHuman}` }, c)).rejects.toThrow("No such file or directory");
  expect(await bashTool.run({ command: `ls ${join(home, "agents")}` }, c)).toBe("agent-alice");   // 连 bob 的目录名都看不到
  expect(await bashTool.run({ command: 'cd "$MEMORY_DIR" && git log --oneline | wc -l' }, c)).toBe("1");
  expect(await bashTool.run({ command: "touch /tmp/mini-letta-sandbox-probe && echo ok" }, c)).toBe("ok");
});

bwrapTest("reflection profile: read-only everywhere except its worktree", async () => {
  expect(await bashTool.run({ command: `cat ${payload}` }, c)).toBe("[]");
  await expect(bashTool.run({ command: `echo x > ${join(payloadDir, "evil.json")}` }, c)).rejects.toThrow("Read-only file system");
  await expect(bashTool.run({ command: "touch /tmp/mini-letta-reflection-probe" }, c)).rejects.toThrow("Read-only file system");
  expect(await bashTool.run({ command: `touch ${join(worktreeDir, "ok.txt")} && echo ok` }, c)).toBe("ok");
});
```

第三个测试是故意的：它把“默认不隔离 shell”这个权衡写成了一条会跑的断言。

一个令人安心的事实：v1.0 加上沙箱之后，第 15、16 章的所有反思测试（默认就在反思配置的 bwrap 里运行）一个都没挂——反思需要的东西（读 payload、在 worktree 里提交、过 hook）都在挖回来的路径里。

在 Docker 里（Lab 6），我们的镜像没有安装 bubblewrap（即便装了，容器默认的 seccomp/权限设置也常常不允许非特权用户命名空间——这一点我们没有验证），探测失败，沙箱自动降级为不隔离，e2e 脚本打印一行警告并跳过隔离检查——和 letta-code 注释里“We intentionally continue rather than fail closed: users can still work, but should know filesystem isolation is degraded”（`availability.ts:98-100`）是同样的选择。

## 19.7 密钥与受保护内容

- **不存密钥**。系统提示：“Do not write credentials, API keys, or tokens into memory. Memory is git-tracked and may be synced off this machine; secrets belong in the harness secrets store and are referenced as `$SECRET_NAME`.”（`letta_root_memfs.md:34`）反思提示词的 Phase 4 也查这一条。但 letta-code 的 hook **不扫描**密钥（第 10 章的表格），这是一条只靠提示词的规则——练习 2。
- **受保护的文件与配置**：`read_only` 字段（v1）、`readOnlyFiles`（v2）、`.memfs.config.json` 本身需要人类批准才能改（第 7 章）。
- **远端认证不落盘**：每次命令临时注入 header，日志脱敏（第 18 章）。

## 19.8 练习

1. **巩固**：打开 `MINI_LETTA_FS_SANDBOX=1`，在 mini-letta 里创建两个 agent，让其中一个的 mock 执行 `ls $MINI_LETTA_HOME/agents`，看它能看到什么。
2. **扩展**：给 pre-commit validator 加一个密钥扫描：拒绝匹配 `sk-[A-Za-z0-9]{20,}`、`ghp_[A-Za-z0-9]{36}`、`-----BEGIN .* PRIVATE KEY-----` 的内容。误报怎么处理？要不要也走“需要人类批准”的环境变量？
3. **读源码**：`buildMemorySubagentSandboxPolicy()` 的注释提到一个 Seatbelt 的坑：如果进程 cwd 的**祖先**目录被拒绝读取，子进程会以**空环境变量**启动。letta-code 是怎么绕开它的？为什么跨 agent 配置要求“cwd 必须在 agents 树之外”？
