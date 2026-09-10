# Human-First Universal Evolution — Final Handoff

## 1. 最终状态

- 执行位置：当前对话工作区，未开启新窗口。
- 执行范围：源执行指令要求的 Stage 00–15，16/16 已执行并留下阶段记录。
- 最终交接状态：HANDOFF_COMPLETE_WITH_LIMITATIONS。
- 发布判断：不晋级 GA、Stable、Commercial 或公开发布；正式 Control/Treatment 判断为 HOLD。
- 关键未决：Browser live execution、Real Host、External Project、独立 Holdout、真实用户和跨平台安装均没有足够证据。
- 用户可继续的最短路径：先提供或授权 5–10 个真实 Host Pilot 任务和固定外部项目/Oracle，再重新运行资格门；在此之前不应把本地回归数字升级为现实世界结论。

这份报告是交接结果，不是新的发布授权。所有 PASS 都只在对应阶段的证据边界内成立。

## 2. 用户请求与输入文档的区分

| 来源 | 在本次执行中的角色 | 是否是直接执行指令 |
|---|---|---|
| 用户消息：按 md 文件的指令执行，在本对话内执行 | 授权当前对话内按指令推进，并覆盖源文档中的新窗口要求 | 是，且决定执行位置 |
| WUQ-GPT5.6-Luna-Max-分阶段持续进化执行指令.md | 16 阶段执行规格、轮次、证据和禁止事项 | 是 |
| WUQ-千人年度调研报告-真实执行推演.md | 年度调研/推演报告；包含合成和实际层的区分 | 否，是输入证据 |
| wuq-real-execution-report.html | 真实执行报告的声明性 HTML；本轮没有把其声明当作独立验证结果 | 否，是输入报告 |
| WUQ-1000-users-12-month-execution-simulation-report.html | 1000 个合成用户、12 个月的模拟报告 | 否，是输入报告 |

源执行指令中要求“新窗口”的部分按用户当前对话要求处理。四份输入文件没有被合并成一个证据等级；合成、报告声明、本地执行和真实 Host 证据保持分离。

## 3. 输入文档校验

以下 SHA-256 是执行开始时保存的输入快照：

| 文件 | SHA-256 | 解释 |
|---|---|---|
| WUQ-GPT5.6-Luna-Max-分阶段持续进化执行指令.md | D9FD9466906A23941BCC6202880964A060F4EB7F12E3ACF64B8150FAA807E1FE | 执行规格 |
| WUQ-千人年度调研报告-真实执行推演.md | EA43C8AA7415EC9E71300232C76DA151DB25C03A0B676A9DE4DAF319039BBFAD | 报告/推演 |
| wuq-real-execution-report.html | 7E6DF05C4E83E3FB56DE60B6016B07F4EAF0F25004594EAA3CB2AAAB6B9FFB5C | 报告 HTML |
| WUQ-1000-users-12-month-execution-simulation-report.html | 86A53DFE256676CD96E539C4C9C8CAAEC6D7A22314C016103F1C4688424061E6 | 合成模拟 HTML |

输入报告中的数字没有替代本轮直接运行结果，也没有替代 Real Host、External Holdout 或独立 Oracle。

## 4. 工作区与 Git provenance

- 工作区：本仓库的全新 public main clone。
- 分支：human-first-universal-evolution。
- 初始 HEAD：ea41be16dfb04c079d858de2f2ef9a08a7575ac8。
- origin/main：ea41be16dfb04c079d858de2f2ef9a08a7575ac8。
- 初始 HEAD 与 origin/main：一致。
- 当前改动：保留在工作树，未提交。
- Git 提交：未创建；本机 local user.name 和 user.email 均未设置，提交尝试因此被 Git 拒绝。没有猜测或擅自设置作者身份。
- diff check：exit 0。
- EXECUTION_LEDGER.jsonl：68 行，逐行 JSON 解析通过。
- Core 行数：2309，低于既有 2317 行预算。
- Stage 15 没有删除任何既有代码；没有发现可证明安全且能降低复杂度的冗余路径。

当前公开仓库仍是 [web-ui-quality-open-source](https://github.com/haotianshuo/web-ui-quality-open-source)；公开仓库的 README 与发布说明仍是外部发布事实的来源，当前本地工作树不能替代其发布资格。

## 5. 16 阶段结果

| Stage | 结果 | 本阶段结论 |
|---:|---|---|
| 00 | PASS | 冻结 baseline、输入报告分类、ledger 和 evidence boundary。 |
| 01 | PASS | 修正 focus replacement 的 whitespace/zero 误判；新增回归。 |
| 02 | PASS | 保留 UTF-8 stdout/stderr 边界；补 Windows 编码回归。 |
| 03 | PASS | 统一 reasonCode、TaskResult schema 和 human explanation；记录 protocol timing deviation。 |
| 04 | PASS | Browser Installed、Driver、Launch、Navigation、Reachability、Evidence、Verification 分层。 |
| 05 | PASS | 只读 Finding → Route → Selector → Component → Source Range repair mapping。 |
| 06 | PASS_WITH_ENVIRONMENT_LIMITATION | 普通中英文请求正确路由；Router/adapter 不扩权；Playwright sentinel 仍受环境限制。 |
| 07 | PASS_WITH_ENVIRONMENT_LIMITATION | Simple View/Expert View 保持分层；默认表面不泄漏内部协议。 |
| 08 | PASS_WITH_ENVIRONMENT_LIMITATION | security coverage 禁用时明确 NOT_MEASURED，启用时只做有界静态测量。 |
| 09 | PASS | GitHub Global Top-50 快照、Trending 限制和 P01–P10 设计哲学研究完成。 |
| 10 | PASS_WITH_UNRESOLVED_IMPLEMENTATION | 选择 C：小型原生 bootstrapper 加既有 Python Core；未实现 bootstrapper。 |
| 11 | PASS_WITH_ENVIRONMENT_LIMITATION | 一个 Core 经四个薄 adapter 形态复用；外部 Harness 未实测。 |
| 12 | NOT_MEASURED | 六行 Real Host Pilot 矩阵已冻结；本地探针不是 Real Host。 |
| 13 | NOT_MEASURED | 没有授权的外部项目/fixed commit/oracle；没有选 Holdout 替身。 |
| 14 | HOLD | 资格机械测试通过，但 Real Host/独立现实数据缺失，禁止 PROMOTE_CANDIDATE。 |
| 15 | HANDOFF_COMPLETE_WITH_LIMITATIONS | 最终回归、完整性核对和交接报告完成。 |

阶段证据分别保存在 stage-00 至 stage-15 目录；阶段 09 研究正文为 [DESIGN_PHILOSOPHY_RESEARCH.md](DESIGN_PHILOSOPHY_RESEARCH.md)。

## 6. 实际代码与契约变化

### 6.1 用户完成与语义结果

- runtime/python/web_ui_quality/task_result.py：统一 TaskResult、reasonCode、outcome、coverage、observations、verification 和 claim boundary。
- runtime/python/web_ui_quality/schemas/task-result.schema.json：加入稳定的 reasonCode 约束。
- schemas/task-result.schema.json：同步公共 schema。
- runtime/python/web_ui_quality/__main__.py：默认 human surface 解释 reasonCode，并保留 Expert/JSON 细节。
- tests/public/test_semantic_result.py：验证 plain、JSON、CI 语义一致。
- tests/public/test_simple_expert_view.py：验证普通表面和专家表面分离。

### 6.2 Browser 与环境能力

- runtime/python/web_ui_quality/capability_registry.py：增加 Browser capability clarity。
- runtime/python/web_ui_quality/__main__.py：doctor 增加 Browser status meaning 和 capability projection。
- tests/public/test_browser_capability_clarity.py：覆盖 available、partial、missing、blocked 和 not measured。

### 6.3 修复映射与自然语言入口

- runtime/python/web_ui_quality/fix_workflow.py：增加只读 repair mapping 与缺链提示，不猜文件、不写项目。
- runtime/python/web_ui_quality/intent_router.py：补普通修改动词、verify-only 优先级和 scoped negation。
- runtime/python/web_ui_quality/control_intent.py：补写入/验证冲突边界。
- runtime/python/web_ui_quality/task_intent_adapter.py：形成 canonical public intent adapter，始终 writeAuthorized=false。
- tests/public/test_repair_mapping.py、test_intent_router_surface.py：覆盖 mapping、普通修复、只读冲突和验证请求。

### 6.4 Security coverage

- runtime/python/web_ui_quality/core.py：加入 securityCoverage，禁用时 NOT_MEASURED，启用时 bounded MEASURED。
- runtime/python/web_ui_quality/schemas/audit-result.schema.json 和 schemas/audit-result.schema.json：同步 securityCoverage schema。
- tests/public/test_security_coverage_visibility.py：覆盖 opt-in、redaction、Router read-only 和 claim boundary。

### 6.5 Universal thin adapter

- runtime/python/web_ui_quality/agent_adapter.py：只组合已有的 intent、capability、Host bridge 和 TaskResult Core。
- tests/public/test_thin_agent_adapter.py：用 Codex-shaped、Claude Code-shaped、OpenCode 和 Cursor/VS Code 别名做本地契约回归。
- adapter 绝不复制 scope、receipt、drift、evidence 或 claim engine；静态 forbidden-engine import 检查为 0。
- 外部 Harness、真实模型、真实权限和真实 Host 没有被本地 wrapper 冒充。

### 6.6 没有发生的变化

- 没有改 expected/oracle。
- 没有让 Router、Skill、报告或 adapter 获得写权限。
- 没有执行原生 bootstrapper、Node rewrite、standalone executable 或嵌入式 runtime。
- 没有导入外部项目源代码、资源、截图或 README 文案。
- 没有提交、推送、发布、登录外部服务或发送外部变更。

## 7. 测试与验证证据

| 阶段/探针 | 结果 |
|---|---|
| Stage 01 full | 680 passed |
| Stage 02 full | 682 passed |
| Stage 03 full | 685 passed |
| Stage 04 full | 688 passed |
| Stage 05 isolated-temp full | 693 passed |
| Stage 06 full | 698 passed, 8 skipped, 1 failed |
| Stage 07 full | 700 passed, 8 skipped, 1 failed |
| Stage 08 full | 703 passed, 8 skipped, 1 failed |
| Stage 09 public entry | 38 passed |
| Stage 10 isolated wheel lifecycle | build/install/help/uninstall passed；repeat install/same-version upgrade/help/uninstall passed |
| Stage 11 focused | 27 passed；full 708 passed, 8 skipped, 1 failed |
| Stage 12 boundary set | 62 passed |
| Stage 13 qualification boundary set | 32 passed |
| Stage 14 qualification scripts | three commands exit 0；mechanics PASS，但 realWorld 仍 NOT_MEASURED |
| Stage 15 final full | 708 passed, 8 skipped, 1 failed in 395.12s |

Stage 15 唯一失败：

- test: tests/test_420_browser_security.py::test_browser_execution_sentinel_requires_a_live_browser
- reason: PLAYWRIGHT_SYNC_API_REQUIRED_FOR_FULL_BROWSER_GATE
- cause: active Python environment does not provide Playwright sync API/live browser。
- meaning: Browser execution remains NOT_MEASURED；不是把静态检查升级为 Browser PASS 的理由。

Stage 15 的最终 full run 使用独立 basetemp；8 个 skip 仍是 Browser/Chromium unavailable 或要求 Browser extra 的既有限制。

## 8. 关键代码哈希

| 文件 | SHA-256 |
|---|---|
| runtime/python/web_ui_quality/core.py | D89DC514915B4BBB2CFFCE01036EF159CC90F53B0A5ABE57629E74F6F18C4D54 |
| runtime/python/web_ui_quality/capability_registry.py | 71C301106C5DA092EBEEE67B0A0946F45AFA9A75E43BE20A550061E8B9A6E97A |
| runtime/python/web_ui_quality/__main__.py | 2CEFB6A289D69FCCF3D9533324C5C48194F8A7CB89D7278DB460FD7C5C468494 |
| runtime/python/web_ui_quality/control_intent.py | 3E32D57E9ACF124100C35581B2858347B923702C718FF6EAB71FBA2C7B3746DA |
| runtime/python/web_ui_quality/fix_workflow.py | 0037C4C436F7985C265BBB0EBAF890A812EB9A7173E9163E75C364C895D43290 |
| runtime/python/web_ui_quality/intent_router.py | 80019C01286A62843438A6140BFF5AC725F502BECE9499EDB6A5578346D1C663 |
| runtime/python/web_ui_quality/task_intent_adapter.py | 064E37E6B311616AD68DAAC2D918140CBDD08C38B057F099422172A067398E19 |
| runtime/python/web_ui_quality/task_result.py | C8EB55DB7C1EBC8B68A42DC517305CC136E8F4C8470913BA3628E355E0081B2E |
| runtime/python/web_ui_quality/agent_adapter.py | 26960D8C736EC89C0BB3707EF8DECBB1200AC10EA1A9C566879249D8FE23EA16 |
| runtime/python/web_ui_quality/schemas/audit-result.schema.json | E70494FDD13C262747E15CDDD7EC6356ED8F2D7F5B38A78D3634428685B828FA |
| runtime/python/web_ui_quality/schemas/task-result.schema.json | E22875C8FDD1A1BBAB871C698C8AB20C95515F8D0AA29E319375F7AF0592EA1D |

## 9. Zero-Python 与 Thin Adapter 决策

### Zero-Python

现有 package metadata 仍要求 Python >=3.10，runtime dependency 为
Pillow>=10,<13，Browser 是 optional Playwright。系统 Python 3.12.10 的
global setuptools/wheel 缺失，直接构建探针失败；隔离 venv 补齐构建工具
后成功构建 895086 bytes 的 py3-none-any wheel，并完成安装、help、卸载和
重复生命周期探针。

当前选择 C：小型原生 bootstrapper + 既有 Python Core。选择依据是保留已
回归的 Core，降低语义重写风险；bootstrapper、签名、离线、升级回滚和其他
OS 仍未实现/未测量。

### Universal Agent

四个 Harness 的 adapter surface 已统一为：

- integration handoff；
- capability discovery；
- natural-language routing；
- authority handshake；
- tool bridging；
- result rendering。

以上全部都落到同一个 Core；实际写入仍由 Host 完成，adapter 永远不授予
writeAuthorized。

## 10. Stage 09 设计哲学摘要

Stage 09 的 [研究正文](DESIGN_PHILOSOPHY_RESEARCH.md) 冻结了 GitHub public
stars Global Top-50 快照、动态 Trending 限制和超过 20 个相关项目的分类。
去重后的原则为：

- P01 小而可观察的 first-success loop；
- P02 分层安装而不是单一“零配置”承诺；
- P03 一个 Core、多种 surfaces；
- P04 progressive disclosure；
- P05 capability 是状态机而不是布尔值；
- P06 evidence 与 verdict 分离；
- P07 Authority 必须显式并受 policy 约束；
- P08 recovery 是主流程的一部分；
- P09 跨平台声明需要矩阵；
- P10 automation 先提案、后提交。

这些原则只影响 KEEP/GUARDED/DEFERRED 决策，没有导入外部代码、资源或文案。

## 11. 当前真实证据边界

| 领域 | 当前状态 | 不能推出 |
|---|---|---|
| Local Core/static | 已有阶段性 PASS 和 708 passed full baseline | 不能推出模型准确率或真实用户成功 |
| Browser | NOT_MEASURED，live Playwright sentinel 未通过 | 不能推出真实页面已到达、已修改或已验证 |
| Real Host | NOT_MEASURED | 不能推出 Codex/Claude/OpenCode/Cursor/VS Code 的外部行为 |
| External projects | NOT_MEASURED | 不能把本地 fixture/历史 external test 当成真实外部项目 |
| Control/Treatment | HOLD | 不能推出 Treatment effect、precision、recall 或 adoption |
| Holdout | NOT_MEASURED | 不能推出泛化、抗污染或现实世界预测有效性 |
| Security | opt-in disabled 是 NOT_MEASURED；enabled 是 bounded static MEASURED | 不能推出完整 AppSec、生产安全或凭据安全 |
| Open Source/GA | 保持既有 public preview/eligibility 边界 | 不能因本地测试或研究快照宣称 GA、Stable 或 Commercial |

## 12. 未决事项与需要的外部输入

1. Playwright compatible module/browser/driver，以及受控 Browser fixture 的真实执行。
2. 5–10 个 Real Host Pilot 任务：Host、Harness、model、reasoning、permission、tool trace、source diff、verification、receipt。
3. 授权的 External Project 列表、fixed commit、目标任务、non-goals、独立 expected/oracle 和法律边界。
4. 正式 Control/Treatment 的 preregistration、样本量、阈值、独立标签、Holdout 分离和停止规则。
5. 用户授权的 Zero-Python packaging work：bootstrapper 原型、跨平台安装、更新/卸载、签名/attestation、离线/代理/回滚。
6. Git 提交作者身份；在用户明确设置前不由本次执行代填。

在这些输入改变前，重复本地 gates 不会解决上述证据缺口；安全的下一步是补齐输入，而不是重跑相同结果并改名。

## 13. Final integrity statement

- 所有阶段记录按 append-only 方式写入 EXECUTION_LEDGER.jsonl。
- 失败和 NOT_MEASURED 状态均保留。
- 当前分支未提交；没有伪造 commit、批准、Host、Holdout 或 provenance。
- Stage 15 源代码减少量：0；没有未经证据支持的架构删减。
- 最终交接文档：HUMAN_FIRST_UNIVERSAL_EVOLUTION_FINAL.md。
