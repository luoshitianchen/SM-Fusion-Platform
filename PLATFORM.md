# SM Enterprise Suite

企业级微服务套件：统一门户、身份认证、API 网关、密钥管理、审计中心与 24 个业务/基础设施服务，全栈国密（SM3/SM4）加持。

## 版本

- 平台大版本 **3.0.0**（2026-09-05）：全平台版本统一；新增 SBOM 物料清单与 CI 依赖审计；补全部署文档。
- 门户 Fusion Platform **5.0.0**；核心业务 ERP / Knowledge Bot **3.0.0**。
- 服务目录：`SM-Fusion-Platform/config/services.json`（28 项，版本/负责人/SLO/合规标签）。

## 架构

```text
Fusion Platform（门户 5.0.0）
 ├─ IAM（身份 3.0.0）        ── 统一认证 / OIDC / MFA
 ├─ API Gateway（网关 3.0.0）── 鉴权 / 限流 / 熔断 / 审计
 ├─ Config KMS（密钥 3.0.0） ── 信封加密 / 轮换 / 吊销
 ├─ Audit Log Center（审计 3.0.0）── 审计留痕 / 防篡改链
 ├─ Observability（观测 3.0.0）── 健康 / SLO / 告警
 └─ 业务域：ERP / Knowledge / HR / CRM / Finance / Procurement / Legal / MDM /
    CMDB / SOC / Backup-DR / Event-Bus / Object-Storage / Data-Exchange /
    Data-Governance / DevSecOps / Service-Desk / Workflow / Notification /
    AgentOps / Release-Center / API-Developer-Portal（均 3.0.0）
```

## 快速开始

```bash
# 1. 配置密钥（生产必填，32+ 随机字符）
cp SM-Fusion-Platform/.env.example .env   # 填写 SM_INTERNAL_API_KEY / SM4_KEY_HEX 等

# 2. 一键编排全部 28 个服务
 docker compose -f SM-Fusion-Platform/docker-compose.yml up -d

# 3. 验证
curl http://127.0.0.1:8200/health        # 门户
curl http://127.0.0.1:8200/api/services  # 服务目录与健康
```

## 安全模型

- **fail-closed**：API 服务写接口必须携带 `X-Internal-Token`（函数级校验，不依赖中间件配置）。
- **国密**：SM4-CBC + SM3-MAC 防篡改；SM3 审计链；PBKDF2 口令哈希（10 万次迭代 + 随机盐）。
- **SBOM**：每仓库 `sbom.json`（CycloneDX 1.5），CI 强制校验；`pip-audit` 依赖审计 0 已知 CVE。
- 渗透测试闭环：路径遍历 / API Key 弱校验 / SSRF / KMS 加解密无鉴权均已实证修复并复测（详见各仓库 CHANGELOG）。

## 目录

| 仓库 | 职责 |
|---|---|
| SM-Fusion-Platform | 门户 / 服务目录 / 编排（docker-compose 28 服务） |
| SM-ERP | 组织、员工、会话、审计中心数据源 |
| SM-knowledge-bot | RAG / 多轮对话 / 权限知识检索 |
| SM-* | 基础设施与业务域服务（统一 base 层） |

## 质量

- 测试：28 仓库 257 用例（含安全回归），CI 覆盖率门禁 ≥70%。
- 静态检查：ruff 全绿；bandit / pip-audit 纳入 CI。
- 文档：每仓库 README / SECURITY.md / SECURITY_BASELINE.md / CHANGELOG.md / DEPLOYMENT 文档。
