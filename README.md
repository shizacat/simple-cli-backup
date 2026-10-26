# Simple CLI Backup

Простая настройка бэкапов на северах.

Возможности:
- Настройка через yml файл
- Для запуска используется одна точка входа
 	В cron можно указать один файл, а все рассписание будет в файлах настроек

## Требования 

Python 3.11+

## Установка

```bash
pip install sback
```

Через консоль можно будет запустить через `sback` команду.

### Ansible

Роль [contribute/ansible_role](contribute/ansible_role/README.md) ставит `sback` в отдельное виртуальное окружение `/opt/sback` и создаёт ссылку `/usr/local/bin/sback`. Зависимости Python остаются в этом окружении. Если задать `sback_config`, роль записывает этот YAML в `/etc/sback/config.yml` и добавляет запуск в `/etc/cron.d/sback`. Время запуска задаётся в `sback_cron_schedule`.

```yaml
- hosts: servers
  become: true
  roles:
    - role: shizacat.sback.sback
```

Установка через Ansible. Фрагмент `#/contribute/ansible_role/` берёт коллекцию из этого каталога репозитория. `version` — тег, ветка или коммит Git.

```bash
ansible-galaxy install -r requirements.yml
```

```yaml
---
collections:
  - name: https://github.com/shizacat/simple-cli-backup.git#/contribute/ansible_role/
    type: git
    version: "0.1.0"
```

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
