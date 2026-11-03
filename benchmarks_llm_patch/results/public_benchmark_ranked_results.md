# Official OpenAI HumanEval Benchmark: Ranked Local Model Leaderboard

> **Benchmark Dataset:** Official OpenAI HumanEval (`HumanEval.jsonl`, 100% Public Data)  
> **Evaluation Mode:** Greedy Decoding ($T = 0.0$, Deterministic)  
> **Evaluated Tasks:** 164 Standard Python Coding Problems  
> **Test Harness:** Subprocess execution with official `check()` assertions  
> **Date:** October 2026  

---

### Ranked Leaderboard Table

| Rank | Model Name | Parameter Size | Pass@1 Success Rate | Correct / Total | Generation Speed | Avg Latency | Recommendation Tier |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **#1** | **`qwen2.5-coder:7b`** | 7.6B | **89.0%** | 146/164 | 107.5 t/s | 3.53s | **Default Local (Standard GPU >= 6GB)** |
| **#2** | **`deepseek-coder:6.7b`** | 6.7B | **75.0%** | 123/164 | 123.9 t/s | 2.96s | Alternative Baseline |
| **#3** | **`qwen2.5-coder:1.5b`** | 1.5B | **68.3%** | 112/164 | 283.7 t/s | 2.76s | **Default Local (Low-Spec CPU / <= 8GB RAM)** |
| **#4** | **`llama3.1:8b`** | 8.0B | **64.6%** | 106/164 | 101.7 t/s | 3.87s | Alternative Baseline |
| **#5** | **`gpt-oss:20b`** | 20.0B | **54.3%** | 89/164 | 92.1 t/s | 8.17s | **High-Capacity Local (High-End GPU >= 16GB / 32GB RAM)** |
| **#6** | **`codellama:7b`** | 7.0B | **40.9%** | 67/164 | 124.2 t/s | 3.37s | Alternative Baseline |

---

### Key Takeaways
1. **Pass@1 Functional Correctness:** Models are ranked by their ability to write syntactically valid code that satisfies 100% of OpenAI's rigorous test assertions.
2. **Speed & Efficiency:** Throughput (tokens/second) reflects live inference speed on local hardware.
3. **Reproducibility:** Anyone can re-run this exact test with:
   ```powershell
   # Test all models:
   python benchmarks_llm_patch/run_public_benchmark_test.py all 10

   # Or test a specific model (e.g. gpt-oss:20b) and auto-merge into leaderboard:
   python benchmarks_llm_patch/run_public_benchmark_test.py gpt-oss:20b 10
   ```
