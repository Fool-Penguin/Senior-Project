# CodeDEE Comprehensive Multi-Benchmark Evaluation & Scaling Report

> **Evaluation Protocol:** Standard Academic Instruct Protocol (ChatML Template + Robust Code Extractor)  
> **Hardware:** NVIDIA GeForce RTX 5080 Laptop GPU (16 GB VRAM)  
> **Runtime Environment:** Managed Python 3.12, Node.js v24 (Native TypeScript Stripping)  
> **Total Evaluated Tasks per Model:** Up to 1,234 tasks across 5 academic benchmarks:  
> 1. **OpenAI HumanEval (Official):** 164 Python algorithmic tasks  
> 2. **MultiPL-E (JS & TS):** 161 JavaScript & 159 TypeScript tasks  
> 3. **BigCodeBench:** 250 tasks across 139 Python engineering libraries  
> 4. **SantaCoder FIM:** 250 bidirectional infilling tasks across Python & JavaScript  
> 5. **CRUXEval:** 250 code execution reasoning tasks  

---

## 1. Ranked Multi-Benchmark Leaderboard (Phase 1 Screening)

| Rank | Model Name | Overall Score | OpenAI HumanEval | MultiPL-E (JS) | MultiPL-E (TS) | BigCodeBench | FIM (Infill) | CRUXEval | Speed (Tokens/s) | Latency (s) | RAM Used | VRAM Footprint |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **`qwen2.5-coder:7b`** | **69.5%** | **89.0%** | 85.0% | 85.0% | 45.0% | 63.0% | 50.0% | **127.0 t/s** | **1.18s** | 10.2 GB | 5.8 GB |
| **#2** | **`qwen2.5-coder:1.5b`** | **66.2%** | **82.0%** | 72.0% | 78.0% | 47.0% | 88.0% | 30.0% | **332.6 t/s** | **0.41s** | 13.8 GB | 7.4 GB |
| **#3** | **`deepseek-coder:6.7b`** | **48.3%** | **78.0%** | 76.0% | 81.0% | 54.0% | 1.0% | 0.0% | **142.0 t/s** | **0.99s** | 13.4 GB | 6.1 GB |
| **#4** | **`codellama:7b`** | **46.5%** | **56.0%** | 47.0% | 50.0% | 63.0% | 58.0% | 5.0% | **140.9 t/s** | **1.43s** | 12.5 GB | 6.1 GB |
| **#5** | **`gpt-oss:20b`** | **41.8%** | **60.0%** | 70.0% | 75.0% | 41.0% | 0.0% | 5.0% | **141.6 t/s** | **2.25s** | 11.5 GB | 13.1 GB |
| **#6** | **`llama3.1:8b`** | **38.0%** | **73.0%** | 18.0% | 53.0% | 48.0% | 1.0% | 35.0% | **119.9 t/s** | **1.40s** | 13.0 GB | 6.2 GB |

---

## 2. Benchmark Breakdown & Empirical Capabilities

1. **OpenAI HumanEval (164 tasks):** Standard Python algorithmic problem-solving under official academic zero-shot Pass@1 conditions.
2. **MultiPL-E JavaScript & TypeScript (320 tasks):** Cross-lingual polyglot performance verifying type safety and ecosystem consistency in modern web runtimes.
3. **BigCodeBench (250 tasks):** Real-world library API orchestration across 139 packages (`pandas`, `requests`, `cryptography`, `numpy`), measuring practical software engineering.
4. **SantaCoder FIM (250 tasks):** Bidirectional infilling evaluating the model's ability to insert patches between existing prefixes and suffixes.
5. **CRUXEval (250 tasks):** Execution simulation testing whether the model accurately models runtime execution state rather than merely pattern-matching tokens.

---
