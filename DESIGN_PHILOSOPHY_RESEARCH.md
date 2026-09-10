# WUQ Stage 09 — GitHub Global Top-50 Design Philosophy Research

## 1. 研究结论先行

本阶段得到的可迁移结论不是“再做一个更大的 Agent”，而是：

1. 让第一次成功成为一条可观察、可恢复、可复现的最短路径。
2. 把一个稳定的 Core 与多个入口、运行环境、工具适配器分开，入口可以变，权限和证据不能被入口悄悄扩大。
3. 把模式、权限、能力、结果和证据分层显示；普通用户先看到下一步，专家才展开内部细节。
4. 把失败、不可达、未授权、未测量和不完整结果明确写出来，不能以“工具存在”代替“任务已验证”。
5. 让安全和质量检查成为可选择、可追踪的覆盖范围，而不是暗中增加访问权或自动开启高风险动作。

对 WUQ 的直接决定是：保留现有的用户完成契约、简单/专家结果、Intent Router、Browser capability clarity、Repair mapping、Security coverage visibility 和 Evidence boundary；本阶段不增加新的运行时功能、不重写 Core、不引入外部项目代码，也不把研究样本变成 GA 或商业资格证据。

## 2. 研究边界与证据分级

- 执行位置：当前对话工作区；源执行指令中关于“新窗口”的要求由用户的当前对话要求覆盖。
- 抓取时间：2026-09-10 05:05（Asia/Tokyo，API 快照时间）；官方页面与仓库页面在同日复核。
- 研究对象：公开 GitHub 项目。样本同时包含 GitHub 按公开星数排序的 Global Top-50 快照和与 Agent、浏览器、质量、安全、策略、适配器相关的公开项目。
- 事实：只记录当前公开页面或 API 直接展示的名称、星数、语言、安装入口、能力边界和文档结构。
- 设计推断：由上述事实归纳出的可迁移原则，明确标记为推断，不当作项目方声明。
- WUQ 决定：只表示本项目是否 KEEP、GUARDED、DEFERRED，不表示外部项目的质量排名。
- NOT_MEASURED：没有进行的真实用户、真实 Host、跨机器安装、外部项目修复、留存、成功率、稳定性、许可证兼容性或商业资格验证。

本文件是原创的研究摘要。所有观察均以链接指向官方 GitHub 页面；没有复制外部项目的源代码、资源、截图或 README 原文。

## 3. Source snapshot A — GitHub Global Top-50 by public stars

来源：[GitHub Search API](https://api.github.com/search/repositories?q=stars%3A%3E100000&sort=stars&order=desc&per_page=50)。查询条件为 stars 大于 100000、按 stars 降序、每页 50；返回的 total_count 为 127，本表保留当时前 50 项。星数是时间点快照，不是质量、正确性、维护承诺或用户完成率。

| Rank | Repository | Stars snapshot | Language |
|---:|---|---:|---|
| 01 | [codecrafters-io/build-your-own-x](https://github.com/codecrafters-io/build-your-own-x) | 546,230 | Markdown |
| 02 | [sindresorhus/awesome](https://github.com/sindresorhus/awesome) | 504,517 | — |
| 03 | [public-apis/public-apis](https://github.com/public-apis/public-apis) | 478,091 | Python |
| 04 | [freeCodeCamp/freeCodeCamp](https://github.com/freeCodeCamp/freeCodeCamp) | 455,221 | TypeScript |
| 05 | [EbookFoundation/free-programming-books](https://github.com/EbookFoundation/free-programming-books) | 396,359 | Python |
| 06 | [openclaw/openclaw](https://github.com/openclaw/openclaw) | 389,305 | TypeScript |
| 07 | [donnemartin/system-design-primer](https://github.com/donnemartin/system-design-primer) | 369,018 | Python |
| 08 | [nilbuild/developer-roadmap](https://github.com/nilbuild/developer-roadmap) | 366,735 | TypeScript |
| 09 | [jwasham/coding-interview-university](https://github.com/jwasham/coding-interview-university) | 360,644 | — |
| 10 | [vinta/awesome-python](https://github.com/vinta/awesome-python) | 319,559 | Python |
| 11 | [awesome-selfhosted/awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) | 318,193 | — |
| 12 | [obra/superpowers](https://github.com/obra/superpowers) | 283,963 | Shell |
| 13 | [practical-tutorials/project-based-learning](https://github.com/practical-tutorials/project-based-learning) | 282,775 | Python |
| 14 | [996icu/996.ICU](https://github.com/996icu/996.ICU) | 276,933 | — |
| 15 | [mattpocock/skills](https://github.com/mattpocock/skills) | 257,802 | Shell |
| 16 | [affaan-m/ECC](https://github.com/affaan-m/ECC) | 255,071 | JavaScript |
| 17 | [facebook/react](https://github.com/facebook/react) | 249,637 | JavaScript |
| 18 | [torvalds/linux](https://github.com/torvalds/linux) | 247,626 | C |
| 19 | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | 243,825 | Python |
| 20 | [trimstray/the-book-of-secret-knowledge](https://github.com/trimstray/the-book-of-secret-knowledge) | 242,880 | — |
| 21 | [TheAlgorithms/Python](https://github.com/TheAlgorithms/Python) | 224,417 | Python |
| 22 | [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) | 217,384 | TypeScript |
| 23 | [vuejs/vue](https://github.com/vuejs/vue) | 212,027 | TypeScript |
| 24 | [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | 211,868 | — |
| 25 | [ossu/computer-science](https://github.com/ossu/computer-science) | 208,872 | HTML |
| 26 | [anomalyco/opencode](https://github.com/anomalyco/opencode) | 206,145 | TypeScript |
| 27 | [n8n-io/n8n](https://github.com/n8n-io/n8n) | 203,870 | TypeScript |
| 28 | [tensorflow/tensorflow](https://github.com/tensorflow/tensorflow) | 199,306 | C++ |
| 29 | [DigitalPlatDev/FreeDomain](https://github.com/DigitalPlatDev/FreeDomain) | 198,344 | Markdown |
| 30 | [trekhleb/javascript-algorithms](https://github.com/trekhleb/javascript-algorithms) | 196,670 | JavaScript |
| 31 | [ultraworkers/claw-code](https://github.com/ultraworkers/claw-code) | 195,199 | Rust |
| 32 | [microsoft/vscode](https://github.com/microsoft/vscode) | 191,502 | TypeScript |
| 33 | [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) | 189,985 | Python |
| 34 | [massgravel/Microsoft-Activation-Scripts](https://github.com/massgravel/Microsoft-Activation-Scripts) | 189,919 | Batchfile |
| 35 | [ohmyzsh/ohmyzsh](https://github.com/ohmyzsh/ohmyzsh) | 189,647 | Shell |
| 36 | [Significant-Gravitas/AutoGPT](https://github.com/Significant-Gravitas/AutoGPT) | 187,237 | Python |
| 37 | [jackfrued/Python-100-Days](https://github.com/jackfrued/Python-100-Days) | 186,215 | Jupyter Notebook |
| 38 | [CyC2018/CS-Notes](https://github.com/CyC2018/CS-Notes) | 185,965 | — |
| 39 | [getify/You-Dont-Know-JS](https://github.com/getify/You-Dont-Know-JS) | 184,847 | — |
| 40 | [avelino/awesome-go](https://github.com/avelino/awesome-go) | 183,636 | Go |
| 41 | [microsoft/markitdown](https://github.com/microsoft/markitdown) | 182,160 | Python |
| 42 | [ollama/ollama](https://github.com/ollama/ollama) | 180,531 | Go |
| 43 | [flutter/flutter](https://github.com/flutter/flutter) | 178,877 | Dart |
| 44 | [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) | 178,347 | TypeScript |
| 45 | [521xueweihan/HelloGitHub](https://github.com/521xueweihan/HelloGitHub) | 175,691 | Python |
| 46 | [github/gitignore](https://github.com/github/gitignore) | 175,679 | — |
| 47 | [anthropics/skills](https://github.com/anthropics/skills) | 175,416 | Python |
| 48 | [twbs/bootstrap](https://github.com/twbs/bootstrap) | 174,758 | MDX |
| 49 | [f/prompts.chat](https://github.com/f/prompts.chat) | 169,798 | HTML |
| 50 | [huggingface/transformers](https://github.com/huggingface/transformers) | 165,040 | Python |

### Snapshot interpretation

Top-50 的内容混合了学习资源、目录、基础设施、框架、运行时和 Agent；因此不能把“高星”直接解释成“适合 WUQ”。本阶段采用两层筛选：先完整冻结 50 项快照，再对与“人类完成任务、权限、证据、适配、恢复和质量反馈”相关的项目做哲学抽样。

## 4. Source snapshot B — GitHub Trending weekly page

来源：[GitHub Trending weekly](https://github.com/trending?since=weekly)。页面是动态内容；当天 HTML 读取暴露了 20 个项目卡片，但没有提供可稳定复核的完整 50 项排名和统一指标。因此本阶段不写入 Trending 的排名或增长量，只把它当作当天的补充信号。

当日暴露的 20 个卡片名称为：DietrichGebert/ponytail、affaan-m/ECC、fmtlib/fmt、tt-a1i/archify、mattpocock/skills、blader/humanizer、NousResearch/hermes-agent、ChromeDevTools/chrome-devtools-mcp、heygen-com/hyperframes、ayghri/i-have-adhd、mksglu/context-mode、openai/skills、coreyhaines31/marketingskills、openai/plugins、THU-MAIC/OpenMAIC、Imbad020/academic-research-skills、every-app/open-seo、ruvnet/ruflo、llvm/llvm-project、petergyang/no-ai-slop。

这一区域的结果只支持“当天公开页面显示过这些项目卡片”，不支持项目质量、增长、维护或用户成功率的断言。

## 5. 哲学抽样与分类

下表把“项目做什么”与“可以迁移的设计哲学”分开。观察列是公开页面的压缩转述；哲学列是本阶段的推断；WUQ 列是受当前证据约束的处理决定。

| 项目 | 用户工作与边界的观察 | 可迁移设计哲学 | WUQ 处理 |
|---|---|---|---|
| [build-your-own-x](https://github.com/codecrafters-io/build-your-own-x) | 用可执行的学习路径把抽象主题拆成能动手的项目入口。 | 第一次成功应落到一个可操作的小闭环，而不是先理解完整体系。 | KEEP：继续以真实用户任务作为演化单位；不复制内容目录。 |
| [sindresorhus/awesome](https://github.com/sindresorhus/awesome) | 用统一目录组织大量分散资源，入口价值来自可导航性。 | 复杂能力首先需要可找、可选、可退出的导航。 | KEEP：简单入口；DEFERRED：新增能力市场。 |
| [public-apis/public-apis](https://github.com/public-apis/public-apis) | 以分类、元数据和贡献约束支持发现外部接口。 | 外部能力应有明确适配边界和可审查元数据。 | GUARDED：适配器可描述能力，不能改变 Authority。 |
| [freeCodeCamp/freeCodeCamp](https://github.com/freeCodeCamp/freeCodeCamp) | 学习路径将说明、练习和反馈串成渐进任务。 | 用户状态要能知道“做到哪一步”和“下一步是什么”。 | KEEP：结果保留验证项与 nextAction。 |
| [free-programming-books](https://github.com/EbookFoundation/free-programming-books) | 资源库重在覆盖面、分类和可持续整理，而非单一执行器。 | 资料与执行分离，资料不能冒充执行证据。 | KEEP：报告与真实执行证据分层。 |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | 本地 Gateway 连接 CLI、控制界面、消息渠道、模型、工具和插件；公开文档同时强调 onboarding、状态检查、权限配对和 sandboxing。 | 一个本地控制平面可以承载多入口，但可信边界必须独立于渠道和模型。 | KEEP：Core/Host/Adapter 分层；DEFERRED：渠道扩张。 |
| [system-design-primer](https://github.com/donnemartin/system-design-primer) | 用主题分层组织系统设计材料，让读者按问题域深入。 | 分层信息结构比把全部细节塞进首屏更耐用。 | KEEP：Simple View / Expert View。 |
| [developer-roadmap](https://github.com/nilbuild/developer-roadmap) | 用阶段和依赖关系表达长期学习路线。 | 长任务需要阶段性完成条件，而不是只有最终目标。 | KEEP：16 阶段 ledger；不把阶段数当成用户操作数。 |
| [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) | 目录把自托管项目按用途、部署和许可等维度组织。 | 选择工具时要同时看到能力、部署负担和责任边界。 | GUARDED：doctor 说明能力；不据目录推断兼容性。 |
| [obra/superpowers](https://github.com/obra/superpowers) | 公开流程从澄清目标、短设计、计划、实现到测试和审查；同一能力按多个 harness 分发。 | 在执行前获得可读的目标确认，在执行后提供反馈闭环；适配器可薄。 | KEEP：用户完成契约和 Host 边界；不复制其工作流内容。 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 技能被设计成小而可组合；公开入口区分 managed read-only 与用户拥有的 editable 安装。 | 可组合不等于自动扩权；安装方式应向用户说明更新和所有权。 | KEEP：Skill 只提供提示/证据；不成为权限来源。 |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | 把计划、测试、实现、审查、验证、记忆和改进组织成流程，并列出不同 harness 的能力状态。 | 过程能力应有支持矩阵，不能用“已安装”代替“已验证”。 | KEEP：Capability / Evidence 分离；NOT_MEASURED：外部 harness 实测。 |
| [anomalyco/opencode](https://github.com/anomalyco/opencode) | 以开源 coding agent 作为可运行入口，并把仓库指令、安装、贡献和安全文件放在同一项目边界。 | 一个清晰的入口需要同时有使用路径、开发路径和安全路径。 | KEEP：分离用户路径和开发证据；不复制其界面。 |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | 公开项目覆盖本地、容器和服务化运行，也允许多种模型或 Agent 连接；文档提示直接文件系统访问的风险。 | 多环境支持必须与权限模型和部署警告一起交付。 | GUARDED：记录 Host/Browser/权限；DEFERRED：服务化扩张。 |
| [aider-ai/aider](https://github.com/aider-ai/aider) | 终端入口把代码库理解、Git 变更、lint 和测试反馈放进一条 pair-programming 回路。 | 变更工具的核心价值是短反馈回路，而不是一次生成更多文件。 | KEEP：修复后必须验证；不扩大自动写权限。 |
| [cline/cline](https://github.com/cline/cline) | 同一 Agent 引擎面向 IDE、CLI 和桌面入口，包含人工审批、扩展和自动化边界。 | 多入口共享 Core，审批应是显式状态而非隐含在入口里。 | KEEP：authority handshake；NOT_MEASURED：外部 Cline 适配实测。 |
| [Roo-Code](https://github.com/RooCodeInc/Roo-Code) | 公开模式将只读问答、架构说明和全权限代码工作区分开，并在工具调用处要求批准。 | 复杂能力用模式分级，普通用户不必暴露内部状态，但高风险动作要停下来。 | KEEP：普通用户隐藏内部标签；GUARDED：危险动作可多问。 |
| [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) | 终端入口配合工具、MCP、JSON 输出、扩展安装和 troubleshooting/release 文档。 | 机器可读输出、故障排查和发布验证应与主入口同等可发现。 | KEEP：TaskResult/JSON；NOT_MEASURED：Gemini harness 真实安装。 |
| [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent) | 公开路径区分模型设置、Docker/云运行和批处理执行，任务是明确的输入输出单元。 | 长流程应能转成可复跑的任务记录，同时注明运行环境。 | KEEP：Evidence Ledger；DEFERRED：批量外部项目运行。 |
| [browserbase/stagehand](https://github.com/browserbase/stagehand) | 浏览器 SDK 将自然语言动作与代码动作组合，并提供提取、缓存、恢复性动作和 MCP 集成。 | 高层便利功能应落在可观察的低层动作上，并保留结构化结果。 | KEEP：Browser capability clarity；不把 API key 当测量证据。 |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | 云任务支持 task-in/result-out，也区分黑盒编排和工具集成，并提供独立 judge 结果。 | 任务结论与执行工具解耦；判定器也应有独立证据边界。 | GUARDED：把 verdict 标为独立证据；NOT_MEASURED：云任务。 |
| [browser-use/web-ui](https://github.com/browser-use/web-ui) | 本地或 Docker 路径提供持久浏览器、定制浏览器和远程可视化入口。 | 跨环境体验要显式说明运行方式、会话持久性和可见性。 | KEEP：Browser status 分层；DEFERRED：VNC/远程浏览器。 |
| [browser-use/desktop](https://github.com/browser-use/desktop) | 桌面 Agent 以多平台安装包、模型提供商和外部输入渠道组合能力。 | 桌面包装层可以换，核心任务和权限协议不应复制多份。 | GUARDED：Adapter only；NOT_MEASURED：安装包。 |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | 以参考服务器和社区服务器表达外部工具接入生态。 | 扩展点应是可声明、可替换、可验证的 adapter，不是把外部逻辑塞进 Core。 | KEEP：Thin Adapter 方向；DEFERRED：服务器市场。 |
| [microsoft/playwright](https://github.com/microsoft/playwright) | Browser automation/test 既有库、CLI、测试、报告、trace 和 VS Code 入口；文档列出浏览器安装、隔离、locator、auto-wait 和跨平台。 | “能启动浏览器”只是前置能力；导航、目标可达、执行和证据要分段呈现。 | KEEP：Stage 04 capability model；当前缺 Playwright 仍是 NOT_MEASURED。 |
| [dequelabs/axe-core](https://github.com/dequelabs/axe-core) | 可访问性引擎嵌入现有测试，报告 violations 与 incomplete，并明确仍需人工复核。 | 自动检查的“不完整”是结果的一部分，不应被压成 PASS。 | KEEP：security/accessibility coverage visibility。 |
| [GoogleChrome/lighthouse](https://github.com/GoogleChrome/lighthouse) | 本地 Chrome 审计可通过 CLI 产生 JSON/HTML，也支持插件和自定义 audit；运行范围是本地环境。 | 报告格式和运行范围必须同时可见，不能把本地审计说成外部用户验证。 | KEEP：报告分层；NOT_MEASURED：真实外部项目。 |
| [semgrep/semgrep](https://github.com/semgrep/semgrep) | 本地 CLI、CI、Docker 和规则定制并存，部分平台能力需要登录。 | 本地可用与平台增强要分开声明，登录不是默认权限升级。 | GUARDED：安全 opt-in；不自动联网。 |
| [open-policy-agent/opa](https://github.com/open-policy-agent/opa) | 策略引擎把规则决策从业务服务中分离，服务传入上下文并取得 allow/deny 等决定。 | Authority 应由可审查的策略决定，执行器不能自行把建议变成授权。 | KEEP：Host reasons/implements；Router/Skill no authority。 |
| [guardrails-ai/guardrails](https://github.com/guardrails-ai/guardrails) | 验证器可组合，输出既可被解析验证，也可配置失败时继续、抛错或重新请求。 | 失败处理是显式策略；验证器不能只给一个无上下文的绿色结果。 | KEEP：reasonCode 与 incomplete boundary。 |
| [aquasecurity/trivy](https://github.com/aquasecurity/trivy) | 扫描器和目标分离，覆盖文件系统、镜像、Git、Kubernetes、依赖、漏洞、配置、秘密和许可等不同范围。 | 质量结论必须带 target、scanner 和覆盖范围，不能用一个“安全”标签概括。 | KEEP：securityCoverage；NOT_MEASURED：外部扫描。 |
| [renovatebot/renovate](https://github.com/renovatebot/renovate) | 自动发现依赖并提出 PR，公开信息包含更新年龄、采用度、通过率、合并信心、限流、排队和人工审批路径。 | 自动化应产生可审阅的提案，并保留排序、等待和人工门槛。 | GUARDED：只生成 mapping/plan；不自动合并或发布。 |
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | 以可组合工作流连接许多节点和外部系统，核心价值是组合，而不是单一模型。 | 组合能力要有边界和可观察中间状态，否则“自动化”会变成不可解释的长链。 | DEFERRED：不引入工作流平台；KEEP：短链、可回放。 |
| [microsoft/vscode](https://github.com/microsoft/vscode) | 稳定编辑器核心通过扩展和多种语言/工具集成扩张。 | 扩展生态应依赖稳定 Core contract，扩展不能重定义核心语义。 | KEEP：Core + Thin Adapters；NOT_MEASURED：真实 VS Code adapter。 |
| [microsoft/markitdown](https://github.com/microsoft/markitdown) | 聚焦把多种输入转换为统一的可处理文本表示，适配范围比核心转换语义更易替换。 | 先统一结果表示，再增加输入适配，避免每个入口维护一套语义。 | KEEP：TaskResult/schema；DEFERRED：更多格式。 |
| [ollama/ollama](https://github.com/ollama/ollama) | 本地模型运行时把模型拉取、运行和 CLI/API 入口分离。 | 本地运行的便利不代表模型输出可信；运行状态、模型来源和结果证据要分开。 | GUARDED：记录 runtime capability；不以本地成功冒充 Host 结果。 |
| [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) | 以抓取、搜索、提取等结构化能力服务 Agent 或应用。 | 外部数据获取应输出来源和范围，抽取结果不等于目标页面已完成。 | KEEP：Evidence Graph；DEFERRED：远程抓取。 |
| [anthropics/skills](https://github.com/anthropics/skills) | 以可复用技能包扩展 Agent 工作方式，技能与 harness 入口分开。 | 可复用知识应是低权限指导层，不能成为事实、许可或写入权限的权威。 | KEEP：Skill non-authority。 |
| [huggingface/transformers](https://github.com/huggingface/transformers) | 一个相对稳定的模型库核心覆盖多种模型、后端和任务。 | 核心抽象要稳定，后端适配要可替换，能力矩阵不能隐藏差异。 | KEEP：Capability registry；DEFERRED：模型后端扩张。 |

### 样本边界

上表的项目数量超过 20，覆盖了 Agent、Harness、Browser、Testing、Accessibility、Security、Policy、Dependency、Workflow、Runtime 和学习/目录类项目。未在表中逐项抽取的 Top-50 项目仍被完整冻结在 Source snapshot A 中；它们的星数和语言是事实，未测量的产品哲学不被补写成事实。

## 6. 去重后的设计原则

### P01 — First success is a small observable loop

用户第一次完成的动作应包含输入、最小执行、可读结果和下一步，而不是先学习内部名词。学习型目录、终端 Agent、浏览器工具和本地助手虽然产品形态不同，但共同把第一步落在可执行命令、一次对话、一个样例或一个可见状态。

WUQ 影响：KEEP 一句话入口与用户完成契约；不增加安装前的架构问卷。

### P02 — Installation is a ladder, not a single promise

成熟项目通常同时提供快速入口、明确前置条件、平台差异、更新/卸载路径或 troubleshooting。所谓“零配置”只能描述某一条路径，不能替代跨平台验证。

WUQ 影响：Stage 10 只做安装路径决策，不在 Stage 09 直接重写；把未运行过的平台标为 NOT_MEASURED。

### P03 — One Core, many surfaces

OpenClaw、Cline、Superpowers、VS Code、MCP 和浏览器项目都展示了不同程度的“核心能力与入口/扩展分离”。可迁移的不是某个目录，而是契约：入口传入意图，Core 产出语义结果，Adapter 负责接线，Host 负责权限与实际执行。

WUQ 影响：KEEP Core/Host/Adapter 边界；任何新 adapter 都不复制 scope、receipt、drift、evidence 或 claim engine。

### P04 — Progressive disclosure protects ordinary users

模式、命令、专家 JSON、详细 trace 和内部路由标签适合调试与审查，不适合成为普通用户的必修课。只读、计划、执行和高风险操作需要不同的确认层。

WUQ 影响：KEEP Simple View / Expert View；Router 内部标签不出现在默认结果；危险动作可多轮澄清。

### P05 — Capability is a state machine, not a boolean

浏览器、模型、网络、凭据、运行时和外部项目都存在“安装了但不能启动”“启动了但目标不可达”“可达但没有证据”等中间状态。Playwright、Trivy、OPA 和多种 Agent 项目都把目标、工具、策略或扫描范围拆开。

WUQ 影响：KEEP Browser Capability Clarity；不以 browserAvailable、nodePresent 或工具安装成功替代 BROWSER_VERIFIED。

### P06 — Evidence and verdict are separate objects

自动检查可以给出 finding、incomplete、judge、lint、trace、JSON 或报告；这些是证据形态。是否解决、是否通过、是否可发布是更高层的主张，必须由充分证据支持。

WUQ 影响：KEEP reasonCode、Evidence Graph、Receipt/Hash、securityCoverage；NOT_MEASURED 不得升级成 PASS。

### P07 — Authority should be explicit and policy-backed

OPA 将策略决策从执行服务分离；Cline、Roo Code、OpenClaw 等公开路径强调审批、配对、沙箱或风险提醒。便利的自然语言入口不应自动得到写文件、凭据或远程访问权限。

WUQ 影响：KEEP Host reasons/implements；Router、Skill、报告和 research 不拥有 Authority。

### P08 — Recovery is part of the happy path

可恢复不是只给失败者的附录：状态检查、重复安装、更新、重试、队列、回滚、trace、独立判定和 troubleshooting 都帮助用户从半成功状态继续。

WUQ 影响：KEEP append-only ledger 与失败留存；Stage 15 只删除无必要复杂度，不删除失败证据。

### P09 — Cross-platform claims need a matrix

Windows、macOS、Linux、WSL、容器、桌面和云环境的安装方式、浏览器依赖、权限、路径和服务状态不同。公开项目提供矩阵或平台专门入口时，用户更容易知道自己处于哪条路径。

WUQ 影响：Stage 10/11/12 分别测量安装、Harness 和 Host；没有对应运行就写 NOT_MEASURED。

### P10 — Automation should propose before it commits

Repair mapping、Renovate、Guardrails、浏览器 judge 和 Agent 审批都说明了一个共同边界：系统可以发现、解释、映射、提出变更或请求确认；真正写入、合并、发布和高风险调用应由显式 Authority 完成。

WUQ 影响：KEEP Repair Mapping as read-only mapping；DEFERRED autonomous repair/auto-merge/publish。

## 7. 交叉比较矩阵

### 7.1 用户第一次成功

| 形态 | 公开项目中的典型路径 | 可以迁移的检查点 | WUQ 状态 |
|---|---|---|---|
| 学习/目录 | build-your-own-x、freeCodeCamp、developer-roadmap | 能否从一个小任务开始，能否看到进度和下一步 | KEEP |
| 终端 Agent | Aider、Gemini CLI、OpenCode、SWE-agent | 安装/认证/一次任务/机器结果是否可分别确认 | KEEP |
| 桌面/本地助手 | OpenClaw、OpenHands、Browser Use Desktop | 启动服务、连接入口、实际任务和权限是否分开 | GUARDED |
| 浏览器/质量工具 | Playwright、Stagehand、axe-core、Lighthouse | 浏览器能力、目标可达、检查结果、人工复核是否分开 | KEEP |

### 7.2 Core 与适配器

| Core 应负责 | Adapter/Harness 可负责 | 不应由 Adapter 负责 |
|---|---|---|
| 意图语义、TaskResult、reasonCode、证据边界、scope、claim boundary | 安装接线、能力发现、自然语言转发、Host handshake、工具桥接、结果渲染 | Scope engine、Receipt/HMAC、drift oracle、Evidence Graph 规则、Authority 决策 |
| 稳定的失败分类与恢复提示 | CLI、IDE、桌面、MCP、浏览器或其他宿主的输入输出格式 | 把安装存在、Skill 建议或模型回答升级成 VERIFIED/PASS |

### 7.3 自动化与人类门槛

| 自动化可以做 | 需要显式确认或真实证据 |
|---|---|
| 解析请求、发现能力、生成候选 mapping、运行只读检查、形成报告、提示 nextAction | 写文件、提交/合并、远程发布、读取凭据、访问受限目标、宣称已解决、宣称 GA/Stable |
| 生成可复跑的任务记录和结构化结果 | 真实 Host/External Holdout、外部用户成功率、法律/许可与商业资格 |

## 8. 对 WUQ 的决策表

| WUQ 现状 | 决定 | 理由 |
|---|---|---|
| 一句话普通入口与 0–1 次澄清 | KEEP | 对应 P01/P04；已有 Stage 06 回归证明，继续演化需以用户完成为主。 |
| Simple View 与 Expert View | KEEP | 对应 P04/P06；内部标签和完整证据仍可审查，但不压给普通用户。 |
| reasonCode、TaskResult schema、Evidence Graph | KEEP | 对应 P05/P06；语义结果和原始证据需要稳定机器边界。 |
| Browser Capability Clarity | KEEP | 对应 P05/P09；当前 Playwright 环境缺失只能保持 NOT_MEASURED。 |
| Repair Mapping | KEEP / GUARDED | 对应 P03/P10；映射可自动化，但不授予 Router 写权限。 |
| Security coverage opt-in | KEEP / GUARDED | 对应 P06/P07；禁用时明确 NOT_MEASURED，启用时仍不扩大 Authority。 |
| 立即重写为 Node/原生多平台 | DEFERRED 到 Stage 10 决策 | 研究只能说明安装梯度的重要性，不能替代 clean-machine 数据。 |
| Hosted Browser、远程 Agent、插件市场 | DEFERRED | 会引入凭据、网络、租户、费用和法律边界，当前用户请求没有授权这些扩张。 |
| 自动修复、自动合并、自动发布 | DEFERRED | 研究支持“提案先于提交”，不支持扩大当前权限。 |
| GA/Stable/Commercial claim | BLOCKED / NOT_ELIGIBLE | 研究样本和本地回归不能替代 Real Host、External Holdout、法律身份与商业门槛。 |

## 9. 明确未测量与不能推出的结论

1. GitHub stars 只是公开时间点信号，不代表项目质量、用户完成、正确率、维护承诺或许可适配。
2. GitHub Trending 页面是动态页面，当天读取只暴露 20 个卡片；没有写入不存在的 Top-50 Trending 排名。
3. 未在本阶段对外部项目执行安装、登录、浏览器任务、修复、回归、更新、卸载、跨平台运行或真实用户访问。
4. 未取得 Codex、Claude Code、OpenCode、Cursor/VS Code 等外部 Harness 的 Real Host 结果；当前本地测试不是这些 Harness 的实测替代。
5. 未取得 1000 个真实用户、12 个月真实留存、真实商业转化或外部 Holdout 数据；用户提供的两个 HTML 和一个报告中的合成/推演数字不被本文件重述为真实证据。
6. 未根据外部项目的许可证、星数、赞助或组织信息推断 WUQ 的开源、商业或发布资格。
7. 本阶段没有改变 WUQ 源代码、schema、expected/oracle、权限模型或发布状态。

## 10. Round record

### Round 1 — source and sample freeze

- 读取当日 [GitHub Trending](https://github.com/trending?since=weekly)。
- 通过公开 [GitHub Search API](https://api.github.com/search/repositories?q=stars%3A%3E100000&sort=stars&order=desc&per_page=50) 冻结 50 项 Global Top-50 by public stars。
- 记录动态页面只暴露 20 项、未写入不稳定排名的限制。
- 选取 Agent、Harness、Browser、Testing、Security、Policy、Adapter 和开发者工具样本。

### Round 2 — philosophy extraction

- 对样本按用户工作、入口、Core/Adapter、权限、结果和恢复边界归类。
- 对 OpenClaw、Superpowers、mattpocock/skills、ECC、OpenHands、Aider、Cline、Roo Code、Gemini CLI、Stagehand、Browser Use、Playwright、axe-core、Lighthouse、OPA、Guardrails、Trivy、Renovate 等官方页面做定向复核。
- 将页面事实与本文件的设计推断分栏，未运行的行为全部保留为 NOT_MEASURED。

### Round 3 — independent dedupe and WUQ mapping

- 合并重复的“简单入口”“分层能力”“Core/Adapter”“显式权限”“证据与 verdict 分离”“可恢复”“跨平台矩阵”主题，得到 P01–P10。
- 只把最小影响映射到 WUQ 已有边界；没有因为样本流行度新增运行时功能。
- 复核本文件没有外部源代码、资源、截图或 README 原文，也没有把 Trending 卡片当作完整 Top-50 排名。

## 11. Integrity check

- 研究交付物：本文件一份。
- Stage 09 协议：stage-09/protocol.md。
- WUQ 源代码变更：0。
- 预期/Oracle 变更：0。
- 权限、Host、发布状态变更：0。
- 外部项目代码或资源导入：0。
- 研究结论中保留了 stars、Trending 动态性、Real Host、External Holdout、真实用户和商业资格的证据边界。
