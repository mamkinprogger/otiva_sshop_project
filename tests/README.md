# Организация структуры нагрузочного тестирования k6

## 1. Структура проекта

Для организации нагрузочного тестирования используется следующая структура директорий:

```text
otiva_sshop_project/
│
├── otiva_sshop/
│   └── module/
│       └── tests/
│           ├── quality/
│           └── load/
│               ├── scripts/
│               │   ├── test_webhook.sh
│               │   └── test_notif.sh
│               │
│               └── testing/
│                   ├── config/
│                   │   ├── environments.js
│                   │   ├── workloads.js
│                   │   ├── thresholds.js
│                   │   └── index.js
│                   │
│                   ├── tests/
│                   │   ├── health.js
│                   │   └── auth.js
│                   │
│                   ├── scenarios/
│                   │   ├── auth/
│                   │   │   ├── login.js
│                   │   │   ├── register.js
│                   │   │   └── logout.js
│                   │   │
│                   │   ├── chat/
│                   │   │   ├── send-message.js
│                   │   │   ├── get-history.js
│                   │   │   └── create-chat.js
│                   │   │
│                   │   └── health/
│                   │       └── health-check.js
│                   │
│                   ├── clients/
│                   │   ├── base-client.js
│                   │   ├── auth-client.js
│                   │   ├── chat-client.js
│                   │   └── user-client.js
│                   │
│                   └── lib/
│                       ├── checks.js
│                       ├── error-handler.js
│                       ├── metrics.js
│                       ├── data-generator.js
│                       ├── helpers.js
│                       └── data.js
│
├── tests/
│   ├── _reports/
│   │   └── *modules
│   │
│   ├── notes/
│   │
│   ├── scripts/
│   │   ├── paths_scripts.txt
│   │   ├── run_all_tests
│   │   └── run_one_test
│   │
│   ├── .env
│   ├── compose-load.yml
│   ├── Dockerfile-k6
│   └── k6-entrypoint.sh
│
└── compose-dev.yml
```

## 2. Регистрация директорий нагрузочного тестирования

При добавлении нового модуля с нагрузочными тестами необходимо указать путь к его директории `load` в файле:

```text
tests/scripts/paths_scripts.txt
```

**Пример содержимого:**

```text
../../otiva_sshop/chat/tests/load
../../otiva_sshop/module/tests/load
```

Пути указываются относительно директории `tests/scripts/`.

## 3. Требования к структуре нагрузочных тестов

После добавления пути необходимо соблюдать установленную структуру директорий внутри папки `load`.

Это необходимо для корректной работы скриптов запуска:

- `run_one_test` — запуск отдельного нагрузочного теста.
- `run_all_tests` — последовательный запуск всех зарегистрированных нагрузочных тестов.

**Важно:** при добавлении новых модулей с нагрузочными тестами необходимо не только зарегистрировать путь в `paths_scripts.txt`, но и соблюдать общую структуру проекта. Это обеспечивает совместимость тестов с существующими механизмами запуска.

---

Также в директории notes указаны future features, которые можно реализовать впоследствии

Для захода в административную панель django login/password: k6