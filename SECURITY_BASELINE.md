# 企业安全基线

本项目按企业内部系统默认安全要求维护，适用于本地、服务器和容器化部署。
本文档描述所有子服务统一落地的最低安全基线，以及平台级的安全与合规机制。

## 访问控制

- 业务接口不得信任客户端传入的用户身份。
- 统一身份由 SM-IAM 签发 OIDC/JWT（HS256），claims 携带 iss=sm-iam / aud=sm-services / scope / roles。
- 全部 25 个子服务内置 JWT 校验中间件：无合法 Bearer 令牌时返回 401（fail-closed）；内部服务间写入使用 `X-Internal-Token` 并通过常量时间比较校验。
- 开发/测试环境未配置 `SM_JWT_SECRET` 时放行，便于本地运行；生产环境必须配置 `SM_JWT_SECRET`。
- 默认启用角色、部门、岗位和数据范围授权模型。

## 认证与令牌

- 每个服务通过 `SM_JWT_SECRET` 与 IAM 共享签名密钥（部署时经 `.env` 注入）。
- IAM 提供 `/oauth/token`（password 与 client_credentials 两种 grant）、`/oidc/.well-known/openid-configuration`、`/oidc/jwks`、`/api/auth/me`。
- 令牌包含 `exp`，服务端校验签名与过期时间，不支持算法混淆（固定 HS256）。
- 生产部署必须为 IAM 配置引导用户（`SM_IAM_BOOTSTRAP_USER` / `SM_IAM_BOOTSTRAP_PASSWORD`）。

## 网络暴露

- 默认仅建议绑定内网地址或由 SM-API-Gateway 统一转发。
- SM-API-Gateway 依据 `config/routes.json`（24 条路由）真实反向代理到各上游服务，剥除 host/content-length/connection 等头，注入 `X-Trace-Id` 与 `X-Internal-Token`，上游失败返回 502。
- 生产环境必须配置允许访问的域名或网关地址（`SM_ALLOWED_HOSTS` + TrustedHost 中间件）。
- 不建议服务直接裸露到公网入口。

## 安全响应头

所有服务统一注入以下响应头：

- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: no-referrer
- Permissions-Policy
- Content-Security-Policy
- X-Request-Id / X-Trace-Id
- 生产环境（`SM_ENV=production`）额外启用 Strict-Transport-Security (HSTS)

## 限流与输入保护

- 每个服务启用按客户端+路径的滑动窗口限流（默认 600 次/60 秒），超限返回 429 + Retry-After。
- 请求体大小上限默认 1 MiB，超限返回 413。
- 所有写接口要求内部令牌，未通过返回 403。

## 密码学（国密）

- 所有服务提供 SM3 摘要（`/api/crypto/sm3`）与 SM4-CBC 加解密（`/api/crypto/encrypt`、`/api/crypto/decrypt`，IV 前置 16 字节）。
- SM4 密钥在首次调用时随机生成并持久化到本地 settings 表（`SM4_KEY_HEX`），生产建议接入 KMS/HSM 托管。
- IAM 用户密码以 SM3 哈希存储。
- `compliance` 中声明“国密SM3/SM4”的服务均已实现对应端点。

## 数据持久化

- 所有子服务使用 SQLite 持久化（`SM_DATABASE_PATH`），重启不丢数据；`read_only` 容器通过命名卷挂载 `/app/data` 保证可写。
- 本地维护 `settings` 表（密钥/配置持久化）与 `audit_events` 表（本地审计留痕）。

## 审计与日志

- 管理操作、登录、权限变更、数据导入导出必须记录审计日志。
- 本地审计事件带 `integrity`（SM3 完整性摘要，防篡改链），并可通过 `SM_AUDIT_CENTER_URL` 异步上报 SM-Audit-Log-Center 集中审计。
- 日志中不得写入密码、Token、Cookie、密钥、身份证号等敏感信息。
- 每个请求应带有追踪 ID（X-Request-Id / X-Trace-Id），便于跨服务排查。

## 可观测性

- 每个服务暴露 Prometheus 文本格式 `/metrics`（请求量/错误量/延迟累积），以及 JSON 版 `/api/ops/metrics`。
- `/readyz` 含运行时、配置、数据库三项探活。
- 每个服务提供 `/api/integration/manifest` 集成契约（依赖、事件、健康/指标路径），供门户与观测平台自动发现。

## 依赖与供应链

- 依赖固定在 requirements.txt（fastapi/pydantic/httpx/gmssl，无新增运行时依赖）。
- GitHub Actions 使用最新主版本。
- 建议开启 Dependabot、CodeQL、Gitleaks、依赖漏洞扫描。

## 发布要求

- 每次正式发布必须更新 VERSION 和 CHANGELOG.md。
- Release 包应由 CI 自动生成。
- 生产部署前必须通过测试、依赖扫描和 Secret 扫描。
- 部署拓扑：SM-Fusion-Platform `docker-compose.yml` 编排全部 27 个服务（ERP、Knowledge-Bot、25 个子服务、门户），所有子服务注入 `SM_JWT_SECRET`/`SM_DATABASE_PATH`/`SM_AUDIT_CENTER_URL` 并挂持久化卷。
