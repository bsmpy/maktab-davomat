# Нативное развёртывание (systemd + nginx хоста)

Стенд работает **не через docker compose**, а нативно: на хосте уже стоит
aaPanel-nginx (занимает 80/443), и другие проекты живут по той же схеме —
systemd + vhost. Доступ — из локальной сети по IP, без домена и без TLS.

```text
Браузер (локальная сеть)
  → nginx этой машины (:80)        vhost face-lan, http://192.168.0.100
    → /                            статика   frontend/dist
    → /admin                       тот же SPA (админка), отдельного бэкенда нет
    → /api/                        proxy →   gunicorn 127.0.0.1:8021
    → /static/, /media/            файлы     backend/staticfiles, backend/media
```

> Django-админки нет: `django.contrib.admin` не установлен, URL не заведён.
> Единственная точка входа — `http://192.168.0.100/admin`, это раздел SPA
> поверх `/api/v1/management/`. Отдельной правки nginx не требуется:
> `try_files … /index.html` отдаёт SPA на любом неизвестном пути.

## Сервисы (systemd, автозапуск включён)

| Юнит | Что делает |
|---|---|
| `maktab-davomat-api` | gunicorn, 4 воркера, `127.0.0.1:8021` |
| `maktab-davomat-celery` | worker: уведомления, обработка событий турникета, загрузка лиц |
| `maktab-davomat-beat` | опрос терминалов, закрытие учебного дня, синхронизация часов |
| `maktab-davomat-bot` | Telegram-бот (long polling) |

```bash
systemctl status  maktab-davomat-api maktab-davomat-celery maktab-davomat-beat maktab-davomat-bot
systemctl restart maktab-davomat-api
journalctl -u maktab-davomat-api -f
```

## Базы (docker, только на 127.0.0.1)

| Контейнер | Порт | Политика |
|---|---|---|
| `maktab-davomat-postgres` | `127.0.0.1:55432` | `unless-stopped` |
| `maktab-davomat-redis` | `127.0.0.1:56379` | `unless-stopped` |

Порты нестандартные намеренно: на машине уже есть чужой PostgreSQL на 5432 и
Redis с паролем на 6379. Наружу они не смотрят.

```bash
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml up -d      # поднять после ребута вручную не нужно
```

## nginx

Конфиги лежат в репозитории и подключены симлинками — правки версионируются:

```text
deploy/nginx/host/face-lan.conf          → /www/server/panel/vhost/nginx/face-lan.conf
deploy/nginx/host/security-headers.conf     подключается внутрь location'ов
```

> `add_header` в nginx **не наследуется**, если в `location` есть свой
> `add_header` — поэтому заголовки безопасности вынесены в сниппет и
> подключаются в каждый такой блок. Для проксируемых ответов их ставит сама
> Django (`SecurityMiddleware`), в nginx они там намеренно не дублируются.

```bash
nginx -t && nginx -s reload
```

## Обновление (деплой новой версии)

```bash
cd /www/wwwroot/websites/maktab-davomat

# backend
cd backend
.venv/bin/pip install -r requirements.txt          # если менялись зависимости
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
systemctl restart maktab-davomat-api maktab-davomat-celery maktab-davomat-beat

# frontend
cd ../frontend && npm ci && npm run build          # VITE_API_URL пустой → запросы на тот же адрес

# bot
systemctl restart maktab-davomat-bot
```

`frontend/dist` отдаётся nginx напрямую, поэтому после `npm run build`
перезапускать ничего не нужно.

## Проверка после деплоя

```bash
curl -s http://192.168.0.100/api/health/          # {"status":"ok",...}
curl -sI http://192.168.0.100/ | head -1          # 200
systemctl is-active maktab-davomat-api maktab-davomat-celery maktab-davomat-beat maktab-davomat-bot
```

## Что ещё не настроено

* **SMS**: `SMS_PROVIDER=console` — коды пишутся в журнал сервиса, а не уходят
  родителю. Ввести доступы Eskiz в Sozlamalar → Integratsiyalar → SMS и
  включить интеграцию.
* **Терминалы**: заведён один демо-терминал `192.168.10.50`, **выключен**,
  чтобы beat не долбил несуществующий IP. Реальные устройства добавляются в
  Sozlamalar → Integratsiyalar → Terminallar.
* **Данные**: база очищена (`manage.py reset_data --keep-user bsm --yes`).
  Остались только учётка `bsm` (DEVELOPER) и настройки интеграций. Реальный
  реестр заливается через `http://192.168.0.100/admin` — Excel-импортом или
  вручную — до этого регистрация родителей работать не будет, потому что она
  проверяет человека по реестру.
  Дамп перед очисткой: `/www/backup/maktab-davomat/before-reset-*.sql.gz`.
* **Посещаемость считается турникетом.** Пока ни одного реального устройства
  не заведено, кабинет будет показывать пустые дни: записи о входах и выходах
  появляются только из событий терминала.
