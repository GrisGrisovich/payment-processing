# Асинхронный процессинг платежей

Сервис принимает заявки на платежи, обрабатывает их асинхронно и отправляет результат через webhook.

## Запуск

Для запуска нужен Docker с Compose. При первом запуске выполните команды из корня проекта.

```sh
cp .env.example .env
docker compose up --build --wait
```

Compose запускает API, consumer, PostgreSQL и RabbitMQ. API применяет миграции перед запуском. API доступен на `http://localhost:8000`, интерфейс RabbitMQ — на `http://localhost:15672` с локальными учётными данными `payments` / `payments`.

Примеры используют ключ `local-dev-key` из `.env.example`. Если вы изменили `API_KEY` в `.env`, подставьте его в заголовок `X-API-Key`.

`DATABASE_URL` задаёт подключение к PostgreSQL для API, миграций и consumer, а `RABBITMQ_URL` — подключение consumer к брокеру. В `.env.example` указаны адреса локальных контейнеров. Для внешней инфраструктуры задайте свои адреса в `.env` или окружении деплоя.

## Примеры

### Запустить получатель webhook

Выполните команду в отдельном терминале из корня проекта. Получатель печатает JSON уведомления и отвечает `200 OK`.

```sh
docker compose run --rm --no-deps --name payment-webhook \
  -v "$PWD/tests/receiver.py:/receiver.py:ro" api python /receiver.py
```

### Создать платёж

Передавайте сумму строкой для сохранения десятичной точности. Для нового платежа задайте новый `Idempotency-Key`. Повтор с тем же ключом и теми же данными вернёт тот же `payment_id`. Если изменить данные, API вернёт `409 Conflict`.

```sh
curl -i http://localhost:8000/api/v1/payments \
  -H 'X-API-Key: local-dev-key' \
  -H 'Idempotency-Key: order-42' \
  -H 'Content-Type: application/json' \
  -d '{
    "amount": "125.50",
    "currency": "RUB",
    "description": "Заказ 42",
    "metadata": {"order_id": 42},
    "webhook_url": "http://payment-webhook:9000/webhook"
  }'
```

Пример ответа `202 Accepted` после создания платежа.

```json
{
  "payment_id": "b312a162-3d8e-47fc-8b4b-9714cafeec42",
  "status": "pending",
  "created_at": "2026-11-18T19:00:00Z"
}
```

### Получить статус платежа

Подставьте `payment_id` из ответа на POST.

```sh
PAYMENT_ID='вставьте payment_id из ответа'
curl -i "http://localhost:8000/api/v1/payments/$PAYMENT_ID" \
  -H 'X-API-Key: local-dev-key'
```

Во время обработки статус — `pending`, а `processed_at` равен `null`. После обработки GET вернёт `succeeded` или `failed` и время обработки. Пример ответа `200 OK` для успешного платежа.

```json
{
  "payment_id": "b312a162-3d8e-47fc-8b4b-9714cafeec42",
  "status": "succeeded",
  "created_at": "2026-11-18T19:00:00Z",
  "amount": "125.50",
  "currency": "RUB",
  "description": "Заказ 42",
  "metadata": {"order_id": 42},
  "webhook_url": "http://payment-webhook:9000/webhook",
  "processed_at": "2026-11-18T19:00:03Z"
}
```

### Проверить повторы webhook

Webhook содержит те же поля, что и GET, за исключением `webhook_url`. Чтобы увидеть две ошибки и успешный повтор, остановите локальный получатель и запустите его с заданной последовательностью ответов.

```sh
docker compose run --rm --no-deps --name payment-webhook \
  -e WEBHOOK_STATUSES=503,503,200 \
  -v "$PWD/tests/receiver.py:/receiver.py:ro" api python /receiver.py
```

Создайте платёж с новым ключом и посмотрите вывод получателя. По умолчанию после ошибок следуют повторы через 1 и 2 секунды. Если все три попытки завершились ошибкой, сообщение попадает в `payments.dlq`. Лимит попыток и начальную задержку можно изменить в `.env` через `WEBHOOK_MAX_ATTEMPTS` и `WEBHOOK_RETRY_BASE_DELAY_SECONDS`.

## Автоматические тесты

**Юнит-тесты** проверяют правила повторов, переход к DLQ и обработку повторного события. Для запуска нужен `uv`.

```sh
uv run --locked pytest tests/unit
```

**Интеграционные тесты** проверяют HTTP-контракт, конкурентную идемпотентность, откат транзакции в PostgreSQL и формирование webhook для обоих исходов шлюза. Команды запускают отдельный Compose-проект с мигрированной базой и API. Если основной проект уже работает, освободите порт 8000 командой `docker compose down`.

```sh
env -u DATABASE_URL docker compose --env-file .env.example -p payment-check up --build --wait api
docker compose --env-file .env.example -p payment-check run --rm --no-deps -T \
  -e PAYMENT_TEST_DATABASE_URL=postgresql+asyncpg://payments:payments@postgres:5432/payments \
  -v "$PWD/tests:/app/tests:ro" api uv run --locked pytest tests/integration
docker compose --env-file .env.example -p payment-check down --volumes
```
