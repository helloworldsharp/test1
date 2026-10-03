# 代理分流规则

本仓库维护公开规则、策略组和受控上游更新。节点、订阅、凭据与实际客户端配置由独立 private dingyue 工具管理。

## 维护入口

- `fragments/`：策略组、provider 声明和 first-match 顺序；仍保留三个稳定入口。
- `rules/*.yaml`：个人直连、代理例外、指定设备、推送、广告放行和海外券商规则，手工维护。
- `rule-sources/sources.json`：上游来源及组合；`overrides.json`：有意增删，禁止直接修补 generated 文件。
- `rules/generated/`：IPv4 规则产物与 `sources.lock.json`；上游来源、内容 hash 和输出统计可追溯。
- [更新器 README](scripts/rule-updater/README.md)：构建、验证和发布边界。

## 当前分流配置

重构已合入 `main`，provider URL 统一指向 `main`，旧 `rules/*.yaml` 路径继续保留。合入只更新规则与工具源码；需使用配套 dingyue 重新生成配置，再单独上传、启用和验收，路由器不会随 Git 合并自动切换。

- BNQ 的组顺序及主规则在 Bybit 前；Crypto 匹配明确排除 Bybit，不依赖两个集合永久没有交集。
- GitHub/Telegram 进入节点选择；Xbox 进入其他游戏平台；Bing/OneDrive/Microsoft 合并成一个微软入口。Xbox 采用目标组当前直连优先的默认顺序。
- 国内域名采用 Meta cn 加明确补充，国内 IPv4 采用 gaoyifan；两者直接复用当前 Google/海外券商域名 provider 排除，再由国内 IPv4 兜底主动解析未分类域名。路由层旧 GEOSITE/GEOIP 入口已被可追溯 provider 替代，DNS 配置不在本仓库重构范围内。
- 国内直连先于设备分派，设备分派先于普通服务。高优先级代理例外仍区分设备。Ookla 新增直连、自定义规则和未合并组的默认字符串保持。
- 全部第三方产物过滤 IPv6；仍保留必要 IPv4 和 no-resolve。路由产物不再使用 ASN/Geo 数据库，客户端 DNS 自身的数据依赖仍需在部署时核对。

## 来源调整与覆盖边界

当前由 37 个输入组合出 28 个第三方/派生 provider，另保留 8 个个人 provider。来源与许可声明见 [NOTICE.md](rule-sources/NOTICE.md)。

OpenAI/Claude/GitHub/Binance/X+Grok/YouTube/Microsoft/Xbox/Epic/EA/Telegram/Netflix 域名采用 Meta；GitHub、Binance、EA 保留部分旧专用域名补充。FCM、Google、Apple、Steam、SteamCN、Sony、Nintendo、LAN、广告、Crypto 和 GFW 的有用覆盖继续复用原源。

明确的行为调整：

- Google 域名保留在 `google`，原 4 段 IPv4 和 6 条 process 规则移入 `google_non_domain`，仍在设备分流后进入 Google 组。国内排除直接引用 `google` 与 `wbrokers`，不再生成可与服务集刷新错开的 `china_exclusions`。
- 国内 IPv4 使用可解析匹配；仅 `china_ipv4` 来源声明 `no_resolve: false`，其他来源的 no-resolve 保持。Google/券商排除先于国内 IPv4 判断，国内域名与裸 IP 分别验证。
- `overrides.json` 保留已复现的旧直连范围：Epic 下载、两个 Apple 下载端点、`cmpassport.com` 和 `element-plus.org`。只恢复具体 suffix，不恢复共享 CDN 的整个平台后缀；这些是保留旧路由意图，不是宣称真实下载出口已经验证。Epic 端点见[官方白名单](https://www.epicgames.com/help/c-36624475/a15422130)，Apple 下载分类见[企业网络说明](https://support.apple.com/en-ie/101555)。
- 去掉上游国内集合的整个 `.ms` suffix，保留微软/设备及未知域名 fallback；将旧 Xbox 专用的 `msgamestudios.com` 补回其他游戏平台，避免落入 Microsoft 大类。`xboxab.net`、`xboxservice.com` 当前用途仍待验证，不机械恢复。
- 不再让 OpenAI 的共享 ASN、Auth0/Stripe 等整个平台决定 AI 出口；保留已知专用端点。新入口的登录、语音、内容功能仍需实机验收。
- 移除 Microsoft 的通用 Akamai 后缀、Apple 的通用 Akamai/Crashlytics 后缀、Binance 的 appsflayer 域名；这些共享或无法明确归属的范围不整体划入单项服务。
- Nintendo 不再接管整个 `35.192.0.0/12` 云网段；游戏专用域名保留，真实裸 IP 需求需依据连接证据补充。
- Telegram 使用官方 IPv4 CIDR；旧宽泛 `91.108.0.0/16` 及官方集合以外网段不整体沿用。Netflix/Twitter 保留旧 IPv4，未以更大的 GeoIP 集合无条件替换。
- Windows/macOS 本机 process 匹配与路由器、Stash iOS/tvOS 不等价；关键验收使用域名/IP，不以 process 规则证明移动端覆盖。

## 验证与生产边界

本地已使用固定 Mihomo v1.19.32 对候选做隔离 first-match 验证；所有测试出口为 REJECT，仅有回环 DNS，不能替代真实登录、下载、消息和代理出口验证。

生产迁移需要配套规则与 dingyue 版本，并核对正式 URL、活动 cache、组选择及恢复材料。main 合并不等于自动发布启用或 OpenClash activation。自动发布仍须单独设置 `RULE_AUTO_PUBLISH=true`，生产验收及失败邮件实收确认前保持关闭。两个 repository 分别维护 branch/worktree，不能假定外层 worktree 带有内层源码或私密运行数据。

本次审计修复调整了 provider 职责：旧开发候选不能只刷新 provider；须用当前 fragments 重新生成 final/Stash，再执行对应客户端验收。原开发候选的正文与配置必须成套回退到修复前 commit，不能把新 Google 域名集与旧排除声明混用。
