# COOP Project Evaluation Results
**Evaluated by:** Claude (separate session)  
**Date:** May 2026  
**Based on:** UPM COOP Rubric (ST02, ST03, ST04, ST05) + PROJECT_OVERVIEW.md

---

## SECTION 1 — Presentation Readiness Assessment

### Content Criteria

**C1 — Accurate information presented with clarity**
Rating: **Good**
The documentation is technically accurate, internally consistent, and well-written. The architecture diagrams, state machine descriptions, and measured outcomes are coherent. However, two placeholders appear that would cost marks if they appear on slides: [Start Date] – [End Date] and [Course Name — AI Agents / Intelligent Systems]. A committee member reading your slides will see those immediately.

Fix: Fill in your actual internship dates and the real course name before any submission or slide export.

---

**C2 — Explained departments at the training organization**
Rating: **Fair**
Section II describes the NOC and its workflow well. What is missing is a description of Emircom's organizational structure — what other departments exist (IT, Sales, Infrastructure, Security), how the NOC sits within the org chart, how many engineers are in the NOC, and who oversees it. The rubric says "departments at the training organization," which implies breadth beyond your immediate team.

Fix: Add one slide (or half a page in the report) with an org chart or department list showing NOC's place in the company. Even a simplified version (3–4 departments) satisfies this criterion.

---

**C3 — Job titles, job descriptions, and tasks related to the trainee's major**
Rating: **Poor — this is your biggest presentation gap**
The documentation describes the project thoroughly but almost never describes you as a trainee. The rubric asks: What was your official job title? What were your assigned tasks each week? Who was your supervisor? What did a typical workday look like? None of this is present.

A committee member will ask: "What did you actually do at Emircom?" If your answer is only "I built this project," that is insufficient. The rubric wants to see that you functioned as an employee with responsibilities, not just an independent developer.

Fix: Add a "My Role" section: your official title (e.g., AI Intern / Junior NOC Analyst), the name and title of your supervisor, a brief week-by-week or phase-by-phase description of your assigned tasks (requirements gathering, design, implementation, testing, demonstration), and any meetings or operational activities you participated in.

---

**C4 — Linked training to at least two courses in the AI program**
Rating: **Excellent**
Section V is strong. You identified 6 courses with specific, non-generic connections. The NLP and Software Engineering links are especially credible. The Machine Learning link is slightly weaker — confidence scoring and similarity detection using an LLM is not really classical ML — but it is defensible.

Fix: Be prepared to explain what you specifically learned in the NLP course that you applied here. If your university calls the course "Deep Learning" or "Foundation Models," use the real name.

---

**C5 — Mentioned and demonstrated mastery of at least one new skill**
Rating: **Excellent**
Section VI lists 8 skills with specific technical depth. The LangGraph explanation is particularly strong — you can demonstrate a real engineering decision (the _LazyLLM shim) that shows genuine mastery, not just "I used a library."

Fix: In the presentation, pick one skill as your showcase skill and demonstrate it live or with a short recorded demo clip. LangGraph is your strongest choice.

---

### Organization Criteria

**O1 — Appropriate introduction**
Rating: **Average**
The documentation has a clear thesis statement and organization introduction. What is missing for the presentation is a proper self-introduction (name, university, program, year) and an attention-getter (a dramatic statistic about NOC fatigue, alert volumes, or MTTR). The documentation jumps straight into the problem.

Fix: Open with one striking statistic. Example: "NOC engineers at large telecom companies process up to 2,000 alerts per 8-hour shift. Studies show 60–70% of alerts are duplicates or false positives." Then introduce yourself and the company.

---

**O2 — Smooth transitions and logical flow**
Rating: **Good**
The documentation flows logically: problem → solution → architecture → results → limitations → conclusion. This is solid. The transition from Section VII (architecture) to Section VIII (pipeline) could be tighter in a presentation — you'd need a bridging sentence explaining why you're zooming in.

Fix: For each slide transition, prepare a one-sentence spoken bridge: "Now that you see the overall system, let me walk you through the AI brain specifically."

---

**O3 — Clear documentation with acceptable-quality visuals**
Rating: **Fair — this is your second biggest gap**
The documentation has well-structured ASCII art diagrams but zero actual screenshots, photos, or real visuals. The rubric specifically says "acceptable-quality visuals." An evaluation committee will expect to see the system running: screenshots of the HITL panel, the React dashboard, the GLPI ticket, the email notification. Without these, the project looks theoretical.

Fix: Add at minimum: (1) screenshot of the Streamlit Operations tab with a ticket loaded, (2) screenshot of the React dashboard, (3) screenshot of a GLPI ticket created by the system, (4) screenshot of the escalation email received. Embed these in both the slides and the report.

---

**O4 — Closing with summary and acknowledgement**
Rating: **Fair**
Section XV is a reasonable conclusion. However, there is no acknowledgement — no thanks to Emircom, your supervisor, the university, or anyone who helped you. This is a rubric requirement.

Fix: Add a final "Thank You" or "Acknowledgements" section/slide that thanks Emircom for the opportunity, your academic supervisor (by name if possible), and anyone else relevant.

---

### Delivery and Response to Questions
These cannot be rated from documentation — they depend entirely on your performance on the day. However, two observations:
- Your biggest delivery risk is being asked "What did you personally build versus what did Claude/AI help you with?" Be prepared with an honest, confident answer. You should be able to explain every design decision in the codebase.
- Confidence risk: The project is technically strong. If you understate it or seem uncertain about your own work, the committee will doubt the authorship.

---

## SECTION 2 — Report Quality Assessment

**Cover Page (3%)**
Estimated: 2/3%
Present: trainee name, organization, university, program, report date. Missing: internship start/end dates (placeholders), supervisor name, course name and code, department. These are standard cover page fields. Losing 1% here is unnecessary.

---

**Abstract (3%)**
Estimated: 0/3%
No abstract exists. Section I is titled "Executive Summary" — this is not the same thing. A formal abstract is 150–200 words in a single paragraph, structured as: problem + objective + methods + results + conclusion. It stands alone and is read first.

This is a free 3% that is currently zero. Write a proper 150-word abstract before submission.

---

**Table of Contents (3%)**
Estimated: 0/3%
Not present. The rubric requires it. For a document with 16 numbered sections, a ToC is straightforward to generate.

Again, free marks — currently zero.

---

**Introduction (6%)**
Estimated: 4.5/6%
Present: description of training site (Section II), thesis statement (Section III), objectives (Section IV), related courses (Section V), new skills (Section VI). This is strong.

Missing: the rubric asks for "background information" — a paragraph explaining what LLMs are, what a state machine is, what ITSM means, and why HITL matters. The report currently assumes the reader knows these terms.

Also missing: explicit "report objectives" (what will this report demonstrate, what sections exist, how are they organized) — distinct from project objectives.

---

**Body (12%)**
Estimated: 8/12%
The technical content is excellent. What costs marks:
- No photos from the training site. The rubric says "pictures from the training site with captions." This likely means photos of the NOC floor, equipment, team, screens.
- No numbered figures. ASCII diagrams are not numbered (Figure 1, Figure 2, etc.) and not referenced in text.
- No numbered tables. Tables in Sections X, XI, XII, XIII are not formally numbered.
- No screenshots of the running system.

---

**Conclusion (3%)**
Estimated: 2.5/3%
Section XV is good. Slightly missing: the rubric asks for "challenges encountered" explicitly in the conclusion. Challenges are in Section XII but not summarized in the conclusion. A two-sentence bridge would fix this.

---

**References (penalty)**
Estimated: −3 to −5% penalty
Critical. The report cites no external sources. LangGraph, Groq, FastAPI, GLPI, React, Docker — all have official documentation that should be cited. Missing references is one of the most common penalties applied to COOP reports.

Fix: Add a References section with at minimum: LangGraph documentation, Groq API documentation, GLPI documentation, FastAPI documentation, and 2–3 academic or industry sources about AI in network operations or HITL systems.

---

**Appendices (penalty)**
Estimated: −1 to −2% penalty
UPM typically requires official forms — internship registration, company acceptance letter, weekly activity log, supervisor evaluation form. Verify with your university.

---

## SECTION 3 — Technical Quality Assessment

**Complexity and Ambition**
Genuinely impressive for a COOP project. Most COOP AI projects are: fine-tune a model on a dataset, or build a simple classifier, or deploy a pre-existing chatbot. This is a multi-agent orchestration system with a state machine, 9 pipeline nodes, two complete frontend implementations, Docker-based ITSM integration, two external network APIs, streaming SSE, and a scope-hardened adversarial chatbot. The scope is closer to a junior full-stack AI engineer's 6-month delivery. That is a strength — but be prepared to explain every part of it.

**Appropriateness of AI Techniques**
LangGraph: appropriate and modern. LLaMA 3.3 70B via Groq: appropriate for the inference workload. HITL architecture: exactly right for a critical operations context. RAG without vector DB: pragmatic and clever given the constraints. The _LazyLLM shim shows genuine systems thinking.

One slight weakness: calling the deduplication engine "Machine Learning" is a stretch. SQLite + LLM similarity is NLP, not ML in the classical sense. A committee member who teaches ML may challenge this.

**System Design Quality**
Clean separation of concerns. The snapshot pattern for email data shows architecture-level bug fixing. The single-thread design respecting Streamlit's constraints shows runtime understanding.

Weakness: no authentication/RBAC. "Anyone with the URL can access the dashboard" will get a raised eyebrow from a telecom company's committee. Be ready with "prototype scope, production would require X."

**Honesty About Limitations**
Section XIII is excellent. Acknowledging mock data, fake runbooks, Groq rate limits, no authentication, and LLM quality dependency on log detail is exactly what a mature engineer does.

**Production Readiness**
Architecture is production-grade in design. Gaps: mock data only, no auth, free-tier LLM rate limits, no monitoring/observability, no CI/CD, no unit tests mentioned. Expected for a COOP prototype.

---

## SECTION 4 — Likely Examination Questions

**Q1: "Walk me through what happens when a Critical network alert comes in."**
Strong answer: Walk the pipeline node by node. "The alert enters triage_node which logs it and initializes state. Then deduplication_node checks SQLite history plus an LLM similarity check — if it's a repeat, the graph pauses and waits for engineer approval to drop it. If it's unique, supervisor_node independently re-classifies the category using the LLM — this catches mislabeled alerts. It then routes to network_ops_node which produces a full analysis: root cause, severity, confidence score, and step-by-step recommendation. runbook_node selects the best-matching SOP from 13 runbooks. correlation_node checks the last 10 tickets for shared root cause. Then the graph pauses at remedy_node — nothing happens until the engineer clicks Approve. Only then does GLPI create the ticket and send the email." Practice saying this under 90 seconds.

**Q2: "What is a LangGraph and why did you use it instead of just calling the LLM directly?"**
Strong answer: "LangGraph models the triage process as a directed graph where each node is an agent with a specific role. The key advantage is interrupt/resume — I can pause the graph at the HITL point, wait for the engineer's decision, and resume from exactly that state. With a sequential function chain, you cannot pause mid-execution and wait for human input without losing all your state. LangGraph's SqliteSaver checkpointer persists every intermediate state to disk, so even if the app restarts, I can resume a ticket that was mid-review."

**Q3: "What is HITL and why is it important here?"**
Strong answer: "HITL — Human-in-the-Loop — means the AI never takes an action autonomously. Every ticket requires an engineer to explicitly approve before a GLPI ticket is created or an email sent. In a 24/7 NOC, a wrong action — like creating a ticket for the wrong team, or sending an email about a false positive — causes real operational disruption. The AI's role is to prepare a complete briefing in under 10 seconds; the engineer's role is to verify and approve. This matches how Emircom's NOC actually operates."

**Q4: "Your RAG system has no vector database. How does it work, and what are the tradeoffs?"**
Strong answer: "Instead of embedding documents and doing cosine similarity search, I send the LLM a structured index of all 13 runbooks — just their titles, categories, and key terms — and ask it to identify which runbook best matches the current alert. The LLM then retrieves that runbook. The tradeoff is that this only scales to a small runbook library — at 500+ runbooks, this approach would exceed the context window. For a pilot deployment with 13 SOPs and no GPU budget, it was the right pragmatic choice. A production system with Emircom's full runbook library would need embeddings."

**Q5: "How would you measure whether this system actually improves NOC performance?"**
Strong answer: "The system logs Response_Time_Secs per ticket in the audit log. Before the system: no baseline measurement exists. If deployed, I would track Mean Time to Triage (MTTT) — the time from alert arrival to GLPI ticket creation — and compare it to the manual baseline. Secondary metrics: SLA breach rate, duplicate alert rate, and supervisor override rate (which measures how often the AI misclassifies). The escalation email also provides a natural measurement point for how long HITL reviews take."

**Q6: "Why did you use LLaMA 3.3 70B and not GPT-4 or Claude?"**
Strong answer: "Cost and latency. Groq's free tier provides LLaMA 3.3 70B inference at extremely low latency — typically under 2 seconds per node — which is critical for a time-sensitive NOC environment. GPT-4 and Claude API access have per-token costs that would make a free-tier prototype infeasible. For a production deployment with budget, either could be substituted since the system uses a standardized .invoke() interface — switching the LLM requires changing one line."

**Q7: "What happens if the LLM gives a wrong answer — misclassifies a Critical ticket as Low?"**
Strong answer: "Three safeguards exist. First, the Supervisor node independently re-classifies every ticket — it acts as a second opinion on the category. Second, the confidence score is shown to the engineer in the HITL panel — if the LLM is uncertain, the score is low and the engineer knows to scrutinize the analysis more carefully. Third, and most importantly, HITL means the engineer always has the final say. The engineer sees the raw logs, the AI analysis, and the runbook recommendation — if the AI misclassified, the engineer will catch it before any ticket is created. The AI is a first-pass filter, not a decision-maker."

**Q8: "This project uses a lot of open-source tools. What is your original contribution?"**
Strong answer: "The original contributions are: (1) the multi-agent pipeline architecture — designing which agents exist, what they do, and how they are connected is a design decision, not a configuration; (2) the _LazyLLM shim that solved the Python 3.14 / Pydantic V1 deadlock — this required debugging a compatibility issue that had no documented solution; (3) the snapshot pattern for the email panel — I identified a race condition bug and designed a specific pattern to eliminate it; (4) the scope-hardened chatbot system prompt, tested against adversarial inputs; (5) 80 mock alerts and 13 realistic JSON runbooks written to telecom domain specifications. I used libraries the same way a professional engineer would — choosing the right tool rather than reinventing it."

**Q9: "What are the ethical risks of deploying AI in a 24/7 network operations environment?"**
Strong answer: "The main risks are: over-reliance, where engineers stop critically reviewing AI suggestions and approve reflexively; adversarial manipulation, where an attacker sends crafted alerts to confuse the AI's classification; and automation bias, where the AI's confident but wrong analysis overrides an engineer's correct intuition. The HITL design mitigates over-reliance by forcing engineers to see the raw logs, not just the AI summary. For adversarial manipulation, the system only accepts alerts from internal sources. For automation bias, the confidence score is visible and the engineer can always override."

**Q10: "If Emircom asked you to deploy this tomorrow, what would you need to do first?"**
Strong answer: "Four things: first, add authentication — role-based access for Tier-1/Tier-2 engineers, Shift Lead, and Manager. Second, connect to the real alert feed — either the Cisco DNA Center production system or Emircom's SolarWinds/Zabbix instance. Third, upgrade the LLM tier — the free Groq tier hits rate limits under real alert volume; production needs either a paid API or a locally-hosted model. Fourth, replace the mock runbooks with real Emircom SOPs — the retrieval engine is already built, the JSON files just need to be populated by the operations team."

---

## SECTION 5 — Priority Improvements (Ranked by Grade Impact)

1. **Add a proper Abstract and Table of Contents** (Impact: +6% on Report)
   Free marks. Currently scoring 0/3% on each. A 150-word abstract and a one-page ToC take 30 minutes to write and recover 6 percentage points on the report component.

2. **Add screenshots and real system visuals** (Impact: high on both Presentation and Report)
   Without screenshots, the system appears theoretical. Need: HITL panel with a live ticket, React dashboard, a GLPI ticket, and the escalation email. Satisfies O3 in presentation and the body figure requirement in the report.

3. **Add a References section** (Impact: prevents −3 to −5% penalty on Report)
   Cite LangGraph, Groq, FastAPI, GLPI, 2–3 academic sources on AI in network operations or HITL systems.

4. **Add your role, job title, and internship tasks** (Impact: fixes C3 in Presentation — currently rated Poor)
   Write a 5-bullet "My Role" section: title, supervisor, what you did each phase. Without this, the committee cannot verify you functioned as an actual employee.

5. **Fill in all placeholders and add acknowledgements section**
   [Start Date], [End Date], [Course Name] visible in documentation. Acknowledgements cost nothing to write and satisfy a rubric requirement currently scoring zero.

---

## SECTION 6 — Overall Estimated Grade

### Presentation Component (40% of final grade)

| Sub-Component | Estimate | Max |
|---------------|----------|-----|
| Content (5 criteria × 5) | 16/25 | 25 |
| Organization (4 criteria × 5) | 14/20 | 20 |
| Professionalism (2 criteria × 5) | 8/10 | 10 — depends on day |
| Delivery (4 criteria × 5) | 14/20 | 20 — depends on delivery |
| Response to Questions | 14/20 | 20 — depends on preparation |
| **Subtotal** | **~66/95 ≈ 69%** | 95 |

With fixes, this could reach 78–82%.

### Written Report Component (30% of final grade)

| Section | Estimate | Max |
|---------|----------|-----|
| Cover Page | 2/3 | 3 |
| Abstract | 0/3 | 3 |
| Table of Contents | 0/3 | 3 |
| Introduction | 4.5/6 | 6 |
| Body | 7.5/12 | 12 |
| Conclusion | 2.5/3 | 3 |
| References penalty | −3 | 0 |
| **Subtotal** | **~13.5/30 ≈ 45%** | 30 |

With all fixes applied, this could reach 24–26/30 (80–87%).

### Supervisor Evaluation (30% of final grade)
Cannot be scored from documentation. Depends on Emircom's assessment of work ethic, punctuality, and technical contribution.

### Overall

| State | Estimated Score |
|-------|----------------|
| Before fixes | 58–62% overall |
| After all Section 5 fixes | 73–78% overall |

**Honest summary:** The technical project is excellent — top 10% of COOP AI projects in scope and execution. The documentation and academic packaging is currently below the technical quality, costing marks on the report component that are entirely recoverable. The presentation gap on trainee role description is the most substantive content issue. If all five priority improvements are addressed, this project can score in the B+ to A- range. As submitted today, the report component alone would bring the aggregate score to a C+ or B-.

**The single most important action: write the abstract and ToC. Those are 6 free marks sitting on the table.**
