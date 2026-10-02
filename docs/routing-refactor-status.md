# 分流重构验收记录

日期：2026-10-03（北京时间）。公共规则与 private dingyue 使用各自的 codex/routing-refactor branch 和独立 worktree；日常 main 工作区未修改。

## 已完成的本地交付

- 分组精简、BNQ/Bybit 显式隔离、国内域名/IP来源统一、Google/券商排除，以及全部第三方数据的受控生成。
- 28 个 generated provider、8 个个人 provider、18 个策略组；个人源文件保持不变。
- 更新器拒绝未知类型/异常空集/过量增删，冻结每轮来源 commit，失败不发布；连续两次下载生成的全部产物字节一致。
- dingyue 支持独立 rules root，冻结本地规则数据，隔离 subconverter 副本；Stash 清理嵌套设备引用、处理默认选择并原子写入。
- 已写 CI，包括日常更新候选、内核行为检查、故障注入和受限发布 job；默认未启用正式发布。

## 验证证据

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

测试命令见更新器 README 和 private dingyue README。私密候选与本地完整日志保存在项目外 backups，不进入公共 repository。

## 尚未完成的生产验收

- 远端 CI 需在开发 branch 发布后取得实际运行结果。
- 未合入生产 main，provider URL 仍指向开发 branch；生产稳定 URL 切换须与配置迁移一起验证。
- 未 upload/activate/reload/restart；活动 OpenClash 的版本、数据、selector chain 与实际业务连接尚未以新候选验收。
- Stash 未实机导入；Verge 的候选必须在 OpenClash 启用后从实际 runtime 派生，当前未将旧 runtime 冒充新版本。
- GitHub 正式自动发布及失败邮件设置/收件未启用或验证；配置文件存在不代表 schedule 已运行。
- 生产恢复材料尚需冻结活动配置、cache 和实际 DNS/Geo 数据依赖。本地候选可直接弃用，不表示已完成线上回滚演练。
