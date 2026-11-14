# CodeDEE: Full-Scale Vulnerability Detection Benchmark

- **Dataset Scale:** Cleaned & Normalized Dataset (50 Samples)
- **RAG Engine:** ChromaDB Vector Store with Few-Shot Code Pairs
- **Hardware Environment:** Intel Core Ultra 9 275HX, NVIDIA RTX 5080 Laptop GPU (16 GB VRAM)
- **Inference Platform:** Ollama (Windows 11 Enterprise x64)

## 🏆 Overall Performance Leaderboard

| Model Name | Overall Accuracy | Python Acc | JavaScript Acc | TypeScript Acc | Avg Latency (s) | Speed (tok/s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **qwen2.5-coder:32b** | **48.00%** | 58.82% | 50.00% | 41.94% | 43.72s | 3.0 |
| **qwen2.5-coder:7b** | **42.00%** | 47.06% | 0.00% | 41.94% | 3.67s | 29.15 |
| **qwen2.5-coder:14b** | **40.00%** | 41.18% | 0.00% | 41.94% | 5.94s | 21.77 |
| **gpt-oss:20b** | **38.00%** | 52.94% | 50.00% | 29.03% | 10.33s | 84.2 |
| **llama3.1:8b** | **28.00%** | 35.29% | 0.00% | 25.81% | 3.92s | 28.92 |
| **qwen2.5:1.5b** | **24.00%** | 23.53% | 50.00% | 22.58% | 2.8s | 51.4 |
| **deepseek-coder:6.7b** | **22.00%** | 17.65% | 50.00% | 22.58% | 4.51s | 25.82 |
| **codellama:7b** | **20.00%** | 17.65% | 50.00% | 19.35% | 4.46s | 28.27 |
| **qwen2.5-coder:1.5b** | **16.00%** | 11.76% | 50.00% | 16.13% | 2.85s | 47.42 |
