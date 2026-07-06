# Neo4j GraphRAG Query Term Graph Design

## 背景

本仓库 `jd-query-graph` 是一个新的内部后端工具，不继承旧
`seektalent-keyword-graph` 的 SQLite bundled snapshot / 轻量 runtime 目标。

本工具的目标是把大量固定格式 JD 导入 Neo4j，使用 LLM/Neo4j GraphRAG 从 JD 中抽取
可用于简历检索的候选 query term，建立 query term 之间的证据化关系，再用 CTS count
API 给可检索词补充召回数量。查询时，输入一个词，返回该词自身的 CTS 召回数量，以及
图谱中相近、变体、相关或共现 query term 的召回数量和证据。

本设计必须以效果优先。LLM 预算充足，不以省 token、省调用次数为首要目标。但效果优先
不等于允许无约束生成：所有抽取、关系、召回观测都必须能追溯到证据、schema 和后处理
判定。

## 长期云服务目标

第一阶段只证明 schema、数据流、抽取边界和查询返回结构可验证；它不是生产云服务设计。
长期目标必须拆成两个平面：

- build plane：离线或批处理构建图谱，负责 JSONL import、source/run/hash 记录、LLM/GraphRAG
  抽取、term normalization、Neo4j 写入、关系校验、CTS probe queue 和 serving snapshot 发布。
- serving plane：给 agent 或后端服务提供只读查询，优先读取 materialized adjacency snapshot，而不是
  让高 QPS 查询直接压到 Neo4j traversal。

Neo4j 是 authoring graph、审查图和图分析底座；大规模 agent 查询应由 read-optimized serving
snapshot 承担，以便缓存、灰度、回滚、限流和权限治理。

## 当前事实

已有可用语料来自 `/Users/frankqdwang/MLE/jd-graph`：

- primary corpus:
  `/Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/source=jobs_bytedance/factual_jobs_mainland.jsonl`
- 本地验证行数：9530
- 文件大小：约 16MB
- source manifest:
  `/Users/frankqdwang/MLE/jd-graph/config/sources/bytedance_jobs_2026_05_12.json`
- captured date: `2026-05-12`
- run id: `bytedance_jobs_2026_05_12_win_sync`

当前仓库已有初始 scaffold：

- `configs/taxonomy.yaml`
- `configs/relationships.yaml`
- `src/jd_query_graph/config.py`
- `src/jd_query_graph/jd_input.py`
- `src/jd_query_graph/cli.py`
- `docker-compose.yml`
- 基础 pytest / ruff 验证

当前 `configs/` 中的 `Skill`、`Tool`、`Framework`、`ProgrammingLanguage` 等细粒度
节点类型只是脚手架，不是本设计的最终 graph schema。它们必须被本设计中的抽象 schema
替代或迁移。

## 输入数据

第一版直接使用 ByteDance mainland JD JSONL。文件可以复制到目标仓库本地 ignored data
目录，例如：

```text
data/corpora/bytedance/factual_jobs_mainland.jsonl
```

`data/` 已被 `.gitignore` 忽略。该 corpus 是本地工作输入，不提交到 git。

ByteDance corpus 是第一阶段本地验证样例，不是长期唯一输入源。生产输入合同必须把数据来源和
JSONL 内容分开描述，至少记录：

- `source_id`
- `source_type`
- `schema_version`
- `captured_at`
- `license_public_source_policy`
- `jsonl_uri`
- `content_hash`
- `import_run_id`

本机绝对路径只能出现在 README example 或本地默认值中，不得作为长期测试合同或跨环境接口。

一条输入 JD 是 JSONL 的一行。实际字段以旧 `jd-graph` 的 canonical job contract 为准，
而不是当前 README 中的临时简化格式。

核心字段：

- `canonical_source_key`: JD 稳定源 ID。
- `source_url`: 原始 JD URL。
- `job_id`: 外部职位 ID，可选。
- `title`: 职位名。
- `team`: 团队或部门字段。
- `location`: 地点文本。
- `cities`: 城市数组。
- `job_type`: 正式、实习等。
- `responsibilities`: 职责数组。
- `qualifications`: 要求数组。
- `raw_snapshot_path`: 原始快照路径。
- `raw_snapshot_sha256`: 原始快照 hash。
- `collected_at`: 采集时间。
- `parse_confidence`: 解析置信度。

抽取文本主要由以下字段组成：

- `title`
- `team`
- `responsibilities`
- `qualifications`
- 必要时附带 `location` / `cities` 作为上下文，不作为默认 query term 来源。

## 目标图谱

Neo4j 主图只保留少量稳定 node label。业务分类放在节点属性或边属性里，而不是膨胀成大量
label。

### Node Labels

#### `JobPosting`

一条 JD。

关键属性：

- `job_posting_id`: 内部 ID，可从 source/canonical key 派生。
- `canonical_source_key`
- `source_url`
- `external_job_id`
- `title`
- `team`
- `location`
- `cities`
- `job_type`
- `raw_snapshot_path`
- `raw_snapshot_sha256`
- `collected_at`
- `source_company`
- `source_id`
- `run_id`

#### `QueryTerm`

一个候选简历检索词。它可能来自 LLM/GraphRAG 抽取、后处理生成、人工审查导入或未来其他
抽取器。第一版重点是 LLM/GraphRAG 抽取。

关键属性：

- `term_id`
- `text`: 原始词面。
- `normalized_text`: 规范化文本，仅使用通用文本标准化，不包含具体词对映射。
- `term_category`: 抽象类型枚举。
- `language`: `zh | en | mixed | unknown`
- `source`: `llm_graphrag | postprocess | manual | imported`
- `status`: `candidate | accepted | rejected | needs_review`
- `evidence_count`
- `created_at`
- `updated_at`

`term_category` 初始枚举：

- `CAPABILITY`: 能力、职责、经验要求或可迁移能力。
- `TECH_OBJECT`: 技术对象、工具、平台、系统、产品或工程对象。此枚举不区分语言、框架、数据库、云服务等细类。
- `DOMAIN_CONTEXT`: 业务领域、业务场景、行业场景。
- `ROLE_CONTEXT`: 岗位、职能、角色上下文。
- `QUALIFIER`: 检索限定词或修饰条件。
- `UNKNOWN`: 模型无法稳定归类，保留待后处理或审查。

这些枚举是 schema 约束，不是词表。代码和配置不得写入具体词到具体枚举的映射。

### Term Identity And Normalization

`QueryTerm` identity 必须可重复生成，不能依赖插入顺序或 LLM 临时输出 ID。

- `text` 保留原始词面。
- `normalized_text` 只做通用规范化：trim、Unicode normalization、大小写折叠、全半角归一、
  空白折叠、通用标点归一。不得在这里写具体同义词或别名映射。
- `language` 由通用字符和语言检测产生，枚举为 `zh | en | mixed | unknown`。
- `term_key` 由 `normalized_text + language + source_scope` 派生，用于幂等 upsert。
- `term_id` 由稳定 hash 派生，输入至少包含 `term_key` 和 schema version。
- `canonical_term_id` 只允许由 accepted `SAME_AS` / `VARIANT_OF` 后处理或人工审查产生，第一阶段
  可以为空。

同一 extractor 或不同 extractor 多次抽到相同 `term_key` 时，必须 merge 到同一 `QueryTerm`，
并通过 `MENTIONED_IN` 增加 evidence，不得重复创建不可区分节点。

#### `RecallObservation`

一次 provider 召回观测。第一 provider 是 CTS。

关键属性：

- `observation_id`
- `provider`: 第一版为 `cts`。
- `query_text`
- `query_mode`
- `total`
- `status`
- `recall_bucket`
- `observed_at`
- `probe_run_id`
- `request_hash`
- `error_code`
- `created_at`

LLM 不得创建 `RecallObservation`。该节点只能由 provider probe 写入。

## Relationship Types

关系必须通过 Neo4j 边表示，不使用 `TermGroup` 这类节点表达同义组、近义组或社区。
同义组、近义组、社区检测是图算法或离线分析的派生结果，不是 LLM 直接抽取的事实节点。

### `MENTIONED_IN`

`(:QueryTerm)-[:MENTIONED_IN]->(:JobPosting)`

表示 query term 来自某条 JD 的某段文本。

必要属性：

- `source_field`: `title | team | responsibilities | qualifications`
- `source_index`: 数组字段中的 index，可选。
- `evidence_text`
- `char_start`
- `char_end`
- `extractor`
- `model`
- `confidence`
- `status`

### `SAME_AS`

`(:QueryTerm)-[:SAME_AS]->(:QueryTerm)`

表示两个 query term 在简历检索中基本可替换。该关系必须非常严格。不能仅凭 embedding 相近
或单次 LLM 判断接受。

必要属性：

- `evidence_type`
- `evidence_text`
- `source_jd_ids`
- `candidate_source`
- `confidence`
- `extractor`
- `model`
- `status`

### `VARIANT_OF`

`(:QueryTerm)-[:VARIANT_OF]->(:QueryTerm)`

表示写法、语言、缩写、大小写、符号、版本或表达变体。不得通过硬编码具体词对判断。

必要属性同 `SAME_AS`。

### `RELATED_TO`

`(:QueryTerm)-[:RELATED_TO]->(:QueryTerm)`

表示招聘检索语义上相关，但不可直接替换。该关系可用于扩展检索、推荐相邻 query term 或召回
诊断。

必要属性同 `SAME_AS`，并额外建议记录：

- `relation_rationale`: 模型或后处理给出的简短理由。

### `CO_OCCURS_WITH`

`(:QueryTerm)-[:CO_OCCURS_WITH]->(:QueryTerm)`

表示两个 term 在 JD、字段或窗口中共同出现。该关系主要由程序统计产生，不依赖 LLM 判定。

必要属性：

- `cooccurrence_count`
- `window_type`: `job | field | paragraph | sentence | fixed_window`
- `support`
- `score`
- `sample_evidence`
- `status`

### `HAS_RECALL`

`(:QueryTerm)-[:HAS_RECALL]->(:RecallObservation)`

表示 query term 有一次 provider recall observation。

必要属性：

- `provider`
- `query_mode`
- `probe_run_id`
- `created_at`

### Relationship Semantics

所有 term-term 关系都禁止 self-loop。关系唯一键至少包含：

```text
source_term_id + relationship_type + target_term_id + candidate_source + evidence_hash
```

方向性规则：

- `SAME_AS` 是对称语义，但物理存储只保留 canonical ordered pair，查询层负责双向展开。
- `VARIANT_OF` 是有方向关系，方向为 variant term -> canonical term。canonical term 不存在或尚未确认时，
  该关系只能保持 `candidate` 或 `needs_review`。
- `RELATED_TO` 默认有方向，方向表示 evidence 或模型提出的 source -> target 解释；查询层可以按配置
  返回反向边，但必须标明方向。
- `CO_OCCURS_WITH` 是对称统计语义，物理存储保留 canonical ordered pair。

状态机：

```text
candidate -> needs_review -> accepted
candidate -> rejected
needs_review -> rejected
```

只有 `accepted` 关系进入 serving snapshot。`SAME_AS` 不自动传递；A=B、B=C 是否推出 A=C
必须由单独的 validation run 产生新关系和 evidence。

## 禁止硬编码

代码、配置和测试不得写入具体业务词对或具体词类映射来制造效果。

禁止示例：

- `K8s = Kubernetes`
- `Go = Golang`
- `大模型 = LLM`
- `Python` 属于某个固定类型
- 固定技术词白名单
- 固定同义词表
- 为了通过测试而写 fixture-specific branch

允许配置：

- node label 枚举。
- `QueryTerm.term_category` 枚举。
- relationship type 枚举。
- relation status 枚举。
- evidence type 枚举。
- LLM prompt version。
- 抽取批大小、重试、并发、置信度阈值。
- 字符串相似、embedding 相似、图相似、共现统计的通用阈值。

## LLM / Neo4j GraphRAG 使用方式

Neo4j GraphRAG 用作抽取 adapter，不拥有整个业务架构。

它负责：

- 按手写 schema 从 JD 文本中抽取 `QueryTerm`。
- 在允许关系类型内提出候选 term-term relationship。
- 为每个候选节点和候选关系返回 evidence snippet、confidence、model metadata。

它不负责：

- 直接接受最终关系。
- 写入 CTS recall observation。
- 决定最终 query term 是否可服务。
- 生成硬编码词表。
- 随意扩展 schema。

Neo4j GraphRAG schema 必须手写并版本化。可以使用自动 schema extraction 做探索，但不能把自动推断 schema 直接作为生产 schema。

由于效果优先，第一阶段允许使用更强 LLM、更大的上下文、更保守的复核调用和更多候选 pair 评估。
但所有 LLM 调用都必须写入 run metadata，保证可复盘：

- model
- provider
- prompt version
- input hash
- output hash
- created_at
- retry count
- extraction run id

## 关系发现与判定

关系判定分两步：候选生成和接受判定。

### 候选生成

候选 term pair 可以来自以下通用信号：

- `llm_extraction`: GraphRAG 在同一 chunk 内提出候选关系。
- `text_similarity`: 通用字符串相似，不包含具体词对映射。
- `embedding_similarity`: term + evidence context 的向量相似。
- `context_similarity`: term 周围 evidence text 的语义相似。
- `graph_neighbor_similarity`: term 连接到相似 JD、字段、场景或邻居结构。
- `cooccurrence`: 同一 JD、字段、段落、句子或固定窗口内共现。

不得对所有 term 做无限制两两 LLM 判断。即使预算充足，也要通过候选生成减少无意义比较，原因
是质量和可解释性，不是成本。

### 接受判定

每条非统计关系进入图谱时必须有：

- allowed relationship type。
- evidence snippet。
- source JD 或 source context。
- candidate source。
- confidence。
- model metadata。
- status。

关系接受原则：

- `SAME_AS`: 最高门槛。必须表示两个词可替换搜索。低置信时进入 `needs_review`，不自动接受。
- `VARIANT_OF`: 必须说明变体类型，但不得依赖硬编码词对。
- `RELATED_TO`: 可以更宽，但必须说明招聘检索上的关联理由。
- `CO_OCCURS_WITH`: 由统计生成，记录窗口、频次、score 和样例 evidence。
- `HAS_RECALL`: 只能来自 CTS probe。

CTS recall 不用于创造语义关系，但可用于后处理风险判断。例如，一个 `SAME_AS` 候选如果两个词
召回数量差距极端，应降级为 `needs_review` 或拒绝。

## CTS Provider Contract

CTS count probe 是独立 provider 集成，不允许由 LLM、fixture 或 query API 伪造。Provider contract
必须定义：

- `query_text`
- `query_mode`: `exact | normalized | quoted | provider_default`
- timeout、retry、backoff 和 rate limit。
- `request_hash`: 由 provider、query_text、query_mode 和 provider options 派生，用于幂等去重。
- `probe_run_id`: 一批 probe 的稳定 run id。
- `observed_at` 和 TTL，用于判断 recall observation 是否 stale。
- `status`: `ok | error | timeout | rate_limited | suppressed | unknown`
- `error_code` 和 provider 原始错误分类。
- `recall_bucket`: 面向 serving 的 bucketed count，可用于隐私保护。

低频或敏感 query 的返回策略必须由 provider 层统一处理。Serving 层不得绕过 provider 的
suppression 或 bucket 规则直接暴露 raw count。

## 社区检测与派生分组

同义组、近义组、概念组、社区不作为 LLM 抽取节点。

后续可以使用 Neo4j GDS 或离线算法在 term-term 图上生成派生结果：

- connected components
- Louvain / Leiden community
- node similarity
- weighted relationship projection

派生结果可以写为 `QueryTerm` 属性或单独 artifact，例如：

- `community_id`
- `community_run_id`
- `community_score`

但派生结果必须记录算法、输入边类型、权重策略和 run id。

## 数据流

第一版端到端流程：

1. 将 ByteDance mainland corpus 复制到 ignored `data/corpora/bytedance/`。
2. 按 canonical job contract 读取 JSONL。
3. 将每条 JD 写入 Neo4j `JobPosting`。
4. 为每条 JD 生成 extraction text。
5. 调 Neo4j GraphRAG / LLM 抽取 `QueryTerm` 和候选关系。
6. 写入 `QueryTerm`、`MENTIONED_IN`、候选 term-term relationships。
7. 程序生成 `CO_OCCURS_WITH`。
8. 对候选关系做后处理校验，更新 status。
9. 对 accepted / serviceable query terms 执行 CTS count probe。
10. 写入 `RecallObservation` 和 `HAS_RECALL`。
11. 查询 API 输入 term，返回 exact term、召回数量、相邻 term、关系类型、召回数量和证据。

生产服务化时，第 11 步不应直接依赖在线 Neo4j traversal。Build plane 应发布 serving snapshot，
Serving plane 只读 snapshot 并按版本返回结果。

## 查询行为

输入：

```text
<用户输入词>
```

查询处理：

- 生成 `normalized_query`，用同一套通用 normalization 规则查找 `QueryTerm.normalized_text`。
- 同时支持 exact surface match 和 normalized match，并在 response 中标明 match type。
- 默认只返回 accepted relationships；debug 或审查接口才允许返回 candidate/needs_review。
- 支持 `relationship_types` filter、`limit`、`cursor` 和 stable sort。
- 排序默认综合 relationship type、status、confidence、recall freshness、cooccurrence score 和 evidence count。
- 如果 latest recall observation 超过 TTL，返回 `stale` 标记，不同步刷新 CTS，除非调用方使用显式
  refresh gate。

返回结构应包含：

- exact match / normalized match。
- exact term 的 CTS total。
- `SAME_AS` / `VARIANT_OF` 邻居及 CTS total。
- `RELATED_TO` 邻居及 CTS total。
- `CO_OCCURS_WITH` 邻居及 CTS total。
- 每条关系的 evidence 和 confidence。
- 如果没有 CTS observation，明确返回 `unknown`，不得伪造数量。
- `response_version`
- `snapshot_id`
- `generated_at`
- `recall_status`: `ok | stale | suppressed | unknown | error`
- pagination cursor。

## Security, Privacy, And Abuse Prevention

CTS 背后可能代表大规模简历数据。即使本系统只读取 count，也必须把 query 服务视为敏感接口。

必须设计：

- authentication 和 service-to-service authorization。
- agent access policy：哪些 agent、任务或环境可以查哪些 provider 和 source scope。
- rate limit、quota 和 burst control，防止枚举式 query probing。
- audit log：记录调用方、query hash、query mode、response status、snapshot id 和 request id。
- secret 管理：CTS credential、LLM credential 和 Neo4j credential 不进入 repo、artifact 或日志。
- 日志脱敏：默认记录 hash 或 bucket，不记录完整敏感 query 和 provider error body。
- low-frequency suppression 和 count bucketing。
- sensitive query filter，用于拒绝或降级可能泄漏敏感属性的 query。
- LLM data-retention policy：明确 JD 文本、prompt、completion 是否可被 provider 保留。
- prompt-injection 防护：JD 文本是非可信输入，不能改变 system/developer prompt 或写入权限。

## 验收标准

第一阶段不是证明系统已生产可用，而是证明 schema、数据流和抽取机制可用且可审查。

必须完成：

- 9530 行 ByteDance mainland corpus 可在目标仓库本地读取。
- README 中简化 JD schema 被 canonical job contract 替换。
- `configs/taxonomy.yaml` 改为本设计的 node label + term category schema。
- `configs/relationships.yaml` 改为本设计的 relationship schema。
- GraphRAG schema 由配置生成或与配置一致。
- fake extraction artifact writer 至少覆盖 20 条真实 JD 的输入结构，用于验证 artifact schema。
- 真实 GraphRAG extraction spike 不属于 Phase 1 scaffold，必须进入 Phase 2 并另有显式 gate。
- 每个 `QueryTerm` 至少有一条 `MENTIONED_IN` evidence。
- 每条 LLM 候选 term-term relation 有 evidence snippet、confidence、model metadata 和 status。
- 不存在具体词对硬编码。
- `CO_OCCURS_WITH` 由统计生成，不由 LLM 硬判。
- CTS probe 可以先使用 fake provider 做结构验证，但 fake observation 也必须符合正式
  `RecallObservation` 字段合同；真实 CTS 必须另有显式人工 gate。
- 查询 API 或 CLI 能返回一个输入 term 的邻居、关系、证据和 recall observation 状态。

真实抽取开启前的质量 gate：

- 抽样检查至少 100 个真实 GraphRAG 产出的 QueryTerm，记录适合作为简历检索词的比例。
- 抽样检查至少 50 条真实 GraphRAG 产出的 term-term relation，分别统计明显正确、可疑、错误。
- 对 `SAME_AS` 和 `VARIANT_OF` 单独统计错误率；如果明显乱连，不允许继续扩大到全量 corpus。
- 如果 GraphRAG 输出噪声很高，正确结论是调整 schema/prompt/后处理，而不是扩大数据量掩盖问题。

## 非目标

第一阶段不做：

- 用户侧轻量包。
- SQLite bundled snapshot。
- UI。
- 全自动发布流程。
- 全量真实 CTS probe。
- 云服务 serving API、auth、rate limit、snapshot publish 和 load test。
- 把社区检测结果作为 LLM 抽取节点。
- 用硬编码词表制造看似准确的关系。

## 风险与未知

- Neo4j GraphRAG 的 KG Builder 能否稳定抽出适合作为简历检索的 QueryTerm，需要 spike 验证。
- `SAME_AS` / `VARIANT_OF` 的误连风险高，必须保守处理。
- `RELATED_TO` 可能过宽，需要通过 evidence、confidence 和 CTS recall 共同约束。
- GraphRAG schema API 属于可用但仍需本仓库适配的外部依赖，不能假设其行为完全符合业务目标。
- LLM 预算充足可以提升覆盖和复核强度，但不能替代证据、schema 和后处理。
