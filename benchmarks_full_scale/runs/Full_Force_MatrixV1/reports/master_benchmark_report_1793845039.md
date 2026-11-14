# CodeDEE: Full-Scale Vulnerability Detection Benchmark

- **Dataset Scale:** Cleaned & Normalized Dataset (928 Samples)
- **RAG Engine:** ChromaDB Vector Store with Few-Shot Code Pairs
- **Hardware Environment:** Intel Core Ultra 9 275HX, NVIDIA RTX 5080 Laptop GPU (16 GB VRAM)
- **Inference Platform:** Ollama (Windows 11 Enterprise x64)

## 🏆 Overall Performance Leaderboard

| Model Name | Overall Accuracy | Python Acc | JavaScript Acc | TypeScript Acc | Avg Latency (s) | Speed (tok/s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **qwen2.5-coder:14b** | **59.27%** | 57.93% | 62.53% | 54.49% | 4.64s | 26.44 |
| **gpt-oss:20b** | **58.51%** | 62.25% | 59.06% | 50.00% | 7.32s | 89.24 |
| **deepseek-coder:6.7b** | **50.11%** | 49.28% | 55.58% | 39.33% | 3.68s | 30.92 |
| **llama3.1:8b** | **48.06%** | 50.72% | 50.12% | 38.20% | 3.39s | 32.12 |
| **qwen2.5-coder:7b** | **46.98%** | 49.57% | 44.91% | 46.63% | 3.34s | 33.85 |
| **codellama:7b** | **40.95%** | 37.18% | 48.39% | 31.46% | 3.76s | 33.7 |
| **qwen2.5:1.5b** | **40.09%** | 40.06% | 44.42% | 30.34% | 2.69s | 48.36 |
| **qwen2.5-coder:1.5b** | **38.36%** | 34.29% | 46.40% | 28.09% | 2.75s | 53.27 |
