# Changelog

Все заметные изменения этого проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/0.3.0/),
проект придерживается [семантического версионирования](https://semver.org/lang/ru/).

## [Unreleased]

### Added

- Правило для агентов: фиксировать каждое изменение в чейнджлоге
- Ansible-роль `contribute/ansible_role`: установка в отдельное виртуальное окружение
- Ansible-роль записывает необязательный файл настроек в `/etc` и задание в `cron.d`
- Роль Ansible ставится из каталога `contribute/ansible_role` через `requirements.yml`

### Removed

- Проверка пути импорта зависимостей в Ansible-роли

## [0.1.0] - 2026-10-26

### Added

- Опция `--plugin-info`

### Changed

- Улучшения кода
- Переписана под pydantic
- Добавлена новая цель - mongodb

## [1.3]

### Fixed

- Исправление ошибок

## [1.2]

### Added

- Вывод версии

### Changed

- Dropbox API v2

### Fixed

- Мелкие исправления

## [1.1]

### Fixed

- Исправление ошибок в блоках `place.mysql` и `place.base`
