# Lab 2 mini-letta v0.2：记忆变成 git 仓库

> 目标：把 v0.1 的 JSON 记忆块换成 MemFS——每个 agent 一个 git 仓库、v2 布局、通用的文件/bash 工具、一个嵌入校验函数源码的 pre-commit hook，以及“只从 HEAD 编译”。前置：第 4–7 章。完成后：`git checkout v0.2`。

## L2.1 改动一览

```bash
cd code/mini-letta
git diff v0.1 v0.2 --stat
```

```text
 package.json                    |   2 +-
 src/agent/loop.ts               |  23 ++++++--
 src/cli.ts                      |  23 ++++++--
 src/llm/mock.ts                 |  23 +++++---
 src/memory/compile.ts           |  76 ++++++++++++++++++------
 src/memory/constraints.ts       | 106 ++++++++++++++++++++++++++++++++++
 src/memory/format.ts            |  40 +++++++++++++
 src/memory/frontmatter.ts       |  56 ++++++++++++++++++
 src/memory/git.ts               |  38 ++++++++++++
 src/memory/hooks.ts             |  87 ++++++++++++++++++++++++++++
 src/memory/memfs.ts             | 110 +++++++++++++++++++++++++++++++++++
 src/store/agent-store.ts        |  23 +++++---
 src/tools/file-tools.ts         | 101 ++++++++++++++++++++++++++++++++
 src/tools/memory-block-tools.ts |  62 --------------------
 src/tools/types.ts              |  13 +++++
 test/v01-blocks.test.ts         |  49 ----------------
 test/v02-memfs.test.ts          | 124 ++++++++++++++++++++++++++++++++++++++++
 17 files changed, 802 insertions(+), 154 deletions(-)
```

主要变化：`AgentRecord` 去掉 `blocks`；新增 `src/memory/` 下六个文件；工具从两个记忆块工具换成通用的 `bash/read_file/write_file/edit_file`。

## L2.2 步骤

**1. 记忆仓库的位置与初始化**（`src/memory/memfs.ts`，第 4、6 章）。`createAgent()` 在保存 `agent.json` 之后调用 `initMemoryRepo()`：`git init -b main`、写本地 `user.name/email`、安装 hook、写入初始文件、一次提交。`AgentRecord` 里不再有 `blocks`。

**2. 路径规则**（`src/memory/format.ts`，第 5 章）。

**3. 三个自包含的校验函数**（第 7 章）。写的时候时刻记住“这段源码要被 `toString()` 嵌进 hook”：函数体内不能引用外部的 import，只能用参数和全局对象。`isProjectedMemoryPath` 里调用了 `normalizeMemoryPath`，所以 validator 脚本里要单独定义一份同名函数。

**4. hook**（`src/memory/hooks.ts`）。`pre-commit` 只有一行：用当前运行时（`process.execPath`，即 bun）执行 `$(git rev-parse --git-common-dir)/hooks/mini-letta-validate.js`。

**5. 工具**（`src/tools/file-tools.ts`）。`bash` 的环境里带上 `MEMORY_DIR`、`AGENT_ID`、`AGENT_NAME`；文件工具只接受**绝对路径**——和 letta-code 一样，`$MEMORY_DIR` 在文件工具里不会被展开（letta-code 系统提示：“`$MEMORY_DIR` is a shell environment variable: it expands inside bash commands, but file tools take literal paths”，`letta_root_memfs.md:24`）。

**6. 编译只读 HEAD**（`src/memory/compile.ts`）。v0.2 仍然每一步都重编译，但内容来自 `git show HEAD:<path>`。

**7. mock 的“记住”**。从调用 `memory_append` 改为一条 bash 命令：

```ts
// src/llm/mock.ts（v0.2）
return callTool("bash", {
  command: [
    'cd "$MEMORY_DIR"',
    `printf '%s\\n' ${shellQuote(`- ${fact}`)} >> human.md`,
    "git add human.md",
    `git commit -q -m ${shellQuote("chore: remember user fact")} -- human.md`,
    "git log --oneline -1",
  ].join(" && "),
});
```

注意 `shellQuote`：用户说的话会被拼进 shell 命令，单引号必须转义（`'` → `'\''`）。mock 是确定性的，但它生成的命令一样要经得起“用户输入里有引号”。

## L2.3 运行与验证

```bash
bun test test/v02-memfs.test.ts
```

v0.2 的测试覆盖：路径规则、frontmatter、树约束、新 agent 的初始提交（作者 `mini-letta <agent-a@mini-letta.local>`）、hook 拒绝/接受、配置保护、“只有已提交的才算数”、端到端的“记住→下一回合知道”。

手动走一遍：

```text
$ export MINI_LETTA_HOME=$(mktemp -d)
$ bun src/cli.ts chat -p "记住：我叫小陆，写 TypeScript，用 pnpm"
  ⚙ bash({"command":"cd \"$MEMORY_DIR\" && printf '%s\\n' '- 我叫小陆，写 TypeScript，用 pnpm' >> human.md && git add human.md && git commit -q -m 'chore: remember user fact' -- human.md && git log --oneline -1"})
  ✓ 839a6c6 chore: remember user fact
好的，我已经把这件事记进记忆里了。
$ bun src/cli.ts chat -c c2 -p "你知道我什么？"
我记得关于你的这些：
- 我叫小陆，写 TypeScript，用 pnpm
$ bun src/cli.ts memory log
839a6c6 (HEAD -> main) chore: remember user fact
46d527b chore: initialize local memory
$ cd "$(bun src/cli.ts memory path)" && printf 'oops\n' > notes.md && git add notes.md && git commit -m "add notes"
Memory validation failed:
  notes.md: missing frontmatter (must start with ---)
```

## L2.4 和真模型一起跑

v0.1 里 `qwen2.5:3b` 能正确调用 `memory_append`；换成“用 bash 改文件再提交”之后，它用 `write_file` 把 `human.md` 覆盖坏了，并声称已经提交（第 6 章踩坑记录）。这不是 mini-letta 的 bug，而是**工具抽象层次**的真实代价：MemFS 把“写记忆”从一个窄工具变成了“通用文件操作 + git”，对模型的能力要求高得多。letta-code 的应对是多层的：详细的提示词（第 10 章）、hook（第 7 章）、回合后提醒（第 9 章）、以及把大部分记忆维护交给后台反思（第 15 章）。

## L2.5 练习

1. **巩固**：给 CLI 加一个 `memory show <path>` 子命令，打印 `git show HEAD:<path>`。
2. **扩展**：hook 现在只校验 `.md`。加一条规则：记忆仓库里不允许出现大于 1 MB 的文件（任何类型），并写测试。
3. **读源码**：letta-code 的 `installMemoryGitHooks()`（`src/agent/memory-git-hooks.ts:294`）在 clone、pull、init 时都会重新安装 hook。为什么不能只在初始化时装一次？（提示：`.git/hooks` 会不会被 clone？CLI 升级后 hook 的内容会不会变？）
