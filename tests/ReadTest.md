Как запустить тесты

Открой терминал в папке проекта и запусти команду:

pytest -v

Ожидаемый результат:

Ты должен увидеть зеленый текст, сообщающий, что все тесты пройдены (PASSED).

Что то в этом духе...

tests/test_core.py::test_hash_determinism PASSED           [ 14%]
tests/test_core.py::test_hash_salting PASSED               [ 28%]
...
tests/test_financial.py::test_top_coding_winsorization PASSED [100%]

========== 10 passed in 0.15s ==========