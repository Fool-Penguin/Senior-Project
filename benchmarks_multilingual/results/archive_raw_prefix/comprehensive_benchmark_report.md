# Comprehensive Multi-Benchmark Evaluation & Model Family Scaling Report

> **Evaluated Stack:** Python, JavaScript, TypeScript (CodeDEE Target Runtimes)  
> **Evaluation Mode:** Raw Prefix Continuation ($T = 0.0$, Greedy Decoding, 100% Deterministic)  
> **Hardware:** NVIDIA GeForce RTX 5080 Laptop GPU (16 GB VRAM)  
> **Evaluated Benchmarks:**  
> 1. **OpenAI HumanEval (Official):** 164 Python standard algorithmic tasks  
> 2. **MultiPL-E Multilingual:** JavaScript (161 tasks), TypeScript (159 tasks)  
> 3. **BigCodeBench:** 50 tasks across 139 Python engineering libraries  
> 4. **SantaCoder FIM:** 50 bidirectional infilling tasks across Python & JavaScript  
> 5. **CRUXEval:** 50 code execution reasoning tasks  
> **Date:** October 2026  

---

## 1. Ranked Multi-Benchmark Leaderboard (Phase 1 Screening)

| Rank | Model Name | Overall Score | OpenAI HumanEval | MultiPL-E (JS) | MultiPL-E (TS) | BigCodeBench | FIM (Infill) | CRUXEval | Speed (t/s) | Latency | VRAM / RAM |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **`qwen2.5-coder:7b`** | **70.7%** | **77.4%** | 75.8% | 78.6% | 50.0% | 62.0% | 36.0% | 125.6 t/s | 0.69s | 5.7G VRAM / 10.2G RAM |
| **#2** | **`qwen2.5-coder:1.5b`** | **52.5%** | **55.5%** | 54.0% | 42.1% | 70.0% | 92.0% | 14.0% | 341.4 t/s | 0.28s | 7.4G VRAM / 14.8G RAM |
| **#3** | **`llama3.1:8b`** | **47.6%** | **57.3%** | 54.0% | 56.6% | 34.0% | 2.0% | 26.0% | 115.9 t/s | 1.35s | 6.1G VRAM / 13.1G RAM |
| **#4** | **`deepseek-coder:6.7b`** | **39.9%** | **50.0%** | 53.4% | 37.1% | 44.0% | 2.0% | 6.0% | 134.8 t/s | 1.14s | 6.0G VRAM / 13.1G RAM |
| **#5** | **`codellama:7b`** | **36.8%** | **32.9%** | 35.4% | 32.7% | 76.0% | 52.0% | 12.0% | 136.1 t/s | 0.72s | 6.1G VRAM / 12.5G RAM |
| **#6** | **`gpt-oss:20b`** | **13.2%** | **32.9%** | 2.5% | 0.0% | 36.0% | 0.0% | 16.0% | 145.7 t/s | 1.40s | 13.4G VRAM / 10.1G RAM |

---

## 2. Key Empirical Findings & Academic Insights

1. **OpenAI HumanEval vs. MultiPL-E:**  
   Official HumanEval establishes the baseline Python algorithmic capability. In polyglot runtimes, performance varies significantly when generating typed JavaScript and TypeScript, proving the necessity of multilingual evaluation for CodeDEE.
2. **Library Awareness (BigCodeBench):**  
   Evaluates interactions with modern third-party packages (`pandas`, `requests`, `cryptography`), distinguishing between raw algorithmic syntax and practical software engineering.
3. **Bidirectional Infilling (FIM):**  
   Evaluates how effectively models insert code between a prefix and suffix, which is directly applicable to automated vulnerability patching and inline code completion.
4. **Execution Reasoning (CRUXEval):**  
   Verifies whether the model truly simulates execution state rather than merely guessing based on syntactic tokens.

---
## 3. Phase 2: Winning Architecture Family Scaling Ladder (Pareto Trade-Off)

| Model Scale | Overall Score | OpenAI HumanEval | MultiPL-E (JS / TS) | Speed (Tokens/s) | Avg Latency | Memory Footprint (VRAM / RAM) | Recommendation Tier |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`qwen2.5-coder:1.5b`** | **52.5%** | **55.5%** | 54.0% / 42.1% | 341.4 t/s | 0.28s | 7.4G VRAM / 14.8G RAM | Recommended |
| **`qwen2.5-coder:7b`** | **70.7%** | **77.4%** | 75.8% / 78.6% | 125.6 t/s | 0.69s | 5.7G VRAM / 10.2G RAM | Recommended |
| **`qwen2.5-coder:14b`** | **74.9%** | **84.8%** | 75.8% / 75.5% | 64.7 t/s | 1.42s | 9.9G VRAM / 13.5G RAM | Recommended |
| **`qwen2.5-coder:32b`** | **74.6%** | **81.1%** | 80.1% / 69.2% | 10.1 t/s | 9.66s | 15.2G VRAM / 15.3G RAM | Recommended |

### Pareto Scaling Analysis:
- **Accuracy Gains vs. Latency:** Quantifies how much accuracy improves per 100ms of additional response latency.
- **VRAM Saturation:** Identifies the parameter threshold where weights fit completely in 16GB VRAM vs. when CPU memory offloading occurs.
