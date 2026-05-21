# Technical Evaluation Prompt

Copy everything below the dashed line and paste it **before** the PROJECT_OVERVIEW.md content.

---

---
---

## PROMPT (copy from here)

You are a senior AI/ML engineer and systems architect with experience in enterprise operations automation, LLM application development, and production NOC/ITSM systems. I am going to share documentation for an AI project I built during a university internship at a telecom company.

Please give me an honest, critical technical evaluation of the project — not an academic one. Evaluate the engineering decisions, architecture, and AI design choices as you would in a professional code/design review.

---

### CONTEXT

- I am a final-semester AI student
- The project is a prototype built during a COOP internship at Emircom, a Saudi telecom company
- I had no access to real production data, no GPU, and no paid API budget
- The project uses: LangGraph (agent orchestration), LLaMA 3.3 70B via Groq (free tier), FastAPI, React, Streamlit, GLPI (open-source ITSM in Docker), SQLite, Gmail SMTP
- The GitHub repository is: github.com/YznCodeX/Emircom_NOC_Agent

---

### WHAT I WANT YOU TO EVALUATE

**1. Architecture Quality**
- Is the multi-agent pipeline design (Triage → Dedup → Supervisor → Specialist → Runbook → Correlation → HITL) well-structured?
- Are responsibilities clearly separated between agents?
- What would a senior engineer change about the architecture?

**2. AI/LLM Design Choices**
- Is LangGraph the right tool for this use case, or would a simpler approach have been better?
- Is the RAG approach (LLM-based retrieval over 13 runbooks, no vector DB) a sound engineering decision given the constraints, or a workaround that will break in production?
- Is using a single LLM (LLaMA 3.3 70B) for all 9 pipeline nodes appropriate, or should different nodes use different models?
- Is the Supervisor node (independent LLM re-classification of every alert) a genuine value-add or unnecessary cost/latency?
- Is the HITL implementation at the right level — too strict, too loose, or appropriate for a telecom NOC?

**3. Production Readiness**
- What are the real blockers to deploying this in a production NOC environment?
- How would this system behave under real alert volumes (hundreds per hour)?
- What monitoring and observability is missing?
- What happens when the LLM API is down or rate-limited in production?

**4. Technical Gaps and Risks**
- What are the weakest parts of the design?
- Are there any design decisions that would cause real problems at scale?
- What security risks exist that are not already acknowledged?
- Is the deduplication approach (SQLite + LLM similarity) reliable enough for production?

**5. Comparison to Industry**
- How does this compare to existing NOC automation tools (e.g., PagerDuty, BigPanda, Moogsoft, ServiceNow AIOps)?
- What does this project do that commercial tools do not, or do worse?
- What do commercial tools do that this project is missing?

**6. What a Hiring Manager Would Think**
- If a candidate showed this project in a job interview for a junior AI engineer role, what would impress you?
- What would concern you?
- What follow-up questions would you ask to test whether they really built it and understand it deeply?

---

### FORMAT

Please structure your response as:

**SECTION A — Architecture Assessment** (What is good, what should be redesigned)

**SECTION B — AI/LLM Design Assessment** (Are the right tools used in the right way)

**SECTION C — Production Readiness** (Real blockers, failure modes, scale concerns)

**SECTION D — Technical Gaps and Risks** (Honest weaknesses beyond what the documentation already admits)

**SECTION E — Industry Comparison** (How this stacks up against real NOC automation tools)

**SECTION F — Interview Assessment** (What a hiring manager would think)

**SECTION G — Overall Verdict** (One paragraph: is this a strong student project, a weak one, or something else?)

Be direct. Do not soften criticism. I need to understand the real strengths and weaknesses of what I built.

---

Now here is the full project documentation:

[PASTE PROJECT_OVERVIEW.md CONTENT HERE]
