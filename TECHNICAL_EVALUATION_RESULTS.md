# Technical Evaluation Results — All LLMs
**Date:** May 2026  
**Evaluated by:** Claude (separate session), Google Gemini, ChatGPT  
**Based on:** TECHNICAL_EVALUATION_PROMPT.md + PROJECT_OVERVIEW.md + GitHub repo

---

## Claude (Separate Session)

### SECTION A — Architecture Assessment

**What Is Good**

The pipeline sequencing is correct. Triage → Dedup → Supervisor → Specialist → Runbook → Correlation → HITL → Remedy is a sensible operational flow. The decision to pause at remedy and drop (never act autonomously) is the right call for a 24/7 operational environment. Many student projects get this backwards.

The snapshot pattern for email data is real engineering. Capturing email_snap_* at the moment of approval rather than reading live session state at send time shows you identified and solved an actual race condition. That kind of bug awareness is not common in student projects.

Modular Streamlit refactor (6 files from one monolithic app.py) shows software engineering discipline that most students skip.

LangGraph interrupt/resume is architecturally appropriate. Using interrupt_before = ["remedy", "drop"] to pause the state machine for human approval is exactly what LangGraph was designed for. This is non-trivial to implement correctly.

**What Should Be Redesigned**

The dual UI is the most serious architectural flaw in the project. You have two complete frontends (Streamlit on 8501, React on 5173) accessing the same agent_graph.py. This is not "offering options" — it is a split-brain risk. The HITL state lives in Streamlit session state (waiting_for_user, email_confirm_pending, email_snap_*). If an engineer uses the React UI to process a ticket that a Streamlit session already has in-flight, what happens? There is no answer in the design. You can potentially create duplicate GLPI tickets. The HITL guarantee — the system's core safety property — only holds if exactly one UI has ownership of a ticket at a time. Your architecture does not enforce this.

Streamlit session state is not application state. This is the architectural flaw underneath the dual-UI problem. Session state is per-user, in-memory, lost on restart. A real NOC has multiple engineers. Engineer A starts reviewing INC-3042. Engineer A's browser crashes. The ticket is now in limbo — in-flight in LangGraph (interrupt is pending), but no Streamlit session holds the handle. There is no recovery path. You cannot transfer ownership to Engineer B. This is a single-user prototype that has no path to multi-user without a full state management rewrite.

Two entry points to the same LangGraph pipeline without concurrency protection. react/backend/main.py and Streamlit both call agent_graph.py. SQLite (check_same_thread=False) does not make SQLite safe for concurrent writes. It disables the single-thread check and moves the problem downstream. Concurrent writes from FastAPI and Streamlit to the same noc_memory.db will corrupt the checkpointer state under load.

The correlation node is context-stuffing, not correlation. "Last 10 tickets in memory" passed to an LLM prompt is not root cause correlation. It has no time window, no topology awareness, and no threshold logic. BigPanda and Moogsoft do topological graph correlation using the actual network dependency map. What you have is best described as "contextual awareness" — useful for a demo, not reliable for operations.

The audit log is a flat JSON file. save_and_advance() appends to processed_tickets.json. After 10,000 tickets, every read loads the entire file. This is a performance cliff with a predictable arrival time.

### SECTION B — AI/LLM Design Assessment

**Is LangGraph the Right Tool?**
Yes, for the HITL interrupt/resume requirement specifically. But your pipeline is a linear DAG, not a graph. LangGraph's power is in cyclic patterns. For a strictly linear sequence, a function chain with an explicit state dataclass would be 80% fewer abstractions and easier to debug. LangGraph is correct but slightly over-engineered for the actual structure.

**Is the RAG Approach Sound?**
For 13 runbooks: yes. For production: no, and you know this. The match rates reported are cherry-picked best-case scenarios. There is no test harness, no held-out evaluation set, and no precision/recall measurement. In a real engineering review, these numbers would be treated as anecdotes, not benchmarks.

**Single LLM for All 9 Nodes**
This is a constraint, not a design choice. The correct production design uses small fast models for triage/dedup, medium models for classification, large models for specialist analysis, and medium streaming models for the chatbot. Using a 70B parameter model to log that a ticket arrived (triage_node) is waste.

**Is the Supervisor Node a Genuine Value-Add?**
Conceptually yes. Executionally questionable. Your supervisor is the same model as your specialist, running a different prompt. Two prompts sent to the same LLM weights will produce correlated errors — the same model will make the same systematic mistakes on the same types of alerts. True independence would require a different model or a fine-tuned classifier. In the demo, it corrected one mislabeling at 92% confidence. That is a compelling demonstration, not a statistical result.

**Is HITL at the Right Level?**
Yes. Pausing at ticket creation and email send is appropriate granularity for a telecom NOC. The level is correct. The implementation risk is that HITL only holds while Streamlit session state is intact.

### SECTION C — Production Readiness

**Real Blockers in Priority Order**

1. Rate limits make the system non-functional at production volumes. The pipeline makes 6-9 LLM calls per ticket. At 12,000 TPM and roughly 800-1200 tokens per call, you exhaust your budget after 1-2 tickets. During a real incident, a NOC may receive 50-200 alerts in 10 minutes.

2. No authentication is a hard blocker for any enterprise deployment.

3. Gmail SMTP is a hard blocker. Gmail has a 500 emails/day limit on free accounts. Gmail spam filters will eventually flag repeated structured NOC notifications. Using a personal Gmail account for corporate communications violates most enterprise IT security policies.

4. No LLM failure handling. The pattern `raw.replace("```json","").replace("```","")` has no try/except. One bad LLM response with a stray comma takes down the pipeline.

**Behavior Under Real Alert Volumes**
At 100 alerts/hour: 100 × ~8 LLM calls = 800 serial API calls. At ~30 seconds per ticket (optimistic): 50 minutes to clear the queue. Critical alerts wait behind whatever was queued first.

**Missing Observability**
No LLM call logging, no pipeline stage timing, no queue depth metric, no dead letter queue, no health endpoints, no structured logs, no alerting if the system itself goes down. This is the meta-problem: you built an alerting system with no alerting on itself.

### SECTION D — Technical Gaps and Risks

**Security:** Prompt injection through alert content is a real attack surface. Alert descriptions and log content go directly into LLM prompts. A crafted syslog message could manipulate the AI's classification. Check whether .env was ever committed — if GMAIL_APP_PASSWORD was committed even once in git history, it is exposed.

**Deduplication Reliability:** No exact-match fast path (should hash alert signature before calling LLM). No time window (a BGP flap from January and one from May should not deduplicate). LLM similarity is non-deterministic — same pair of alerts might be classified differently on different runs.

**JSON Parsing Fragility:** The `raw.replace("```json","")` pattern appears in every agent node. LLMs produce trailing text, nested code blocks, and comments inside JSON. This will fail in production. Needs try/except with retry and fallback to JSON mode.

**_LazyLLM Shim Lock-In:** The shim works but opts out of the entire LangChain tool ecosystem — structured output, function calling, retry handlers, callbacks, tracing.

### SECTION E — Industry Comparison

| Capability | BigPanda / Moogsoft / PagerDuty | Your Project |
|-----------|--------------------------------|--------------|
| Ingestion scale | Millions of events/day | 1-2 tickets/min |
| Correlation | Topological (network graph-aware) | Last 10 tickets in LLM prompt |
| Deduplication | Hash + ML, sub-millisecond | LLM similarity, ~2 seconds |
| Multi-source connectors | 100+ out of the box | CSV, Meraki, Cisco DNA Center |
| Authentication / RBAC | Enterprise SSO, fine-grained roles | None |
| HA / DR | SaaS, 99.9% SLA | Single process, no redundancy |
| Bidirectional ITSM sync | Yes | One-way only |

**What Your Project Does That Commercial Tools Do Not:**
- LLM-generated remediation recommendations per alert
- Conversational AI assistant with live alert queue context
- Cost (~$20-50/month vs. $100k+/year for ServiceNow AIOps)
- Natural-language reasoning explainability

### SECTION F — Interview Assessment

**What Would Impress:**
- LangGraph interrupt/resume correctly implemented
- The _LazyLLM shim (most impressive technical decision in the project)
- The snapshot pattern
- Domain knowledge (BGP, OSPF, MPLS, LACP in mock data)
- Full-stack breadth under free-tier constraints

**What Would Concern:**
- No tests whatsoever
- Dual UI reads as scope creep
- Metrics are anecdotes (98% match rate from 4 manual tests)
- No discussion of unhappy path / failure handling

**Follow-Up Questions to Test Depth:**
1. What happens when Groq returns a 503 in the middle of the runbook node?
2. If Engineer A approves in React while the same ticket is at HITL in Streamlit, what happens?
3. Open the SQLite database. Show the deduplication table schema.
4. What is the false positive rate for runbook matching?
5. Explain the _LazyLLM shim — what exactly deadlocked and why?
6. Why 10 tickets for correlation? What happens during an alert storm of 200?
7. How would you add a second concurrent engineer without losing the HITL guarantee?

### SECTION G — Overall Verdict

This is a strong prototype with genuine engineering substance — not a tutorial wrapped in a demo. The LangGraph HITL interrupt pattern, the Python 3.14/Pydantic shim, the snapshot bug fix, the domain research, and the full-stack breadth all show real engineering thinking. This is meaningfully above the level of the average final-year capstone project.

The honest ceiling is that it is a single-user proof-of-concept. There are no tests, no LLM failure handling, fragile JSON parsing throughout, and scale characteristics that would make the system non-functional during the alert storms it was designed to handle. The metrics presented are best-case demonstrations, not evaluations.

If a candidate showed this in an interview: "This person can build real things, learns quickly, debugs non-obvious problems, and has good engineering instincts. Now I want to know if they understand the limits of what they built."

---

## Google Gemini

### SECTION A — Architecture Assessment

**The Good:**
- Decoupled Agent State: LangGraph is an excellent choice. Using a state machine with explicit interrupt points for HITL is exactly how enterprise automation should be designed.
- Modular Node Design: Breaking down routing, deduplication, and RAG into distinct nodes makes the pipeline testable and debuggable.
- Mocking Legacy Systems: Using GLPI via Docker to mock Remedy shows strong systems engineering maturity.

**What Needs Redesign:**

Synchronous Bottleneck: Your architecture implies the alert waits for 9 sequential graph nodes before presenting to the HITL. In a NOC, if an alert takes 10-15 seconds to traverse 9 LLM calls, an incident storm of 500 alerts will gridlock the API. You need an asynchronous message broker (e.g., Kafka, RabbitMQ, or Redis + Celery) handling the ingestion queue, processing the LangGraph pipeline in the background, and pushing states to the frontend via WebSockets/SSE.

Database Concurrency: Relying on SQLite with check_same_thread=False for LangGraph persistence in a FastAPI application is a critical flaw for production. Under high concurrent load, SQLite will throw database locking errors. This must be migrated to PostgreSQL.

Frontend Bloat: Maintaining Streamlit and React + FastAPI is technical debt. Drop Streamlit entirely for the production branch and commit to React.

### SECTION B — AI/LLM Design Assessment

**The Good:**
- Context Control: The snapshot pattern for session state to prevent cross-ticket data leakage is a highly practical solution.
- Prompt Engineering vs. GPU Cost: Decision to avoid a Vector DB and use prompt-based RAG for 13 runbooks was smart and pragmatic.

**What Needs Redesign:**

Overkill on the LLM: Using LLaMA 3.3 70B for every node is massively inefficient.
- Triage/Routing: A much smaller model (e.g., LLaMA 3 8B) or even a traditional classifier (XGBoost) can route alerts to 5 categories with 99% accuracy.
- Deduplication: Using LLM similarity is too slow and non-deterministic. Primary deduplication should be deterministic (regex on device_id + alert_code + time_window). LLM only if deterministic check is ambiguous.
- The Supervisor Node: Should only trigger if initial classification confidence falls below a threshold (e.g., <85%), not on every single alert.
- Runbook RAG at Scale: When Emircom hands you 500 runbooks, you will need a lightweight vector store (Qdrant or Milvus) and an embedding model.

### SECTION C — Production Readiness

**Real Blockers:**

1. Data Exfiltration / Security: Sending raw telecom syslog data to the Groq API is a massive compliance violation. NOC logs contain IP addresses, hostnames, and potentially plaintext credentials. A Saudi telecom company will strictly require data residency. You will need to switch to an on-premise hosted model (e.g., vLLM serving LLaMA locally).

2. API Rate Limiting: 12,000 TPM will be exhausted by a single flapping interface that generates 20 alerts in a minute. Must implement a bypass: if LLM fails or times out, alert must instantly drop into a "Manual Triage" queue.

3. Alert Storms: A real network outage will generate 5,000+ cascading alerts in 3 minutes. Your correlation engine (checking the last 10 tickets) will fail completely.

### SECTION D — Technical Gaps and Risks

- Correlation logic (last 10 tickets) is arbitrary. Time-windowed correlation (all alerts from same datacenter within a 5-minute window) is mathematically safer.
- False Positives in Deduplication: Never deduplicate across different severity levels or different source IPs — strict isolation rules needed.
- Missing Observability: No LLM tracing. Implement LangSmith or Phoenix for LLM call tracing.

### SECTION E — Industry Comparison

Compared to ServiceNow AIOps / Moogsoft: Commercial tools rely on CMDB topology — they know Router A connects to Switch B. Your AI relies purely on textual similarity in logs, which is less precise.

Where Your Tool Wins: Commercial ITSM tools have terrible UI/UX for runbooks. Your generative RAG approach (extracting exact steps from a JSON SOP) paired with the NOC AI Chatbot is far superior to standard PagerDuty or Remedy wikis.

### SECTION F — Interview Assessment

**What Would Impress:**
- The _LazyLLM Shim: Encountered a Python 3.14/Pydantic deadlock and engineered a custom shim bypassing the broken wrapper while maintaining the .invoke() contract. This shows senior-level debugging.
- End-to-End Execution: Backend, state machine, frontend, ITSM integration, Dockerized. Proves you are an engineer, not just an AI researcher.
- HITL Focus: Recognizing that AI should augment, not replace, NOC engineers shows strong domain awareness.

**What Would Concern:**
- Lack of defensive engineering around LLM latency and costs.
- Ignoring the security implications of cloud APIs in telecom.

### SECTION G — Overall Verdict

This is an exceptionally strong student prototype that punches well above the weight of an average final-year project. You have successfully navigated complex architectural patterns and applied them to a highly relevant enterprise problem. While not strictly production-ready due to concurrency limits, cloud API data risks, and LLM latency bottlenecks, the foundational engineering logic is sound. It proves you can build real-world AI systems, not just academic models.

---

## ChatGPT

### SECTION A — Architecture Assessment

**What is genuinely good:**

1. HITL-first design — Best engineering decision. For telecom NOCs, fully autonomous remediation is dangerous. The interrupt/resume design using LangGraph is appropriate and realistic. A lot of junior projects skip this entirely and assume "AI auto-fixes incidents," which immediately signals lack of operational maturity.

2. Separation of operational stages — The pipeline structure is mostly clean: Intake → Dedup → Classification correction → Specialist analysis → Runbook retrieval → Correlation → Ticketing/HITL. You did not build "one giant agent prompt that does everything."

3. Explicit state model — The AgentState design is solid. You tracked reasoning outputs, confidence, duplicate metadata, correlation metadata, escalation state, ITSM linkage.

4. Operational realism — SLA timers, escalation logic, duplicate suppression, shift handoff concepts, ticket routing, audit logs, ITSM integration, alert categories. This looks like someone actually observed NOC workflows.

**What should be redesigned:**

1. Too many LLM-dependent stages — A senior engineer would aggressively reduce LLM usage. Deduplication, classification, correlation, runbook retrieval, recommendations are all LLM-driven.

2. The Supervisor node is architecturally questionable — If the first classification is already AI-generated, the supervisor is mostly latency, token cost, and probabilistic disagreement. Commercial systems use ensemble confidence, deterministic enrichment, topology-aware correlation, and rule overrides — not "second LLM checks first LLM." A better architecture: Raw Alert → Deterministic enrichment → Single classifier → Confidence threshold → Human review if uncertain. The supervisor feels more like "multi-agent theater" than necessity.

3. Specialist agents are mostly prompt partitions — Same model, different prompts, different category context. This is workflow decomposition, not truly multi-agent intelligence.

4. Correlation architecture is too shallow — No temporal windows, no topology awareness, no dependency graphs, no CMDB relationships. One WAN failure triggers 400 downstream alerts; local-memory LLM approach will miss systemic structure.

5. SQLite is acceptable for prototype only — Production needs PostgreSQL, Redis, Kafka/RabbitMQ, event queues, durable async workers.

### SECTION B — AI/LLM Design Assessment

Was LangGraph the right tool? Yes for learning and demonstrating orchestration. But your pipeline is a linear DAG. A production engineer might build FastAPI + Celery/Kafka workers + finite state machine + rules engine + targeted inference services without LangGraph.

The RAG design: One of the better decisions given your constraints. At enterprise scale you need embeddings, chunking, metadata filtering, retrieval evaluation, citation grounding. But for 13 SOPs, your design is pragmatic.

Single model for all nodes — Acceptable for prototype, wrong for production:

| Task | Better Approach |
|------|----------------|
| Deduplication | Embeddings/similarity |
| Classification | Small finetuned classifier |
| Correlation | Graph/statistical methods |
| Runbook retrieval | Embeddings + reranker |
| Recommendation synthesis | Large LLM |

Deduplication via LLM similarity — Biggest engineering weakness. LLMs are not reliable duplicate detectors under production variability. Non-determinism, prompt sensitivity, inconsistent thresholds, latency, cost — all make this unreliable for real NOC operations.

### SECTION C — Production Readiness

Biggest blockers:

1. No real telemetry integration maturity — No streaming ingestion, no event backpressure, no queueing, no retries, no idempotency guarantees, no event ordering.

2. LLM dependency fragility — Entire system depends on one remote API, one model, one provider. If Groq rate limits, times out, or changes model behavior, your NOC workflow partially collapses. Need: fallback models, cached decisions, degraded modes, circuit breakers, retries, async buffering.

3. Latency explosion at scale — At 3-5 seconds per node × 6 LLM nodes × hundreds of alerts/hour: operationally unacceptable triage latency during incidents.

4. No true observability — No distributed tracing, no token usage metrics, no per-node latency, no hallucination tracking, no prompt versioning, no retry dashboards.

### SECTION D — Technical Gaps and Risks

- Confidence scores are likely meaningless — LLM confidence is not calibrated probability. Unless you implemented calibration curves and empirical evaluation, those percentages are mostly cosmetic.
- Prompt injection protection claims are overstated — Scope hardening is not robust security. If logs contain malicious payloads, the model can still behave unpredictably.
- Correlation logic is operationally weak — "Shared root cause" via LLM text reasoning is unreliable without topology and dependency graphs.
- No authentication is a deployment blocker — Creates tickets, sends emails, handles operational alerts. Without auth, audit identity, role permissions, and action attribution, it cannot enter production environments.
- No evaluation framework — Precision/recall, false duplicate rate, routing accuracy, hallucination rate, escalation correctness, latency distributions — none measured.

### SECTION E — Industry Comparison

Compared to PagerDuty / BigPanda / Moogsoft / ServiceNow — obviously far less mature operationally. Expected.

**What your project does surprisingly well:**
1. Workflow coherence — End-to-end operational flow, not disconnected feature collection
2. HITL integration — Operators as first-class participants
3. ITSM integration realism — Using GLPI instead of mocking was the right move
4. Telecom-domain specificity — Domain-aware alerts, routing, and runbooks give credibility

**What commercial systems do much better:**
1. Event ingestion scale (millions of events/day vs your 1-2 tickets/min)
2. Correlation sophistication (graph analytics, topology engines, dependency models)
3. Reliability engineering (uptime, failover, resilience, deterministic behavior)
4. Explainability and governance (auditability, reproducibility, policy controls, compliance logging)

### SECTION F — Interview Assessment

**What Would Impress:**
1. Full-stack ownership (backend + orchestration + frontend + integrations + persistence + ITSM)
2. Operational thinking (NOC workflows, SLA pressure, alert fatigue, escalation paths)
3. Engineering pragmatism (adapted to no GPU, no production data, no budget)
4. Integration complexity (webhooks, SSE, ITSM APIs, Dockerized enterprise software, async workflows)

**What Would Concern:**
1. Overuse of "agent" terminology — need to distinguish truly agentic vs deterministic workflow parts
2. This statement is too strong: "The system is production-ready in architecture" — Prototype architecture yes, production-ready no
3. Lack of evaluation rigor — needs metrics, benchmarks, error analysis, failure characterization

**Interview Questions:**
- Why use LangGraph instead of queues/workers?
- Which nodes truly require LLM reasoning?
- How would you evaluate duplicate detection quality?
- What happens during API outage?
- How would you scale to 10k alerts/day?
- Which design decisions would you reverse today?

### SECTION G — Overall Verdict

This is a strong student systems project with genuine engineering depth, not a toy LLM demo. The strongest aspects are the operational realism, HITL workflow design, end-to-end integration work, and pragmatic adaptation to severe constraints. The weakest aspects are overreliance on a single large LLM for nearly every decision, shallow correlation/deduplication methods, lack of rigorous evaluation, and overstated production-readiness claims. A senior engineer would not view this as deployable to a real telecom NOC yet, but they would absolutely view it as evidence that you can think beyond notebooks and understand how AI systems interact with operational infrastructure. For a final-semester AI student, this is materially above average and strong enough to attract serious interest for junior AI/platform engineering roles — especially if you can discuss the limitations as clearly as the strengths.
