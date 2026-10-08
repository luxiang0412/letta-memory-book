# 附录 A 源码地图

> 概念 → letta-code（`70ead335`）中的位置 → mini-letta（`v1.0`）中的对应物。行号均在该提交上核对过。

## A.1 路径与布局

| 概念 | letta-code | mini-letta |
|---|---|---|
| 本地后端存储根 | `src/utils/local-backend-paths.ts:19` `getLocalBackendStorageDir` | `src/store/paths.ts` `getHome`（`MINI_LETTA_HOME`） |
| 本地记忆仓库路径 | `src/backend/local/paths.ts:48` | `src/memory/memfs.ts` `getMemoryDir` |
| Cloud 检出路径 | `src/agent/memory-filesystem.ts:46` `getMemoryFilesystemRoot` | — |
| 当前作用域的记忆目录 | `src/agent/memory-filesystem.ts:100` `resolveScopedMemoryDir` | `ToolContext.memoryDir` |
| 本检出的 git 目录 | `src/agent/memory-git-dir.ts:11` `getMemoryGitDir` | `src/memory/git.ts` `gitDir` |
| v1/v2 判定 | `src/agent/memory-format.ts:6` `detectMemoryFormat` | 只支持 v2 |
| core 路径 | `src/agent/memory-format.ts:13` `isCoreMemoryPath` | `src/memory/format.ts` |
| 被投影的路径 | `src/agent/memory-format.ts:23` `isProjectedMemoryPath` | `src/memory/format.ts` |
| MemFS 是否启用 | `src/agent/memory-runtime.ts:13` | 总是启用 |
| 后端能力 | `src/backend/backend.ts:169` `BackendCapabilities` | — |

## A.2 记忆的诞生

| 概念 | letta-code | mini-letta |
|---|---|---|
| 默认块 | `src/agent/memory.ts:16`、`src/agent/prompts/{persona,human}.mdx` | `src/store/agent-store.ts` `DEFAULT_BLOCKS` |
| 根 `MEMORY` 块 | `src/agent/create-agent-request.ts:44` | `src/memory/memfs.ts` `ROOT_MEMORY_INDEX` |
| 块 → 文件 | `src/backend/local/initial-memory.ts:41, 82` | `src/memory/memfs.ts` `initialMemoryFiles` |
| 初始化仓库 | `src/agent/memory-git.ts:1316` `initializeLocalMemoryRepo` | `src/memory/memfs.ts` `initMemoryRepo` |
| 本地仓库配置修正 | `src/agent/memory-git.ts:1136` | 同上（user、autocrlf、eol） |
| 关闭签名 | `src/agent/memory-git.ts:1151-1155`、`src/agent/memory-git-signing.ts:13` | — |
| harness 写入 | `src/agent/memory-git.ts:1184, 1234` | `src/memory/memfs.ts` `commitMemoryPaths` |

## A.3 守门员

| 概念 | letta-code | mini-letta |
|---|---|---|
| frontmatter 规则 | `src/memory-frontmatter.ts:18` | `src/memory/frontmatter.ts` `validateMemoryFile` |
| frontmatter 解析 | `src/utils/frontmatter.ts:73` | `src/memory/frontmatter.ts` `parseFrontmatter` |
| 树约束 | `src/memory-constraints.ts:39` | `src/memory/constraints.ts` `validateMemoryTree` |
| 默认预算 | `src/memory-constraints.ts:302` | `DEFAULT_MEMORY_CONSTRAINTS` |
| 配置保护 | `src/agent/memory-constraints.ts:32, 132-146` | validator 脚本内 |
| pre-commit 生成 | `src/agent/memory-git-hooks.ts:38` | `src/memory/hooks.ts` |
| 嵌入函数源码 | `src/agent/memory-git-hooks.ts:90` | `buildValidatorScript` |
| 布局策略文件 | `src/agent/memory-git-hooks.ts:21, 224` | — |
| 安装 hook | `src/agent/memory-git-hooks.ts:294` | `installMemoryHooks` |
| 审计 HEAD | `src/agent/memory-constraints-audit.ts:52, 107` | `src/memory/audit.ts` |

## A.4 编译与缓存

| 概念 | letta-code | mini-letta |
|---|---|---|
| 编译入口 | `src/backend/local/system-prompt-compilation.ts:432` | `src/memory/compile.ts` `compileSystemPrompt` |
| 已提交版本号 | `…/system-prompt-compilation.ts:65` | `src/memory/git.ts` `headRevision` |
| 读已提交文件 | `…/system-prompt-compilation.ts:81` | `readCommittedMemory` |
| v2 渲染 | `…/system-prompt-compilation.ts:154` | `renderCoreMemory` |
| v1 渲染 | `…/system-prompt-compilation.ts:305` | — |
| 元信息（v1） | `…/system-prompt-compilation.ts:364` | agent-info 提醒代替 |
| 注入 | `…/system-prompt-compilation.ts:380` | `injectCoreMemory` |
| 技能列表 | `…/system-prompt-compilation.ts:391` | — |
| 按对话缓存 | `src/backend/local/local-backend.ts:896` | `src/agent/system-prompt.ts` `resolveSystemPrompt` |
| `<memory_update>` 文案 | `src/backend/local/local-backend.ts:165` | `src/agent/reminders.ts` `formatMemoryUpdate` |
| `<memory_update>` 注入 | `src/backend/dev/pi-stream-adapter.ts:595` | `src/agent/loop.ts`（持久化的 user 提醒） |
| `/recompile` | `src/cli/commands/registry.ts:411` | `bun src/cli.ts recompile` |
| 提示词选择 | `src/agent/personality.ts:112`、`src/agent/prompt-assets.ts` | `DEFAULT_SYSTEM_PROMPT` |
| 提示词 | `src/agent/prompts/letta_root_memfs.md`、`letta_local_memfs.md` | — |

## A.5 提醒

| 概念 | letta-code | mini-letta |
|---|---|---|
| 回合后同步 + 提醒 | `src/reminders/memory-git-sync.ts:58, 162` | `checkMemoryAfterTurn`、`formatSyncReminder` |
| 修复进行中提醒 | `src/reminders/memory-git-sync.ts:40` | — |
| agent-info | `src/cli/helpers/agent-info.ts` | `formatAgentInfo` |
| 调用点（三条路径） | `src/headless.ts:3097/4742`、`src/cli/app/use-submit-handler.ts:3746`、`src/websocket/listener/turn-cleanup.ts:51` | `src/agent/loop.ts` |

## A.6 上下文与 recall

| 概念 | letta-code | mini-letta |
|---|---|---|
| token 估算 | `src/backend/local/local-context-estimate.ts:79, 164` | `src/context/tokens.ts` |
| 压缩阈值 | `src/backend/dev/provider-turn-executor.ts:34, 241, 262` | `src/context/compaction.ts` `compactionThreshold` |
| 地板检查 | `src/backend/dev/provider-turn-executor.ts:215`、`pi-stream-adapter.ts:361` | — |
| 请求前检查 | `src/backend/dev/pi-stream-adapter.ts:562` | `src/agent/loop.ts` |
| 滑动窗口规划 | `src/backend/local/compaction.ts:584` | `planSlidingWindow` |
| 全量规划 | `src/backend/local/compaction.ts:652` | `planAll` |
| 摘要提示词 | `src/backend/local/compaction.ts:61, 85` | `SLIDING_WINDOW_SUMMARY_PROMPT` |
| 摘要截断 | `src/backend/local/compaction.ts:544` | `clipSummary` |
| 摘要包装 | `src/backend/local/compaction.ts:682` | `packageSummary` |
| 压缩编排 | `src/backend/local/local-backend.ts:727` | `src/context/compact-conversation.ts` |
| 上下文 id 列表 | `src/backend/local/local-store.ts:1157, 1201` | `ConversationStore.inContext/setContext` |
| 摘要消息类型 | `src/backend/local/local-message-projection.ts:196` | `Message.kind = "summary"` |
| 检索 | `src/backend/local/transcript-search.ts:523` | `src/recall/search.ts` |
| 分词 / 词频 / BM25 | `…/transcript-search.ts:229, 258, 317` | `tokenize`、`termFrequency`、`searchRecall` |
| 问题降权 | `…/transcript-search.ts:570-583` | `latestUser` |
| recall 子 agent | `src/agent/subagents/builtin/recall.md`、`src/agent/prompts/recall_subagent_local.md` | `recall_search` 工具 |

## A.7 反思

| 概念 | letta-code | mini-letta |
|---|---|---|
| 触发器类型 | `src/reflection-settings.ts:1` | `ReflectionTrigger` |
| 默认设置 | `src/cli/helpers/memory-reminder.ts:15, 51` | `DEFAULT_REFLECTION_SETTINGS` |
| 回合后判断 | `src/cli/helpers/post-turn-reflection.ts:22` | `src/reflection/post-turn.ts` |
| transcript 与状态 | `src/cli/helpers/reflection-transcript.ts:28, 911, 927` | `src/reflection/transcript.ts` |
| 构造 payload | `…/reflection-transcript.ts:1644` | `buildReflectionPayload` |
| 推进水位线 | `…/reflection-transcript.ts:1870` | `markReflected` |
| 多对话 payload | `…/reflection-transcript.ts:1756` | — |
| 启动器 | `src/cli/helpers/reflection-launcher.ts:769` | `src/reflection/launcher.ts` |
| 预留 / 排队 | `…/reflection-launcher.ts:286` | `reflection.lock` |
| 重试退避 | `src/cli/helpers/reflection-retry.ts` | — |
| 任务提示 | `src/cli/helpers/reflection-prompt.ts:9` | `buildReflectionTaskPrompt` |
| 父记忆快照 | `src/cli/helpers/reflection-memory-v2.ts:43` | 编译 worktree HEAD |
| 子 agent 提示词 | `src/agent/subagents/builtin/reflection-v2.md` | `REFLECTION_SYSTEM_PROMPT` |
| 显式集成 | `…/reflection-launcher.ts:458` | — |

## A.8 worktree、锁、worker

| 概念 | letta-code | mini-letta |
|---|---|---|
| 创建 worktree | `src/agent/memory-worktree.ts:125` | `src/reflection/worktree.ts` `createMemoryWorktree` |
| 作用域 | `src/agent/memory-worktree.ts:191` | `src/agent/sandbox-profiles.ts` `reflectionProfile` |
| 状态枚举 | `src/agent/memory-worktree.ts:215` | `FinalizeStatus` |
| 消费 / 重编译判定 | `src/agent/memory-worktree.ts:235, 241` | `consumesTranscript` |
| 刷新父仓库 | `src/agent/memory-worktree.ts:275` | `src/sync/remote.ts` `refreshFromOrigin` |
| 收尾状态机 | `src/agent/memory-worktree.ts:363, 659` | `finalizeMemoryWorktree` |
| worker 合并 | `src/agent/memory-worktree.ts:685` | — |
| 记忆操作锁 | `src/agent/memory-operation.ts:20, 35` | `src/utils/file-lock.ts` |
| memory worker | `src/agent/subagents/memory-worker.ts`、`builtin/memory.md` | — |
| 冲突修复 | `src/agent/memory-conflict-repair.ts:161` | — |

## A.9 同步

| 概念 | letta-code | mini-letta |
|---|---|---|
| 远端 URL | `src/agent/memory-git.ts:228` | `src/sync/remote.ts` `remoteUrlFor` |
| 认证参数 | `src/agent/memory-git.ts:483` | — |
| 非交互环境 | `src/agent/memory-git.ts:533` | — |
| 重试 | `src/agent/memory-git.ts:632` | — |
| clone / pull | `src/agent/memory-git.ts:1504, 1589` | `cloneMemory`、`pullMemory` |
| 回合后推送 | `src/agent/memory-git.ts:1837` | `syncAfterTurn` |
| 镜像仓库 hook | `src/agent/memory-git-hooks.ts:254, 280` | — |

## A.10 隔离与观察

| 概念 | letta-code | mini-letta |
|---|---|---|
| 开关 | `src/sandbox/availability.ts:65, 88` | `src/sandbox/policy.ts` |
| bwrap 探测 | `src/sandbox/availability.ts:155` | `isBwrapAvailable` |
| bwrap 参数 | `src/sandbox/bwrap.ts:38` | `buildBwrapArgs` |
| 两种策略 | `src/permissions/sandbox-policy.ts:255, 312` | `src/agent/sandbox-profiles.ts` |
| 进程内守卫 | `src/permissions/cross-agent-guard.ts:387` | `assertNotOtherAgentsMemory` |
| 整进程封装 | `src/memory-confinement.ts:22` | — |
| Memory Palace | `src/web/generate-memory-viewer.ts`、`registry.ts:139` | `src/palace/*` |
| 反思提交识别 | `src/web/generate-memory-viewer.ts:295` | `history()` 的 `isReflection` |
| /doctor | `registry.ts:77`、`src/skills/builtin/context-doctor/SKILL.md` | — |
| 遥测 | `src/cli/helpers/reflection-launcher.ts:170, 188` | — |
