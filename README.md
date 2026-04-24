# 🚀 Hyper-Tier Studio Pro
### *Industrial-Grade Local Data Refinery & Vector Engine*

![Status](https://img.shields.io/badge/Release-Professional_Edition-blue)
![Engine](https://img.shields.io/badge/Vector_Engine-DuckDB-orange)
![AI](https://img.shields.io/badge/Local_AI-Ollama/Phi--3-green)

---

## 📖 About the Project
Hyper-Tier Studio Pro is a high-performance, vectorized data engine designed to process tens of millions of rows locally without cloud costs. By utilizing a **Columnar Vectorized Engine**, it bypasses the limitations of standard Python (Pandas), allowing a single workstation to handle "Big Data" at the speed of thought.

---

## 📊 Real-World Performance Benchmark
Tested on legacy hardware to prove efficiency.

- **Machine:** Lenovo IdeaPad 500 15ISK (2015)
- **CPU:** i7-6500U | **RAM:** 12GB | **Storage:** SATA SSD Caddy
- **Dataset:** NYC Yellow Taxi (12.7 Million Rows / 2.1 GB)
- **Execution Time:** **3 minutes 30 seconds**

---

## 🛠 Key Features
*   **Vectorization Kernel:** Powered by DuckDB for SIMD-accelerated processing.
*   **Neural Bridge:** Local AI (Phi-3) for Natural Language-to-SQL translation.
*   **Industrial Output:** Native Parquet support with ZSTD compression.
*   **Disk Spilling:** Process datasets larger than your RAM safely.

---

## 🚦 Getting Started
1. Run `python build_production.py` to auto-setup the environment.
2. Launch via `python launch.py`.
3. (Optional) Run `ollama run phi3:mini` for AI features.
