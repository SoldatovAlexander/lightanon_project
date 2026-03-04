import time
import lightanon as la

# 1. Схема (единая для всех движков!)
schema = {
    "user_id": la.rules.Hash(salt="kafka_secret"),
    "ip":      la.rules.Mask(visible_chars=3),    # 192.***
    "amount":  la.rules.GaussianNoise(std=0.1)
}

# 2. Инициализация StreamEngine
engine = la.StreamEngine(schema)

# 3. Имитация потока данных (Kafka Consumer)
raw_stream = [
    {"ts": 162001, "user_id": "alice", "ip": "192.168.1.1", "amount": 100.0},
    {"ts": 162002, "user_id": "bob",   "ip": "10.0.0.5",    "amount": 5000.0},
    {"ts": 162003, "user_id": "alice", "ip": "192.168.1.1", "amount": 150.0},
]

print("Starting Stream Processing...")
start_time = time.time()

# Обработка
for event in engine.process_iter(raw_stream):
    print(f"Clean Event: {event}")

print(f"Done in {time.time() - start_time:.6f}s")

# Пример проверки консистентности
# Хэш для 'alice' должен быть одинаковым в обоих событиях
clean_events = engine.process_batch(raw_stream)
assert clean_events[0]['user_id'] == clean_events[2]['user_id']
print("\nConsistency Check: PASSED")