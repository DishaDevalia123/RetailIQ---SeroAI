# RetailIQ

An AI analytics system that works like an on-demand data analyst for company operations data. Leaders ask questions in plain English and get calculated answers, auto-generated charts, plain-language explanations of *why* a result happened, comparisons across follow-up questions, and suggestions for what to explore next.

Built as a prototype at a manufacturer (House of Sero) on ERP data covering sales, production, retail and dispatch, and tested with company leadership. It helped leaders get answers about **60% faster** instead of waiting for manual reports.

> This public repository is a simplified version. All company data has been removed; sample schema and data only.

## Reliability: how it avoids wrong answers

- **Best-of-3 execution voting:** generates 3 candidate queries, executes all of them, and returns the result they agree on
- **Self-healing repair loop:** if a query fails, the error is fed back to the model to repair it automatically
- **Deterministic guardrails:** operations LLMs often get wrong, such as date arithmetic, are handled in code, not by the model
- **Few-shot learning from failures:** whenever a new type of question failed, an example of it was added to the prompt pool, so similar questions succeed next time
- **Read-only database access:** the system can query data but never change it
- **Logging and monitoring:** errors, response times and repair rates are logged; core logic is unit-tested

## Speed and cost

- **Semantic caching:** each question is reduced to an intent/entity fingerprint (for example `{intent: aggregate, metric: revenue, period: 2025}`), so repeated questions are answered from cache without another LLM call

## How it works

1. A question comes in → intent and entities are extracted
2. Cache check → a repeat question is answered instantly
3. The LLM generates 3 candidate SQL queries using few-shot examples
4. All 3 are executed; the agreeing result wins; failures go through the repair loop
5. Guardrails validate sensitive operations
6. The answer is returned as a table, chart and written explanation, with suggested next questions
7. Conversational memory keeps context for follow-up questions

## Example (sample data)

**Query:** "How did revenue change from 2024 to 2025?"

| Year | Revenue |
|---|---|
| 2024 | $482,300 |
| 2025 | $410,150 |

*Revenue declined by roughly 15% from 2024 to 2025.*

*Want to dig deeper into what contributed to this: a specific store, a category, or a seasonal dip?*

**Follow-up:** "What drove the drop in Q3?"

RetailIQ recalls the prior comparison, narrows the analysis to Q3, and surfaces the contributing store and category breakdowns alongside a chart, without needing the year range repeated.

## Tech stack

| Layer | Tools |
|---|---|
| Backend | Python, FastAPI |
| LLM | OpenAI API (GPT) |
| Database | MySQL (read-only user) |
| Data handling | pandas |
| Visualization | Matplotlib, Seaborn |

## What's next

Ongoing research in a separate project, [Self-Learning AI Agent](https://github.com/DishaDevalia123/Self-Learning-AI-Agent):

- **Confidence scoring and calibration,** so the system knows when it is likely to be wrong
- **Clarifying questions** when confidence is low, instead of guessing
- **A retrieval-based (RAG) memory of past failures,** so the system learns from its own mistakes automatically
