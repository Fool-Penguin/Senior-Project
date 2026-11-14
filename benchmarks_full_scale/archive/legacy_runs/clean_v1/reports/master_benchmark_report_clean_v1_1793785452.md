# CodeDEE: Full-Scale Vulnerability Detection Benchmark

- **Dataset Scale:** Cleaned & Normalized Dataset (50 Samples)
- **RAG Engine:** ChromaDB Vector Store with Few-Shot Code Pairs
- **Hardware Environment:** Intel Core Ultra 9 275HX, NVIDIA RTX 5080 Laptop GPU (16 GB VRAM)
- **Inference Platform:** Ollama (Windows 11 Enterprise x64)

## 🏆 Overall Performance Leaderboard

| Model Name | Overall Accuracy | Python Acc | JavaScript Acc | TypeScript Acc | Avg Latency (s) | Speed (tok/s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **qwen2.5-coder:32b** | **34.00%** | 41.18% | 0.00% | 32.26% | 19.24s | 6.22 |
| **qwen2.5:1.5b** | **16.00%** | 23.53% | 50.00% | 9.68% | 2.76s | 49.23 |
| **qwen2.5-coder:1.5b** | **14.00%** | 11.76% | 50.00% | 12.90% | 2.74s | 43.68 |
| **qwen2.5-coder:7b** | **14.00%** | 0.00% | 0.00% | 22.58% | 3.49s | 28.95 |
| **qwen2.5-coder:14b** | **14.00%** | 5.88% | 0.00% | 19.35% | 5.08s | 22.48 |
| **gpt-oss:20b** | **14.00%** | 23.53% | 0.00% | 9.68% | 9.2s | 90.48 |
| **llama3.1:8b** | **12.00%** | 0.00% | 0.00% | 19.35% | 3.56s | 30.16 |
| **deepseek-coder:6.7b** | **8.00%** | 0.00% | 50.00% | 9.68% | 4.02s | 22.56 |
| **codellama:7b** | **8.00%** | 5.88% | 50.00% | 6.45% | 4.41s | 30.92 |
