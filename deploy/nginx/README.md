# nginx

Both configurations serve the app from **one origin with no domain name** — the
SPA at `/`, the API under `/api/` — reached by IP on the local network, e.g.
`http://192.168.0.100`.

| File | Used by |
|---|---|
| `default.conf` | the `nginx` service in `docker-compose.yml` |
| `host/face-lan.conf` | the host nginx when the app runs natively (see [`deploy/README.md`](../README.md)) |

## Routes (`default.conf`)

| Path | Upstream | Notes |
|---|---|---|
| `/` | `frontend:80` | the built SPA, `/admin` included |
| `/api/` | `backend:8000` | gunicorn |
| `/static/`, `/media/` | shared volumes | collected static files and uploads |

## Why one origin

With the SPA and the API on the same address there is no DNS name and no
certificate to manage:

* the refresh-token cookie is first-party, so `AUTH_COOKIE_DOMAIN` stays empty
  and `SameSite=Lax` is enough;
* CORS never enters the picture;
* the frontend is built with an empty `VITE_API_URL` and calls `/api/v1/...` on
  whatever address it was opened from, so a new IP needs no frontend rebuild.

Over plain `http://`, set in `backend/.env`:

```env
DJANGO_ALLOWED_HOSTS=192.168.0.100,localhost,127.0.0.1
FRONTEND_URL=http://192.168.0.100
BACKEND_URL=http://192.168.0.100
CORS_ALLOWED_ORIGINS=http://192.168.0.100
CSRF_TRUSTED_ORIGINS=http://192.168.0.100
AUTH_COOKIE_DOMAIN=
AUTH_COOKIE_SECURE=False
SECURE_SSL_REDIRECT=False
```

`AUTH_COOKIE_SECURE` must be `False` here: the browser never stores a `Secure`
cookie over plain HTTP, so a login would not survive a page reload.
