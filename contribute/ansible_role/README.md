# Роль Ansible для sback

Роль ставит утилиту `sback` в отдельное виртуальное окружение и добавляет команду в `PATH`. Зависимости Python остаются в этом окружении.

По умолчанию окружение лежит в `/opt/sback`, а команда доступна как `/usr/local/bin/sback`. Скрипт запускает интерпретатор из окружения, поэтому системный Python не используется.

На Debian и Ubuntu системный Python помечен как externally managed. Роль поэтому не вызывает системный `pip`.

## Требования

- Ansible 2.14 или новее
- Собранные факты Ansible
- Debian, Ubuntu, RHEL, CentOS, Rocky, AlmaLinux или Fedora
- Python 3.11 или новее
- Доступ к PyPI, если пакет ставится оттуда
- Права суперпользователя (`become: true`)
- Учётная запись из `sback_user` и группа из `sback_group` уже существуют

На Ubuntu 22.04 системный `python3` — это 3.10. Поставьте Python 3.11+ и укажите его в `sback_python`.

## Подключение

Каталог `contribute/ansible_role` — коллекция. Роль внутри называется `sback`, в плейбуке это `shizacat.sback.sback`.

Файл `requirements.yml`:

```yaml
---
collections:
  - name: https://github.com/shizacat/simple-cli-backup.git#/contribute/ansible_role/
    type: git
    version: "0.1.0"
```

```bash
ansible-galaxy install -r requirements.yml
```

```yaml
- hosts: servers
  become: true
  roles:
    - role: shizacat.sback.sback
```

Из клона репозитория, без Galaxy:

```yaml
- hosts: servers
  become: true
  roles:
    - role: contribute/ansible_role/roles/sback
```

## Переменные

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `sback_python` | `python3` | Интерпретатор Python 3.11+ |
| `sback_venv_path` | `/opt/sback` | Каталог виртуального окружения |
| `sback_bin_path` | `/usr/local/bin/sback` | Ссылка на команду |
| `sback_package` | `sback` | Имя на PyPI, каталог исходников или ссылка pip |
| `sback_version` | пусто | Версия пакета PyPI, в кавычках |
| `sback_pip_state` | `present` | `present` ставит отсутствующий пакет, `latest` обновляет |
| `sback_system_packages` | `[]` | Свой список пакетов ОС вместо списка роли |
| `sback_user` | `root` | Владелец файлов окружения |
| `sback_group` | `root` | Группа файлов окружения |
| `sback_config` | `{}` | Настройки бэкапа: словарь или текст YAML. Пустое значение ничего не пишет |
| `sback_config_path` | `/etc/sback/config.yml` | Куда записать `sback_config` |
| `sback_config_mode` | `0640` | Права файла настроек |
| `sback_cron_enabled` | `true` | При непустом `sback_config` создать задание. `false` удаляет его |
| `sback_cron_path` | `/etc/cron.d/sback` | Файл задания |
| `sback_cron_user` | `root` | Пользователь, от которого cron запускает `sback` |
| `sback_cron_schedule` | `0 3 * * *` | Минута, час, день месяца, месяц, день недели |

Пустой `sback_config` оставляет установку без файла настроек и без задания cron и не изменяет уже созданные файл и задание. Непустое значение записывается в `sback_config_path`. Роль проверяет файл командой `sback --config-test` и, если `sback_cron_enabled` включён, ставит пакет cron и задание. Команда в задании: `sback --config` с путём к этому файлу. Расписание берётся из `sback_cron_schedule`, по умолчанию каждый день в 03:00. `sback_cron_enabled: false` при заданном `sback_config` удаляет файл в `cron.d`.

На Debian и Ubuntu пакет и служба называются `cron`. На RHEL и Fedora роль ставит пакет `cronie` и включает службу `crond`. Имена можно заменить переменными `sback_cron_package` и `sback_cron_service`.

Пустой `sback_system_packages` выбирает пакеты по семейству ОС:

- Debian и Ubuntu: `ca-certificates`, интерпретатор и пакет `venv`
- RHEL и Fedora: `ca-certificates`, интерпретатор и пакет `pip`, чтобы `venv` мог поставить pip внутрь окружения

Имя пакета берётся из имени программы в `sback_python`. Для `python3.12` роль ставит `python3.12` и `python3.12-venv`.

## Примеры

Зафиксировать версию:

```yaml
- hosts: servers
  become: true
  roles:
    - role: shizacat.sback.sback
      sback_version: "1.3.0"
```

Поставить Python 3.12 и обновлять пакет при повторном запуске:

```yaml
- hosts: servers
  become: true
  roles:
    - role: shizacat.sback.sback
      sback_python: python3.12
      sback_pip_state: latest
```

Поставить из каталога с исходниками:

```yaml
sback_package: /opt/src/sback
sback_version: ""
```

Другое семейство ОС — пакеты задаются явно:

```yaml
sback_python: python3
sback_system_packages:
  - ca-certificates
  - python3
  - python3-venv
```

Записать настройки и запускать бэкап каждый день в 04:15:

```yaml
sback_cron_schedule: "15 4 * * *"
sback_config:
  places:
    - name: local
      type: folder
      rotate:
        count: 6
      config:
        path: /var/backups
  slises:
    - name: daily
      place:
        - local
      target:
        - name: etc
          type: file
          config:
            path:
              - /etc
```

Только файл настроек, без задания cron:

```yaml
sback_cron_enabled: false
sback_config:
  places:
    - name: local
      type: folder
      config:
        path: /var/backups
  slises:
    - name: daily
      place:
        - local
      target:
        - name: etc
          type: file
          config:
            path:
              - /etc
```

Чтобы окружение собралось заново, удалите каталог `sback_venv_path` и запустите роль ещё раз. Это нужно после смены `sback_python` или `sback_user`.
