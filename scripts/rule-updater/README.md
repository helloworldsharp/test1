# rule-updater

只处理公开规则数据；不读取订阅、节点、controller secret，不连接路由器。依赖 Python 3.12+、PyYAML 6.0.3；内核测试使用固定 Mihomo v1.19.32 amd64，下载前记录的 release digest 在解压前核对。

从仓库根目录运行：

```text
python -m pip install -r scripts/rule-updater/requirements.txt
python -m unittest discover -s scripts/rule-updater -p "test*.py"
python scripts/rule-updater/updater.py --output <新的候选目录>
python scripts/rule-updater/get_mihomo.py --output <临时目录中的内核路径>
python scripts/rule-updater/verify_kernel.py --candidate <候选目录> --mihomo <内核路径> --evidence <新的证据目录>
```

所有入口接受 `--root`（内核下载器除外），默认本 checkout；候选与证据目录必须显式指定且尚不存在。Windows 的临时目录遵循机器上的 backups/temp 约定；应保留的验收证据放在 backups 中。正式源码目录不存运行 cache。

## 输入与增删

`sources.json` 声明 GitHub repo/ref/path 或 HTTPS 来源以及实际格式；同一 repo/ref 每轮解析一次 commit。只接受实际实现并验证的 domain/classical/IP 类型，未知类型直接失败。输出按 `parts` 组合，可按类型保留旧来源 IPv4 或专用域名。

纯 IP 来源默认附加 no-resolve；国内 IPv4 来源显式设置 `no_resolve: false`，让未命中国内域名集的请求能根据 DNS 结果在设备分流前分类。其他 IP 来源不随之改变。Google 域名和非域名规则分开输出，国内排除复用服务侧的域名 provider，避免复制排除集的缓存版本差异。

`overrides.json` 的 `add`/`remove` 只处理明确条目；删除项已被上游移除时报告 stale removal，要求复核，避免过期意图悄悄失效。它不是无限域名集合减法。BNQ/Bybit 与国内例外使用 fragments 中的明确逻辑规则保障最终路由。

AI 补充仍使用现有 `ai_openai`/`ai_anthropic` provider。OpenAI 的6个精确 CDN/WorkOS 端点、`claude.dev` 和 Anthropic 官方入站 IPv4 `160.79.104.0/23,no-resolve` 在 `overrides.json` 维护；共享平台不扩大为整个 suffix，Anthropic 的出站 MCP 网段不作为客户端目的地址补入。

ChatGPT Voice IPv4 从官方 `https://openai.com/chatgpt-voice.json` 获取，声明为 `json-prefixes`/`ipcidr` 来源并组合进 `ai_openai`；不在 overrides 手抄当前 IP。解析要求非空 `prefixes` 列表，每项为单个 `ipv4Prefix` 或 `ipv6Prefix` CIDR，校验地址族和网络边界；过滤 IPv6，IPv4 默认附加 no-resolve。异常数据使整轮构建失败，保留 last-good 产物。来源更新沿用同一轮下载、hash、变化阈值和发布 gate。

更新器全部来源和转换通过后才建立新候选目录，拒绝覆盖已有目录；网络/解析失败不写正式产物。I/O 失败可能留下不完整候选，不能发布，可复核后清理。相同输入输出一致，正文无变化保留上次内容变化时的 receipt，不因上游每日生成时间制造 commit。

相对当前 generated 基线，每个输出默认最多删除 20%（小集容许 5 条）或增长 50%（小集容许 100 条）；同时受 min_rules/max_rules 限制。异常变化要求复核 sources 定义，不自动回退、拼接旧新来源或吞掉失败。这些阈值不替代路由行为验证。

generated 文件通过 .gitattributes 固定 LF，避免 Windows checkout 的换行转换破坏 receipt 中的内容 hash；许可证副本保留下载字节。

## 验证证明范围

内核加载本轮本地候选，等全部 provider 初始化完成后检查基础路由、AI 补充域名、Anthropic 网段内外边界及候选中每个 OpenAI Voice IPv4 网段的代表地址；当前23条语音IP时共270个场景。source-device fixture 使用三个回环地址，同时验证普通来源进入 AI、指定设备继续使用设备组、共享 WorkOS 后缀不被整体接管。受控 DNS 默认返回文档地址 `192.0.2.123`，国内 fixture 返回 `1.2.4.8`；验证域名解析后的国内直连、裸 IP、Google/券商排除、下载与服务归属。另有两例控制 DNS 查询的 no-resolve 验证。出口全部 REJECT，真实互联网服务不会收到测试连接；语音 UDP、节点能力和真实登录仍须实机验证。

`--mutate bnq-shadow`、`--mutate devices-first`、`--mutate override-unguarded` 应返回非零并产生完整 report.json，分别检出 Bybit 被 Crypto 接走、设备规则抢在直连前和代理例外失去设备保护。只有测试副本被变更。

`--mutate google-refresh` 应成功通过上述场景及3个新增场景：只在 Google provider 增加一个 `.cn` 服务域名，其余缓存保持旧版，三个来源均不得被国内直连接走。四种 mutation 均在 CI 中执行。按服务归属和设备保护的细节由这些真实内核场景检查；dingyue offline validator 只负责语法、引用、默认候选和通用顺序边界，不是完整策略解释器。

原策略组用合成节点做语法检查，行为测试把各组出口换为 REJECT 来观察匹配组；实际 selector chain、节点健康、默认选择及 Stash/Verge 的实机功能仍待对应客户端验收。

测试端口同时检查 TCP/UDP 可绑定性；释放端口到内核绑定之间仍有竞争窗口，监听失败会带具体错误和 kernel.log 路径终止。启动检查除了 listener 与 provider 条数，还等待一个独立回环请求产生匹配日志；Mihomo 在 provider 初始化后才将 tunnel 设为 Running。就绪探针允许在 30 秒内轮询，实际行为用例仍各执行一次，避免启动竞态吞掉首个用例或重试掩盖路由失败。

## CI 与发布

`.github/workflows/rules.yml` 在 push/PR 验证已提交产物；schedule/workflow_dispatch 获取上游并生成候选，执行 unit、内核与故障注入检查。schedule 为每天 UTC 00:47（北京时间 08:47），只有默认 branch 的定时工作流会运行。

正式发布要求同时满足：在 main、定时或手动事件、repository variable `RULE_AUTO_PUBLISH=true`、全部验证通过、候选配置已迁移到生产 URL。开发阶段不设置该变量。

只读 validation job 产出不可变 artifact；有 contents write 权限的 publish job 只允许 generated 数据路径。发布单个普通 commit，不 force push、不绕过 branch protection。远端前移或权限拒绝使工作流失败；下一次需基于当前 main 重建验证。GITHUB_TOKEN push 不依赖后续 workflow 再补验证。

`publish.py --candidate <目录>` 仅用于干净的发布 checkout：核对文件集合与 hash 后复制、stage 数据，不自行 commit/push。它不是日常工作区的修改合并器。客户端多 provider 刷新并非原子；涉及跨集合职责、URL 或优先级变化须配置迁移，不能交给每日数据更新。

异常通知使用 GitHub 原生 Actions failure email，由接收账号启用并实际确认收件。无变化成功不发通知；schedule 完全未启动不产生失败邮件。生产发布、通知设置/收件与实机验证分别验收。
