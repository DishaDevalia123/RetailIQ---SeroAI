# RetailIQ

Ask your retail sales data questions in plain English and get back calculated answers, auto-generated charts, plain-language explanations, and comparisons across follow-up questions — with the system proactively suggesting what to dig into next.

**Built with:**
- Prompt Engineering — structured prompts driving reliable NL-to-SQL generation
- Few-Shot Learning — a curated example pool that grows with every new edge case
- Semantic Caching — intent/entity fingerprinting to skip redundant LLM calls
- Deterministic Guardrails — safe handling of LLM-unreliable ops like date math
- Self-Healing SQL Repair Loops — auto-recovers from failed queries
- Best-of-3 Execution Voting — runs 3 SQL candidates, returns the majority-agreeing result
- Conversational Memory — context-aware, follow-up-friendly answers
- OpenAI API (GPT) — powers language understanding and SQL generation
- FastAPI + MySQL — backend and data layer

**Tech Stack**

Backend -	Python, FastAPI
LLM -	OpenAI API (GPT)
Database -	MySQL
Data Handling -	Pandas
Visualization -	Matplotlib, Seaborn

## Example

**Query:** "How did revenue change from 2024 to 2025?"

| Year | Revenue |
|---|---|
| 2024 | $482,300 |
| 2025 | $410,150 |

*Revenue declined by roughly 15% from 2024 to 2025.*

*Want to dig deeper into what factors might have contributed to this — a specific store, a category, or a seasonal dip?*

*Follow-up: "What drove the drop in Q3?"*

RetailIQ recalls the prior comparison, narrows the analysis to Q3, and surfaces the contributing store and category breakdowns alongside a chart — without needing the year range repeated.
