# RetailIQ---SeroAI

Ask your retail sales data questions in plain English — no SQL required.

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
