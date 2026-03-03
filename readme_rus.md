
```markdown
# LightAnon

**Высокопроизводительная анонимизация данных для ML и 152-ФЗ**

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Engine](https://img.shields.io/badge/engine-Pandas%20%7C%20Polars-orange)
![License](https://img.shields.io/badge/license-MIT-green)
![Compliance](https://img.shields.io/badge/compliance-152--FZ-red)

**LightAnon** — это Python-библиотека для обезличивания данных, ориентированная на скорость и простоту. Она поддерживает **Pandas** для стандартных задач и **Polars** для обработки больших данных (Big Data). Инструмент позволяет готовить датасеты для ML, соблюдая требования **152-ФЗ (Приказ Роскомнадзора № 996)** и сохраняя статистическую полезность данных.

## 🚀 Ключевые возможности

* **Двойной движок:** Автоматическое переключение между `pandas` и `polars` (для сверхбыстрой обработки файлов 10GB+).
* **CLI Интерфейс:** Запуск анонимизации из командной строки через YAML-конфиг (удобно для CI/CD и Airflow).
* **Сохранение полезности:** Использование шума, обобщения и баккетинга вместо простого удаления данных.
* **Юридический отчет:** Генерация справки о соответствии методов требованиям Роскомнадзора.
* **FinTech Ready:** Модуль для финансов (мультипликативный шум, защита от атак на VIP-клиентов/выбросы).

## 📦 Установка

```bash
git clone [https://github.com/your-username/lightanon.git](https://github.com/your-username/lightanon.git)
cd lightanon
pip install -r requirements.txt