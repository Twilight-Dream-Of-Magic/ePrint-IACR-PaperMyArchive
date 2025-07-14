# Information Winding Theory 工程宪章（不可删除）

硬性约束：`iwt_research/TODO.md` 不能删除，且主线语义不可漂移。

## 工程主旨 / Mission
IWT 工程是一个对称密码函数结构检测套件：
1. 输入：算法实现 + 类型（Block/Stream/Hash）+ 输入输出规模。
2. 执行：必须经过 `iwt_core` 原子算子链。
3. 输出：高维点阵结构、微函数连接结构、TM-1/TM-2/TM-3 结论与可验证报告。

## Immutable Mainlines（ID/Title 不可改）
1. `M1_theory_correctness_alignment`  
   `Paper-correct theory anchors are implemented as executable objects.`
2. `M2_misread_and_semantic_guardrails`  
   `Known semantic misreads are blocked by protocol-level guardrails.`
3. `M3_engineering_alignment_with_paper`  
   `Core implementation aligns with paper definitions and threat-model layering.`
4. `M4_engineering_extensions_and_risk_control`  
   `Engineering extensions, diagnostics, and added controls are explicit and auditable.`

## 当前锁定执行策略
1. 单一 CLI 主链：`analyze` + `verify`。
2. 删除兼容债：不保留 legacy facade 命令和模块。
3. 强制 C++ 路径：非 `iwt_core` 后端直接失败（`IWT_CORE_REQUIRED`）。
4. 报告契约：仅接受 `v3`，不迁移旧报告。

## Threat Models（中英双语语义）
1. `threat_model_1_black_box` (TM-1)
   - 中文：仅允许观测层输出轨迹与投影统计，禁止机制侧字段参与判定。
   - English: Observation-only mode; mechanism-side annotations are excluded from decisions.
2. `threat_model_2_instrumented` (TM-2)
   - 中文：允许插桩事件与增强状态用于机制解释，但不回灌 TM-1 判定。
   - English: Instrumented events/state are allowed for diagnostics without feeding TM-1 decisions.
3. `threat_model_3_intervention` (TM-3)
   - 中文：先 TM-1 筛查，再生成干预计划，再执行 TM-2 聚焦探针形成闭环证据。
   - English: TM-1 screening -> intervention planning -> TM-2 focused probes.

## Canonical Engineering Anchors（论文/文档必须引用这些真实路径）
- `iwt_research/run_experiment.py`
- `iwt_research/pipeline/block_workflow.py`
- `iwt_research/pipeline/block_core.py`
- `iwt_research/pipeline/block_runner.py`
- `iwt_research/pipeline/tm1_runner.py`
- `iwt_research/verify/report_contracts.py`
- `iwt_research/metrics/trajectory/aggregate.py`
- `iwt_research/core/ops_kernel.py`
- `iwt_research/core/ops_trace.py`
- `iwt_research/app/analyze.py`
- `iwt_research/algorithm_api/loader.py`
- `iwt_research/algorithm_api/builtin_iwt_core.py`
- `iwt_research/iwt_core/include/iwt/plugin_api.hpp`

## 报告契约（v3）
必须包含：
- `report_schema_version = "v3"`
- `evidence_schema_version = "v3"`
- `native_capability`
- `execution_backend = "iwt_core"`
- `atomic_trace_digest`
- `threat_model_semantics`
- `composition_structure_diagnosis`

契约验证入口：`iwt_research/verify/report_contracts.py`。

## 主线实施清单（持续执行）
1. 继续维持 `run_experiment.py` 薄编排，不回流到单大函数。
2. 维持 pipeline 分层边界，不在 CLI 层写统计逻辑。
3. 维持高维图模块化（neighbor/coupling/reachability/cycles/evidence）。
4. 文档与论文锚点只允许指向本页 canonical anchors。
