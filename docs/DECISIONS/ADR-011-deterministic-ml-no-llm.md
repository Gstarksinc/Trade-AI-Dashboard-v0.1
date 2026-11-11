# ADR 011: Deterministic Quantitative ML without LLMs/Agent Frameworks in Signal Path

## Status
Accepted

## Context
There is industry temptation to inject Large Language Models (LLMs), agent frameworks (e.g. LangChain, CrewAI), or unstructured NLP analysis directly into low-latency live trading signal execution paths. LLMs are non-deterministic, suffer from hallucinations, introduce high inference latency (>500ms), and cannot provide rigorous mathematical guarantees required for statistical arbitrage.

## Decision
Keep the live trading and risk decision path **100% deterministic and quantitative**:
1. Signal generation relies exclusively on calibrated gradient boosting (LightGBM) and Random Forest meta-classifiers with deterministic seeds.
2. Zero LLM, MCP, or generative agent frameworks exist in the live signal, risk, or paper execution pathways.
3. Machine learning code is audited for bitwise artifact determinism (SHA256 matching).

## Consequences
- **Positive**: Sub-millisecond inference; 100% reproducible backtesting; mathematical verification via CPCV and DSR.
- **Negative**: Excludes qualitative social media sentiment analysis (which has questionable quantitative signal value anyway).

