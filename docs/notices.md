# Уведомления

Уведомление сообщает, чем закончился срез. Канал описывается в `notices`, а срез выбирает его в поле `notify`.

Поле `status` у ссылки решает, когда отправлять отчет: `good` — только если срез прошел без ошибок, `bad` — только если хотя бы одна цель или место завершились ошибкой. Без `status` отчет уходит всегда.

Ошибка одной цели не останавливает остальные цели среза. Ошибка одного места не останавливает остальные места. После отчета команда завершается с ошибкой, если срез или отправка не удались.

## Контракт

Класс уведомления лежит в пакете `sback/notices` и наследует `NotifyBase` из `sback/lib/notify_base.py`.

- `name` совпадает с полем `type` в настройках.
- `description` — краткое описание канала.
- `config_model` — pydantic-модель поля `config`.
- `send(body)` отправляет готовый текст отчета.

Если тип не зарегистрирован или `config` не проходит `config_model`, возникает `NotifyError`.

## Сейчас реализовано

`email` отправляет отчет по SMTP. Обязательны `server`, `to` и `from`. `server` записывается как `host` или `host:port`; без порта используется 25. `password` включает вход на сервер. `ssl: true` открывает SMTP SSL. `starttls: true` включает STARTTLS на обычном соединении. Если заданы оба, используется SSL. Тема по умолчанию `---= Backup info =---`.

```yaml
notices:
  - name: mail
    type: email
    config:
      server: smtp.example.com:587
      to:
        - a@example.com
      from: backup@example.com
      password: secret
      starttls: true

slises:
  - name: daily
    place:
      - local
    target:
      - name: files
        type: file
        config:
          path:
            - /etc
    notify:
      - name: mail
        status: bad
```
