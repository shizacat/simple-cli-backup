# Simple CLI Backup

Простая настройка бэкапов на северах.

Возможности:
- Настройка через yml файл
- Для запуска используется одна точка входа
 	В cron можно указать один файл, а все рассписание будет в файлах настроек

## Требования 

Python 3.10+

## Разработка

Документация: [docs/README.md](docs/README.md).

### Настройка окружения

```bash
uv sync
```

### Запуск

```bash
uv run sback --config config.yml
uv run sback -t config.yml
uv run sback init --config config.yml
```

`-t` проверяет файл настроек и не запускает бэкап. То же самое делает `--config-test`.

### Тестирование

```bash
uv run pytest
```

### Линтинг

Python-код форматируется через black.

```bash
uv run black .
uv run black --check .
```

### Локализация

```bash
cd ./
pygettext -a -d scb source/
```
