# 代理分流规则

本仓库维护公开规则、策略组和受控上游更新。节点、订阅、凭据与实际客户端配置由独立 private dingyue 工具管理。

## 维护入口

- `fragments/`：策略组、provider 声明和 first-match 顺序；仍保留三个稳定入口。
- `rules/*.yaml`：个人直连、代理例外、指定设备、推送、广告放行和海外券商规则，手工维护。
- `rule-sources/sources.json`：上游来源及组合；`overrides.json`：有意增删，禁止直接修补 generated 文件。
- `rules/generated/`：IPv4 规则产物与 `sources.lock.json`；上游来源、内容 hash 和输出统计可追溯。
- [更新器 README](scripts/rule-updater/README.md)：构建、验证和发布边界。

## 当前重构候选

开发 branch：`codex/routing-refactor`。这是候选配置，provider URL 指向同名开发 branch；不代表生产 main 或路由器已经迁移。旧 `rules/*.yaml` 路径继续保留。

- BNQ 的组顺序及主规则在 Bybit 前；Crypto 匹配明确排除 Bybit，不依赖两个集合永久没有交集。
- GitHub/Telegram 进入节点选择；Xbox 进入其他游戏平台；Bing/OneDrive/Microsoft 合并成一个微软入口。Xbox 采用目标组当前直连优先的默认顺序。
- 国内域名采用 Meta cn，国内 IPv4 采用 gaoyifan；两者共享 Google/海外券商域名排除。路由层旧 GEOSITE/GEOIP 入口已被可追溯 provider 替代，DNS 配置不在本仓库重构范围内。
- 国内直连先于设备分派，设备分派先于普通服务。高优先级代理例外仍区分设备。Ookla 新增直连、自定义规则和未合并组的默认字符串保持。
- 全部第三方产物过滤 IPv6；仍保留必要 IPv4 和 no-resolve。路由产物不再使用 ASN/Geo 数据库，客户端 DNS 自身的数据依赖仍需在部署时核对。

## 来源调整与覆盖边界

当前由 38 个输入组合出 28 个第三方/派生 provider，另保留 8 个个人 provider。来源与许可声明见 [NOTICE.md](rule-sources/NOTICE.md)。

OpenAI/Claude/GitHub/Binance/X+Grok/YouTube/Microsoft/Xbox/Epic/EA/Telegram/Netflix 域名采用 Meta；GitHub、Binance、EA 保留部分旧专用域名补充。FCM、Google、Apple、Steam、SteamCN、Sony、Nintendo、LAN、广告、Crypto 和 GFW 的有用覆盖继续复用原源。

明确的行为调整：

- 不再让 OpenAI 的共享 ASN、Auth0/Stripe 等整个平台决定 AI 出口；保留已知专用端点。新入口的登录、语音、内容功能仍需实机验收。
- 移除 Microsoft 的通用 Akamai 后缀、Apple 的通用 Akamai/Crashlytics 后缀、Binance 的 appsflayer 域名；这些共享或无法明确归属的范围不整体划入单项服务。
- Nintendo 不再接管整个 `35.192.0.0/12` 云网段；游戏专用域名保留，真实裸 IP 需求需依据连接证据补充。
- Telegram 使用官方 IPv4 CIDR；旧宽泛 `91.108.0.0/16` 及官方集合以外网段不整体沿用。Netflix/Twitter 保留旧 IPv4，未以更大的 GeoIP 集合无条件替换。
- Windows/macOS 本机 process 匹配与路由器、Stash iOS/tvOS 不等价；关键验收使用域名/IP，不以 process 规则证明移动端覆盖。

## 验证与生产边界

本地已使用固定 Mihomo v1.19.32 对候选做隔离 first-match 验证；所有测试出口为 REJECT，仅有回环 DNS，不能替代真实登录、下载、消息和代理出口验证。

生产迁移需要配套规则与 dingyue 版本，并核对正式 URL、活动 cache、组选择及恢复材料。开发 branch 发布不等于 main 合并、自动发布启用或 OpenClash activation。两个 repository 分别维护 branch/worktree，不能假定外层 worktree 带有内层源码或私密运行数据。
