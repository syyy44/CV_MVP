# V2 UI 方案：面试官工作台

> 读者：前端 / 后端 / 设计  
> 基线：`.gstack/qa-reports/qa-report-localhost-2026-06-12.md`（15 条痛点，面试官贴合度 58/100）  
> 一句话：后端数据已足够，问题在 Persona 与信息架构。重排信息、脚本优先、裁掉工程师观测面。  
> 修订：2026-06-12 v3（重写：对比降级为浮层、验收改为可见状态、删冗余）

---

## 1. 目标与定位

### 1.1 定位

primary user 是「明天要进会议室的面试官」。本产品按**真实招聘工具**设计，UI 只服务面试官。

代价：作为 take-home，工程深度（观测 / 审计 / 台账 / 注入防御）不在主 UI 直接陈列，评审需经 README、Langfuse 或 `audit-export` API 验证。  
缓解：把工程严谨度用面试官能懂的形式留在产品里——脚本内**证据原文**、`评分依据` Tab 的维度分与 `risk_flags`、hold 卡的**注入拦截说明**。这些既建立面试官信任，也是评审可见的工程信号。

### 1.2 要做到的三件事（以屏上状态验收，不计秒表）

| 目标 | 可验收的状态 |
|------|--------------|
| **快速排序** | 看板首屏，每位候选人无需展开即可见：推荐结论 + 分数 + 风险/待核实计数 + 单一主 CTA |
| **直接带走** | 面试准备首屏默认是面试脚本，必问 3 题可见，一键复制 Markdown |
| **hold 不卡壳** | 待定候选人首屏即见：风险说明 + 核实清单 + 判定建议 |

> 「快」是设计意图，但验收以**可见状态**为准。固定的 3 人演示案例无法用秒表客观证明「30 秒决策」，故不写时间门槛。

### 1.3 信任信息 vs 工程师观测

| 类型 | 示例 | 处理 |
|------|------|------|
| 面试官信任信息 | 简历原文引用、评分理由、风险标记、置信度 | **UI 保留**（脚本内联 / 评分依据 Tab） |
| 工程师观测面 | 可观测性 Tab、审计 JSON 导出、台账浏览器、Langfuse 徽章、Token/延迟 | **从 UI 删除** |
| 后端能力 | Langfuse trace、SQLite 决策事件、audit-export API | **保留**，仅运维 / 评审经 Langfuse 或 API 使用 |

---

## 2. Persona 与任务

| 角色 | 场景 | 成功标准 | 阶段 |
|------|------|----------|------|
| 业务/技术面试官 | 收到 3–5 份 HR 筛过的简历 | 快速排出面试顺序 | P0 |
| 同上 | 面试前 30 分钟准备 | 拿到必问题 + 红旗 + 疑点，可复制 | P0 |
| 同上 | hold 候选人 | 清楚为什么待定、先核实什么 | P0 展示 / P1 字段 |
| 同上 | 拿不准两人选谁 | 并排看技能缺口差异 | P1 |
| 同上 | 面完记录结论 | 笔记 + 人工改推荐 | P2 |

维护者 / 评审不是 UI 用户：经 Langfuse、`audit-export` API、README 完成验证。

---

## 3. 信息架构

### 3.1 Before → After

```
Before（V1，工程师视角）
  顶部：Langfuse 状态 · 版本 · 回放
  Tabs：排名 │ 档案 │ 可观测性 │ 审计导出

After（V2，面试官视角）
  顶部：产品名 · [新建运行] · 模式徽章（实时/回放）
  主 Tabs：候选看板 │ 面试准备
  对比：看板上多选触发的轻量浮层，非独立 Tab（见 4.4）
```

主视图只有两个 Tab。横向对比降级为浮层，原因见 4.4。

### 3.2 从 UI 删除的模块

| 删除项 | 原用途 | 删除后如何完成 |
|--------|--------|----------------|
| `Observability` 视图 | 台账、节点耗时、修复遥测 | Langfuse + 日志 |
| `Audit` 审计导出 UI | 下载 `audit-export.v1` JSON | API / README curl |
| `AdvancedPanel` | 收纳上述 | 整组件删除 |
| TopBar Langfuse 徽章 | 强化 LLM demo 感 | `/health` 仍返回，UI 不展示 |
| 首页 schema/台账/Langfuse 文案 | 工程师叙事 | 改面试官叙事（§5） |

后端不动：`tracing.py`、`ENABLE_LANGFUSE`、`audit-export`/`events` API、台账写 SQLite。  
面试官 UI 不动：脚本/追问旁证据原文、`评分依据` Tab、LiveProgress。

### 3.3 导航与 URL

| 参数 | 取值 | 默认 |
|------|------|------|
| `run` | `run_id` | session 内当前 run |
| `tab` | `board` \| `prep` | `board` |
| `candidate` | `candidate_id` | prep 时必填 |

行为契约：

1. 看板主 CTA → 一次操作进入 `tab=prep&candidate={id}`。  
2. 准备页切换候选人 → 同步 `candidate` 参数（链接可分享）。  
3. 后退回到上一组合。  
4. `tab=prep` 无 `candidate` → 默认选看板第 1 个 `completed`。

对比浮层是看板内的临时状态，不进 URL（关闭即回看板）。

### 3.4 Tab 职责

| Tab | 职责 | 不承载 |
|-----|------|--------|
| 候选看板 | 排序、筛选、多选触发对比 | 长篇评分正文 |
| 面试准备 | 脚本、hold 卡、深读依据 | 跑批 telemetry |

---

## 4. 页面方案

### 4.0 候选人 / 运行状态

| 候选人 `status` | 看板展示 | 主 CTA | 进准备页 |
|-----------------|----------|--------|----------|
| `pending`/`running` | 灰显行 +「处理中」 | 禁用 | 否 |
| `completed` | 完整决策行 | 见 4.1 | 是 |
| `needs_review` | 「需复核」+ 一句原因 | 查看原因（只读） | 只读，无脚本 |
| `failed` | 「失败」+ `error` 前 80 字 | 查看原因 | 否 |

| Run `status` | 看板顶栏 |
|--------------|----------|
| `running` | 「筛选进行中」+ 跳 LiveProgress |
| `completed` | JD 标题（P1）· N 人 · 筛选 chips（P1） |
| `failed` | 错误摘要 +「新建运行」 |

### 4.1 候选看板

解决：UX-007（对比入口）、UX-008（卡片过载）、UX-011（置信度不可行动）、UX-014（rubric 编号外露）。

布局：表格式行 + `border-b`，非厚卡片。行本身不可点；只有主 CTA 和多选 checkbox（P1）可交互。

```
┌─────────────────────────────────────────────────────────────┐
│  本次筛选 · 3 名候选人                         [新建运行]    │
│  按匹配分数排序。用右侧按钮进入面试准备。                      │
├─────────────────────────────────────────────────────────────┤
│ #1  李伟        89  ●通过    0 风险 · 0 待核实   置信：高    │
│     六年后端，超过 Python 年限门槛              [准备面试 →]   │
│ #2  陈浩        63  ◐待定    ⚠ 1 风险 · 3 待核实  置信：中    │
│     Python/FastAPI 基础，注入风险已拦截         [先做核实 →]   │
└─────────────────────────────────────────────────────────────┘
```

主 CTA 随推荐变化：

| `recommendation` | 按钮 | 目标 |
|------------------|------|------|
| `proceed` | 准备面试 | `tab=prep&candidate=id` |
| `hold` | 先做核实 | 同上（prep 展示 hold 卡） |
| `reject` | 查看原因 | 同上（prep 默认切「评分依据」） |

字段：

- `decision_summary`：一行 ≤ 60 字。P0 取 `match_reason[0]`；P1 后端字段。  
- `risk_count` / `verification_count`：见 §6.3。  
- 置信度 band + hover：见 §5.2。

**筛选（P1）：** chip `[全部] [通过] [待定] [拒绝]`，数字为本 run 计数。默认「全部」= `recommendation != reject`（隐藏拒绝），点「拒绝」才显示拒绝行。离开「拒绝」回到上一非拒绝 chip，避免空列表。

**多选 → 对比（P1）：** 勾选 2 人（仅 `completed`）→ 看板底部浮动条「已选 2 人 · 对比」→ 打开对比浮层（4.4）。不足 2 人不显示浮动条。

### 4.2 面试准备

解决：UX-002（题包深埋）、UX-003（导出）、UX-005（首屏倒置）、UX-009（证据折叠）、UX-010（无优先级/时间盒）。

唯一导出动作：**复制脚本** → 剪贴板 Markdown（§6.6）。不做 PDF / 打印 / 发送。

```
┌─────────────────────────────────────────────────────────────┐
│  李伟 · ●通过 89 · 置信：高                    [复制脚本]     │
│  [面试脚本] [评分依据] [候选人画像]   ← 默认：面试脚本        │
├─────────────────────────────────────────────────────────────┤
│  建议面试 ~45 分钟 · 必问 3 题 + N 追问 + M 选问              │
│  ▍必问（默认展开）                                          │
│  ▍模糊点追问（默认展开前 3 条，附证据原文）                  │
│  ▍选问 [展开]                                              │
└─────────────────────────────────────────────────────────────┘
```

子 Tab：

| Tab | 内容 | 默认展开 |
|-----|------|----------|
| 面试脚本 | 必问 / 追问 / 选问 + 时长 | 必问全展开；追问前 3；选问折叠 |
| 评分依据 | 维度条、match_reason、risk_flags | reject 经 CTA 进入时自动选中此 Tab |
| 候选人画像 | 结构化简历摘要 | 次要 |

差异：

- `proceed`：脚本区占满首屏，无 hold 卡。  
- `hold`：4.3 行动卡置顶，脚本在其下缩短展示（必问仍可见）。

候选人切换：顶栏下拉，变更时更新 URL；每项 `姓名 · 推荐徽章 · 分数`。

### 4.3 hold 行动卡

解决：UX-006（待定无指引）、UX-009（hold 最需要证据）。

```
┌─────────────────────────────────────────────────────────────┐
│  陈浩  ◐待定 63 · 中置信                                     │
├─────────────────────────────────────────────────────────────┤
│  ⚠ 为什么待定（默认展开，每条附 [查看原文]）                  │
│  ✔ 通过前必须核实（verification_checklist）                  │
│  判定建议：{pass_criteria}                                    │
└─────────────────────────────────────────────────────────────┘
```

内容优先级（从上到下）：

1. `risk_flags`（含注入）——每条一句说明 + 证据链接  
2. 导致 hold 的关键 `match_reason`（≤ 2 条）  
3. `verification_checklist`（P1 独立字段；P0 用 `follow_ups` 占位，标「建议核实」）  
4. `pass_criteria`（§6.4）

### 4.4 候选人对比（浮层，P1）

解决：UX-007。

**为什么是浮层不是 Tab：** 真实场景只在「两人难取舍」时对比，且演示固定 3 人。独立 Tab + 决策矩阵对此体量过度设计。降级为看板上勾 2 人弹出的轻量浮层，读完即关，不占主 IA、不进路由。

```
┌──────────────────────────────────────────────┐
│  对比                                    [×]   │
├────────────────┬───────────────┬──────────────┤
│                │   李伟 89      │   陈浩 63     │
│ 推荐           │   ●通过        │   ◐待定       │
│ 必备技能       │   92 ███▉      │   75 ███      │
│ AI 工程成熟    │   90 ███▉      │   60 ██▌      │
│ 经历相关性     │   90 ███▉      │   70 ██▊      │
│ 风险           │   —           │   ⚠ 注入      │
│ 待核实         │   0           │   3           │
├────────────────┴───────────────┴──────────────┤
│  [准备面试：李伟]   [先做核实：陈浩]            │
└────────────────────────────────────────────────┘
```

要点：

- 固定 2 人并排；维度 mini bar 对齐，缺口一眼可见。  
- 维度行固定顺序：推荐、`required_skills`、`ai_engineering_maturity`、`experience_relevance`、风险、待核实。  
- **不写自动决策提示句**（面试官自己读）。  
- 底部 CTA 直接跳对应候选人准备页。  
- 窄屏：浮层内表格 `overflow-x: auto`，首列 sticky。

---

## 5. 文案与置信度

### 5.1 面试官叙事

| 位置 | 文案 |
|------|------|
| 首页主标题 | 候选人筛选与面试准备 |
| 首页副标题 | 上传 JD 与简历，几分钟拿到排名和可直接带进会议室的面试脚本。每条结论都附简历原文。 |
| 看板说明 | 按匹配分数排序。用右侧按钮进入面试准备。 |
| 复制成功 toast | 面试脚本已复制，可粘贴到笔记或飞书文档。 |

主路径禁词：schema、台账、Langfuse、token、span、audit-export、有界修复。

### 5.2 置信度 band

| band | 展示 | hover |
|------|------|-------|
| 高 | 置信：高 | 各维度评分一致、证据充分，可直接安排面试。 |
| 中 | 置信：中 | 部分维度证据偏弱或有待核实点，建议先看追问再定。 |
| 低 | 置信：低 | 评分冲突或证据不足，建议 hold 或缩短面试以核实为主。 |

映射（P0 前端）：`>= 0.85` 高；`0.65–0.85` 中；`< 0.65` 低。P1 可由后端 `confidence_band` 覆盖。

---

## 6. 数据与接口

### 6.1 脚本数据源

| 阶段 | 数据源 |
|------|--------|
| P0 | 前端读 `dossier` + 本地规则 |
| P1 | `GET /api/candidates/{id}/interview-script`，后端为唯一真相，删除前端 `buildInterviewScript` 业务逻辑 |

迁移用 `script_rule_version` 字段标记，便于回归对比。

### 6.2 必问规则

**v1（P0）：** `dossier.questions` 按 difficulty 降序取前 3 题为必问，其余为选问，`follow_ups` 为追问。时长默认 `expert 10 / senior 8 / mid 6 / junior 5` 分钟，`suggested_duration_min = Σ必问 + 4×追问 + 5`。局限：未按 JD 缺口选题，UI 标「v1」。

**v2（P1）：** 必问优先覆盖未满足的 must-have 与最低分维度，再按难度补齐。

输入：`questions[]`（`competency`/`difficulty`/`rubric_refs[]`）、`score.sub_scores`、`score.requirement_results[]`（`requirement_id`/`met`/`weight`/`display_label`）。

步骤：

1. 取 `sub_scores` 最低的 2 个维度（并列优先级 `required_skills` > `ai_engineering_maturity` > `experience_relevance`）。  
2. 取 `requirement_results` 中 `met=false` 且 `weight >= must_have`，按 weight 降序。  
3. 题与维度/requirement 关联：题有 `rubric_refs` 则直接归入；否则用 `competency` 关键词匹配 §6.2.1 映射表。  
4. 凑满 3 题：先每个未满足 must-have 选 1 题（难度高者优先），再每个最低分维度选 1 题，最后按难度补齐。  
5. 选问 = 剩余题按难度降序。  
6. 追问 = 全部 `follow_ups`，与 `verification_checklist` 同文本去重。

标记 `script_rule_version: "v2"`；每道必问附 `selection_reason`（`must_have_gap`/`dimension_gap`/`difficulty_fill`，调试用，UI 不展示）。

#### 6.2.1 维度—能力关键词映射

| 维度 | 命中词 |
|------|--------|
| `required_skills` | Python, FastAPI, 后端, API |
| `ai_engineering_maturity` | LangGraph, LLM, 编排, RAG, prompt |
| `experience_relevance` | 年限, 项目, 上线, 生产 |
| `project_depth` | 架构, 性能, p95, 吞吐 |
| `communication_clarity` | 沟通, 协作, 文档 |

演示期望（陈浩 hold）：必问应含 1 题覆盖 `ai_engineering_maturity` 缺口 + 1 题覆盖注入/风险，而非纯难度 Top3。

### 6.3 看板计数字段

| 字段 | 计算 |
|------|------|
| `risk_count` | `len(risk_flags)` |
| `verification_count` | `len(verification_checklist)`；P0 无字段时用 `len(follow_ups)`，标签写「待核实」不加粗 |
| `decision_summary` | P1 后端一句；规则：首条正向 `match_reason` 或首条 risk 短句 |

### 6.4 hold checklist 与 pass_criteria

`verification_checklist` 生成（P1）：

1. 纳入所有 `follow_ups`；  
2. 有注入类 risk → 插入「请候选人说明简历中异常指令的来源」；  
3. 每个未满足 must-have → 插入「请具体说明 {display_label} 的满足情况」；  
4. 去重后 cap 5 条；  
5. 按 risk > must-have > follow_up 排序。

`pass_criteria` 模板：

```
若以上 {n} 条核实均有可信、可核对简历或项目的答复，可将推荐调整为「通过」；否则维持「待定」。
```

### 6.5 接口清单

| 优先级 | 接口 | 说明 |
|--------|------|------|
| P0 | — | dossier 足够 |
| P1 | `GET /api/candidates/{id}/interview-script` | v2 规则 + checklist |
| P1 | `CandidateRunResult` 增字段 | `decision_summary`, `risk_count`, `verification_count`, `confidence_band` |
| P2 | `POST/PATCH/GET .../notes` | 面后笔记 |
| P2 | `PATCH .../decision` | 人工改推荐 + 台账事件 |
| P2 | rubric `display_label` | UX-014 |
| 不做 | `interview-script.pdf` / `.md` 服务端 | 复制即可 |
| 保留不展示 | `audit-export`、events API | 维护者用 |

`interview-script` 响应（P1）：

```jsonc
{
  "candidate_id": "...",
  "script_rule_version": "v2",
  "suggested_duration_min": 45,
  "sections": [ /* must_ask | follow_up | optional */ ],
  "verification_checklist": [
    { "item": "...", "reason": "must_have_gap", "evidence_refs": [] }
  ],
  "pass_criteria": "若以上 3 条核实均有可信答复…"
}
```

### 6.6 复制脚本 Markdown 格式

```markdown
# 面试脚本 — {候选人姓名}
岗位：{jd_title 或「本次筛选」} · 推荐：{通过|待定|拒绝} · 分数：{overall}
置信：{高|中|低} · 建议时长：~{N} 分钟

## 必问
1. [{难度}] {题干}
   - 要点：…
   - 红旗：…
   - 建议时长：{n} 分钟

## 模糊点追问
- {追问}（依据：{证据摘要}）

## 选问（时间充裕）
- …

（hold 时追加）
## 待核实（通过前）
1. …
判定：{pass_criteria}
```

不含内部 requirement_id、trace id、token。单候选人单次复制，不做批量。

---

## 7. 设计系统

- Tailwind + shadcn；`proceed`/`hold`/`reject` 语义色 + 图标双编码（不只靠颜色）。  
- 看板：表格式行，仅 CTA/checkbox 可点。  
- 对比浮层：表格横向滚动 + sticky 首列。  
- Accordion 仅用于选问、评分标准全文。  
- 证据：脚本区默认渲染 1 条 `EvidenceSpanView`，其余按需。  
- 无打印样式。

字号：

| 元素 | 约定 |
|------|------|
| 看板姓名 | `text-base font-medium` |
| 决策摘要 | `text-sm text-muted-foreground` |
| 脚本题干 | `text-sm`，序号 `font-semibold` |
| 正文最小 | ≥ 16px |

---

## 8. 优先级与验收

| 阶段 | 范围 | 验收（可见状态） |
|------|------|------------------|
| **P0** | 两 Tab IA + URL 深链；看板决策行 + CTA；面试准备脚本 + 复制 Markdown；hold 行动卡（前端拼）；删除观测/审计/AdvancedPanel/Langfuse UI；§4.0 状态；面试官文案 | 见下 P0 清单 |
| **P1** | 筛选 chips（默认隐藏拒绝）；多选 → 对比浮层；`interview-script` v2 + 摘要字段；JD 标题 | 见下 P1 清单 |
| **P2** | 笔记 + 人工改推荐；rubric `display_label` | 笔记 CRUD + 改推荐写台账；展示 `display_label` |
| **P3** | 上传规模、批量动作 | 容量评估 |

**P0 验收**

- [ ] 看板每行无需展开即见：推荐徽章 + 分数 + 风险/待核实计数 + 单一主 CTA  
- [ ] 点主 CTA 一次进入 `tab=prep&candidate=`，脚本为默认首屏  
- [ ] 面试脚本首屏可见必问 3 题，复制 Markdown 成功并提示  
- [ ] hold 候选人首屏可见：风险说明 + 核实清单 + 判定建议  
- [ ] 全程无可观测性 / 审计 / 高级抽屉 / Langfuse 顶栏  
- [ ] `running` / `failed` 候选人状态不误导，CTA 行为正确  

**P1 验收**

- [ ] 默认列表不含 reject，点「拒绝」chip 才显示  
- [ ] 看板勾 2 人 → 对比浮层并排显示维度 bar，关闭回看板  
- [ ] 必问符合 v2 规则（陈浩案例含缺口题）  
- [ ] `verification_checklist` 不等于简单 follow_up 计数  

---

## 9. 明确不做

- 不重做 scoring pipeline。  
- 不恢复 Scenario B 模拟面试官。  
- 不做多租户 / 鉴权 / ATS。  
- 不在产品 UI 暴露 Langfuse / 台账 / audit-export。  
- 不做 PDF / 打印 / 发送 / 批量导出。  
- 不做横向对比独立 Tab，不做自动决策提示句。

---

## 10. 已决记录

| ID | 决议 |
|----|------|
| D1 | 双 Tab + URL 深链 |
| D2 | 从 UI 删除工程师观测面，Langfuse 仅运维侧 |
| D3 | 看板多选 → 对比；v3 进一步降级为浮层（非 Tab） |
| D4 | 仅复制 Markdown，不做 PDF/打印 |
| D5 | 筛选 chips，默认隐藏拒绝 |
| D6 | 看板仅 CTA/checkbox 可点 |
| D7 | 不做发送 |
| D8 | 笔记 + 人工改推荐放 P2 |
| D9 | （已撤销）原对比决策提示句 → v3 不做自动提示 |
| D10 | 对比表横向滚动 + sticky 首列 |
| D11 | P0 前端拼脚本 → P1 后端唯一真相 |
| D12 | P1 必问 v2（缺口优先） |
| D13 | 纯面试官产品定位，维持 D2，工程深度靠证据/评分依据/hold 卡间接体现 |

---

## 11. 修订记录

| 版本 | 变更 |
|------|------|
| v1 | 设计评审：分层指标、P0/P1 wireframe、状态机、待决事项 |
| v2 | §11 决议落地；删观测面（D2）；深化 URL/筛选/对比/v2 必问/面后闭环 |
| v3 | 重写：对比降级为浮层（删独立 Tab + 决策矩阵 + 决策提示句）；秒表指标改为可见状态验收；删冗余（合并优先级与验收、移除重复流程章节）；定位 D13 写入 §1 |
