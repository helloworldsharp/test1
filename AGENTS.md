# 项目协作指南

## 项目概览

- 本仓库维护代理订阅转换所用的自定义规则和策略组配置。
- `rules5.ini` 是当前主配置入口；它组合上游公开规则集与本仓库通过 GitHub Raw URL 发布的 `.list` 文件。
- 本仓库没有构建脚本、自动测试或 CI。修改后的实际转换和代理行为仍需在使用该配置的订阅转换工具中验证。

## 目录与入口

- `rules5.ini`：当前规则集顺序、策略组和规则生成开关。
- `Direct.list`：补充直连规则。
- `ProxyLite.list`：补充代理规则。
- `IBKR.list`：Interactive Brokers 相关规则。
- `APPpush.list`：Apple 推送规则。
- `aloneip2.list`、`alonejp.list`：按源 IP 分流的独立规则。
- `backup/`：旧版配置和历史规则，仅供对照。除非任务明确指向旧版配置，否则不要把它当作当前入口，也不要同步修改。

## 核心工作流

1. 新增或修改根目录 `.list` 后，检查 `rules5.ini` 是否通过正确的 GitHub Raw URL 引用该文件。
2. 在 `rules5.ini` 中新增 `ruleset` 目标时，必须存在名称完全一致的 `custom_proxy_group`；修改名称时两处同步更新。
3. 保持规则集的匹配顺序。`[]FINAL` 必须继续作为最后的兜底规则，避免提前截获流量。
4. 保留 `enable_rule_generator=true` 和 `overwrite_original_rules=true` 的现有生成行为；只有用户明确要求改变转换方式时才能修改。
5. 若仓库名、默认分支或规则文件名发生变化，必须同步更新 `rules5.ini` 中对应的 GitHub Raw URL。

## 开发约定

- `.list` 文件使用一行一条 Clash 规则，说明文字使用以 `#` 开头的独立注释行。
- 延续文件现有规则类型和参数格式，例如 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-KEYWORD`、`IP-CIDR`、`SRC-IP-CIDR` 与 `no-resolve`。
- 修改规则时保持范围最小，不要顺手重排整个文件或批量清理历史内容。
- 添加规则前检查目标文件内是否已有相同条目。仓库当前存在少量历史重复规则；除非任务明确要求去重，否则不要扩大修改范围。
- 策略组名称包含 emoji 和空格时必须原样保留；不要仅为统一外观改名。

## Git 工作流

### 修改前

1. 运行 `git status -sb`。
2. 若有未提交修改：
   - 属于当前任务或可明确隔离时可以继续，但不得修改或暂存无关改动。
   - 与目标文件重叠、影响验证或无法判断时停止并说明。
3. 仅当工作区干净且当前分支已配置 upstream 时运行 `git pull --ff-only`。
   - 无 upstream 或处于 detached HEAD 时跳过并说明。
   - pull 失败时停止，不得擅自 merge、rebase 或 reset。
4. 默认使用当前分支。仅在大范围重构、实验性或高风险修改、多任务并行，或用户明确要求时新建分支。

### 修改后与 Commit

1. 执行与改动对应的静态检查和实际工具验证。
2. 检查 `git status -sb`、`git diff` 和 `git diff --check`。
3. 只暂存当前任务文件，然后检查 `git diff --cached`。
4. 验证通过、暂存内容准确且没有意外文件时，可以自动 commit。纯审阅、规划或未修改文件时不得 commit。
5. commit message 使用 `feat:`、`fix:`、`docs:`、`refactor:`、`test:` 或 `chore:` 前缀。

### Push

1. 仅当用户本次明确要求，或项目存在单独的长期授权时才能 push。
2. 只允许将当前分支推送到已有 upstream。
3. 禁止 force push、修改 remote/upstream 或推送标签。
4. 未 push 时在结束汇报中说明原因。

默认流程：

`status -> 条件性 pull -> 修改 -> 验证 -> diff/check -> 限定暂存 -> cached diff -> commit -> 授权后 push`

## 验证方法

修改 `.list` 文件后：

1. 忽略空行和 `#` 注释，检查新增行是否符合文件现有的 Clash 规则格式。
2. 检查目标文件内是否出现意外重复条目。
3. 若文件由 `rules5.ini` 引用，确认 Raw URL 中的文件名、仓库和分支仍正确。

修改 `rules5.ini` 后：

1. 确认每个 `ruleset` 的目标名称都有同名 `custom_proxy_group`。
2. 确认本仓库 Raw URL 指向实际存在且受 Git 管理的文件。
3. 确认 `[]FINAL` 仍位于规则集末尾，并检查策略组引用名称没有拼写或字符差异。
4. 在实际订阅转换工具中生成配置并检查结果；静态文本检查不能替代此步骤。

所有修改完成后运行：

```powershell
git diff --check
git status -sb
git diff
```

## 已知陷阱与保护规则

- `backup/` 中的配置可能引用当前根目录不存在的旧文件，不能据此推断当前 `rules5.ini` 的依赖关系。
- GitHub Raw URL 只有在相应修改提交并推送后才会对远程使用者生效；本地编辑成功不代表远程规则已经更新。
- 不要批量删除文件或目录。禁止使用 `del /s`、`rd /s`、`rmdir /s`、`Remove-Item -Recurse` 或 `rm -rf`。
- 需要删除文件时，只能一次删除一个明确路径的文件，例如 `Remove-Item "C:\path\to\file.txt"`。
- 如果任务需要批量删除文件，停止操作并请用户手动删除。
