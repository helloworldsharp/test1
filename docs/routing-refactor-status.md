# 分流重构验收记录

日期：2026-10-03（北京时间）。公共规则与 private dingyue 使用各自的 codex/routing-refactor branch 和独立 worktree；日常 main 工作区未修改。

## 已完成的本地交付

- 分组精简、BNQ/Bybit 显式隔离、国内域名/IP来源统一、Google/券商排除，以及全部第三方数据的受控生成。
- 28 个 generated provider、8 个个人 provider、18 个策略组；个人源文件保持不变。
- 更新器拒绝未知类型/异常空集/过量增删，冻结每轮来源 commit，失败不发布；连续两次下载生成的全部产物字节一致。
- dingyue 支持独立 rules root，校验本地规则构建期间未变，隔离 subconverter 副本；Stash 清理嵌套设备引用、处理默认选择并原子写入。HTTP 正文仍由客户端按 URL 下载。
- 已写 CI，包括日常更新候选、内核行为检查、故障注入和受限发布 job；默认未启用正式发布。

## 初始候选的历史验证

以下为独立审计前的记录，不代表后续修复已经进行现场或真实业务验收。

| 检查 | 结果与范围 |
| --- | --- |
| 公共更新器与发布 helper unit tests | 9 项通过；含下载失败、不完整候选、异常删除、hash 篡改、无关 staging 保护 |
| private dingyue ProjectVerifier | 92 项通过；含独立规则根、构建中规则变化、输入覆盖保护、subconverter 原配置保护、Stash 逻辑引用与默认顺序 |
| Mihomo v1.19.32 | 105 个 first-match 场景通过，全部 provider 加载条数与输入一致 |
| no-resolve | 2 个受控 DNS 场景通过；应跳过解析时没有查询，应解析时实际查询并命中对应 IP 规则 |
| 顺序故障注入 | 去掉 Bybit 排除、将设备规则前移，均能检出错误；只修改隔离测试配置 |
| 真实订阅缓存构建 | 经用户同意复用过期缓存后成功；原缓存、VPS 输入与 pref.toml hash 未变 |
| final 与 Stash | 离线校验及本地 Mihomo 语法检查通过；有 default-selected 的目标均存在于真实候选 |
| PowerShell 与 diff | UI 脚本语法及两个 repository 的 diff check 通过 |
| GitHub CI | [公共规则](https://github.com/helloworldsharp/test1/actions/runs/37037058447)与[Windows dingyue](https://github.com/helloworldsharp/proxy-rule-tools/actions/runs/37037049830)均通过；正式 publish job 为 skipped |
| 开发 branch 读回 | 两仓库 branch/upstream 已建立；36 个 provider 的 Raw 内容与公共 commit 字节一致，两个 main 未改变 |
| 旁路由现场内核 | 经授权隔离上传，alpha-g24b6de7 对真实候选的语法检查通过；独立进程加载全部 36 个 provider，条数与输入一致；活动配置 hash、原进程 PID/start tick 未变，测试进程与远端临时目录已清理 |

测试命令见更新器 README 和 private dingyue README。私密候选与本地完整日志保存在项目外 backups，不进入公共 repository。

## 独立审计后的修复与本地验证

修复基线：公共 `d46aa070`，private tools `b25d8861`。修复使用原 receipt 的 37 份公开来源字节，逐一核对 SHA-256；未混入本轮新上游数据。国内 6205 段 IPv4 范围完全不变，仅取消该分类路径的 no-resolve。首次迁移在隔离生成目录省略旧 IP 正文基线，以允许这次已审查的全量 flag 变化；正式更新器的删除阈值保持原值。

- 恢复未分类域名经 DNS 解析后的国内 IPv4 直连，并保持 Google/券商排除和设备优先级。
- 补回五个已复现的旧直连/下载范围，去除整个 `.ms` 国内分类，将 `msgamestudios.com` 放回游戏组。补充仅保留具体范围，尚未证明真实业务质量。
- 取消重复的 `china_exclusions`；Google 域名 provider 同时用于服务与国内排除。原 Google 4 段 IPv4、6 条 process 规则在 `google_non_domain` 保留，仍位于设备之后。8 个个人 provider 文件未改。
- final 的动态 URL 机制保持；构建显式提示本地正文未嵌入。不存在的 default-selected 在 final 与 Stash 转换前被拒绝，失败保留既有成功文件。

| 检查 | 修复后的结果与边界 |
| --- | --- |
| 回归先失败 | 修复前内核新增用例检出 31 个错误决策；工具新增用例检出默认节点漏检与缺少正文提示 |
| 公共 unit tests | 10 项通过，包括仅显式国内 IP 来源启用解析，其他来源 no-resolve 保持 |
| private ProjectVerifier | 95 项通过；新增缺失默认候选失败保留、include-all 展开及正文提示场景 |
| Mihomo v1.19.32 | 141 个 first-match 与 2 个 DNS/no-resolve 场景通过；全部为回环 DNS、REJECT 出口 |
| 单 provider 刷新 | 仅 Google 增加 `.cn` 域名，其余缓存保持旧版，144 个场景通过 |
| 故障注入 | Bybit 遮蔽检出 1 例；设备抢先检出 30 例；代理例外缺少设备保护检出 2 例 |
| 来源回放 | 37 个原始内容 hash 一致，按当前正式基线再次生成的所有文件字节一致；国内 IPv4 范围仍为原 6205 段 |
| 跨仓库组装 | 合成节点经 BuildBundle 生成 final（36 providers/18 groups）及 Stash（32/15），离线引用/默认选择与本地 Mihomo 语法检查通过；不等于 Stash 实机验收 |

首次修复 CI 暴露了两个环境差异并补充修正：Windows CP1252 无法输出中文提示（已本地复现，CLI 统一 UTF-8 并在测试中显式使用 CP1252 stream）；Linux 首个内核请求可能早于 tunnel Running（固定版本源码确认启动顺序，加入独立路由就绪探针，不重试正式用例）。

本轮未重新上传或测试旁路由、未生成真实订阅候选、未实机导入 Stash/Verge。新旧 provider 职责不能混用，须从当前 fragments 重新生成候选。相关证据保留在项目外 `backups/proxy-rule/20261003-routing-fixes`；本 commit 的远端 CI 以实际 run 结果为准，以上历史 CI 链接不替代本次检查。

## 尚未完成的生产验收

- 现场 alpha-g24b6de7 已完成隔离候选检查；这不构成接管流量后的真实业务验证。
- 未合入生产 main，provider URL 仍指向开发 branch；生产稳定 URL 切换须与配置迁移一起验证。
- 仅完成隔离目录 upload；未上传正式配置或 activate/reload/restart。活动 OpenClash 的版本、数据、selector chain 与实际业务连接尚未以新候选验收。
- Stash 未实机导入；Verge 的候选必须在 OpenClash 启用后从实际 runtime 派生，当前未将旧 runtime 冒充新版本。
- GitHub 正式自动发布未启用，失败邮件设置/收件未验证；浏览器通知设置页要求登录。用户已同意在生产验证及邮件实收确认后启用，条件尚未满足；配置文件存在不代表 schedule 已运行。
- 已只读保存活动与 managed 配置、provider cache、GeoSite.dat、Country.mmdb、ASN.mmdb 和 22 个组的当前选择；生产迁移前仍需复核时效性，恢复操作尚未演练。磁盘快照不等于完整复现内核内存状态。
