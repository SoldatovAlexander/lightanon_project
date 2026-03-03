# LightAnon

**High-Performance Data Anonymization for ML & Compliance (152-FZ)**

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Engine](https://img.shields.io/badge/engine-Pandas%20%7C%20Polars-orange)
![License](https://img.shields.io/badge/license-MIT-green)
![Compliance](https://img.shields.io/badge/compliance-152--FZ-red)

**LightAnon** is a zero-config Python library designed to anonymize datasets for Machine Learning pipelines. It supports **Pandas** for standard tasks and **Polars** for high-performance processing of large datasets (10GB+). It helps you safely share data complying with **Roskomnadzor Order No. 996 (152-FZ)** while preserving statistical utility.

## 🚀 Key Features

* **Dual Engine:** Seamlessly switch between `pandas` (standard) and `polars` (turbo mode for big data).
* **CLI Tool:** Anonymize files directly from the terminal using YAML configuration.
* **Utility Preservation:** Uses statistical noise, generalization, and bucketing to preserve data distribution.
* **Compliance Audit:** Automatically generates a report mapping applied transformations to legal methods.
* **FinTech Ready:** Specialized rules for financial data (Multiplicative Noise, Whale/Outlier protection).

## 📦 Installation

```bash
git clone [https://github.com/your-username/lightanon.git](https://github.com/your-username/lightanon.git)
cd lightanon
pip install -r requirements.txt