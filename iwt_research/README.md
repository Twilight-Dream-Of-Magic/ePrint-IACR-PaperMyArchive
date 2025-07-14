# IWT Structural Analysis Suite (iwt_core Required)

## Scope / 主旨
This repository is a structural analysis suite for symmetric primitives.
用户输入算法实现、算法类型（Block / Stream / Hash）和输入输出规模，然后运行统一分析流程，得到高维点阵结构、微函数连接结构与威胁模型结论。

Execution mainline:
1. `analyze` loads an adapter (`--impl module:factory`).
2. The adapter executes through `iwt_core` atomic operators.
3. `report.json` is produced with schema `v3`.
4. `verify` checks reproducibility and report contracts.

## Non-negotiable Protocol / 不可变协议
1. `execution_backend` must be `iwt_core`.
2. `native_capability.available` must be `true` and required symbols must all be `true`.
3. Report contract is `v3` only (`report_schema_version`, `evidence_schema_version`).
4. Legacy CLI commands are removed: `run/tm3/calibrate/stream/hash/suite`.

## Threat Model Semantics / 威胁模型语义
- `threat_model_1_black_box` (TM-1)
  - 中文: 仅允许观测层输出轨迹与投影统计，禁止机制侧字段参与判定。
  - English: Observation-only mode; mechanism-side annotations are excluded from decisions.
- `threat_model_2_instrumented` (TM-2)
  - 中文: 允许插桩事件与增强状态用于机制解释，但不回灌 TM-1 判定。
  - English: Instrumented events/state are allowed for diagnostics without feeding TM-1 decisions.
- `threat_model_3_intervention` (TM-3)
  - 中文: 先 TM-1 筛查，再生成干预计划，再执行 TM-2 聚焦探针形成闭环证据。
  - English: TM-1 screening -> intervention planning -> TM-2 focused probes.

## CLI
### Analyze
```bash
py -3.14 -m iwt_research analyze \
  --impl iwt_research.algorithm_api.builtin_iwt_core:create_adapter \
  --type block \
  --input-bits 8 \
  --output-bits 8 \
  --threat-model threat_model_2_instrumented \
  --seed 0 \
  --out iwt_research/report_out/example_block
```

`--type` supports `block|stream|hash`.

### Verify
```bash
py -3.14 -m iwt_research verify --report iwt_research/report_out/example_block/report.json
```

## External Algorithm Integration
- Python adapter protocol:
  - `iwt_research/algorithm_api/protocols.py`
  - `iwt_research/algorithm_api/loader.py`
- Builtin adapter:
  - `iwt_research/algorithm_api/builtin_iwt_core.py`
- C++ plugin contract:
  - `iwt_research/iwt_core/include/iwt/plugin_api.hpp`

If adapter/report is not iwt_core-backed, analyze fails with `IWT_CORE_REQUIRED`.

## Required Report v3 Fields
Mandatory top-level fields (checked by `iwt_research/verify/report_contracts.py`):
- `report_schema_version = "v3"`
- `evidence_schema_version = "v3"`
- `native_capability`
- `execution_backend = "iwt_core"`
- `atomic_trace_digest`
- `threat_model_semantics`
- `composition_structure_diagnosis`

## Canonical Engineering Anchors
- `iwt_research/run_experiment.py`
- `iwt_research/pipeline/block_workflow.py`
- `iwt_research/pipeline/block_core.py`
- `iwt_research/pipeline/block_runner.py`
- `iwt_research/pipeline/tm1_runner.py`
- `iwt_research/metrics/trajectory/aggregate.py`
- `iwt_research/core/ops_kernel.py`
- `iwt_research/core/ops_trace.py`
- `iwt_research/app/analyze.py`
- `iwt_research/verify/report_contracts.py`

## Charter
Project charter and immutable mainlines are in `iwt_research/TODO.md`.
