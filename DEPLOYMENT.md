# Production Deployment Guide — Nutrient: The Super Food

This guide covers deploying **Nutrient – The Super Food** (`food_delivery`) to production platforms including **Render**, **Railway**, and standard **Linux VPS (Ubuntu / Nginx / Gunicorn / Systemd)**.

---

## Architecture Overview

- **Framework**: Django 5.1 LTS (Python 3.13)
- **WSGI Server**: Gunicorn 26.x
- **Static Assets Serving**: WhiteNoise 6.12 (`CompressedManifestStaticFilesStorage` with Brotli/gzip compression and far-future HTTP cache headers)
- **Database Support**:
  - Cloud managed MySQL or PostgreSQL via `DATABASE_URL` (`dj-database-url`)
  - Local/dedicated MySQL 8.x via PyMySQL wrapper
  - Zero-config SQLite fallback (`USE_SQLITE=True`)
- **Security Hardening**:
  - HSTS (1-year duration with subdomains and preload)
  - Strict HTTPS redirection (`SECURE_SSL_REDIRECT=True`)
  - Secure and HttpOnly cookies (`SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`)
  - Clickjacking protection (`X_FRAME_OPTIONS='DENY'`)
  - Automated `CSRF_TRUSTED_ORIGINS` resolution for cloud PaaS subdomains

---

## Environment Variables Reference

| Variable | Default (Dev) | Production Recommendation | Description |
| :--- | :--- | :--- | :--- |
| `DEBUG` | `True` | `False` | **CRITICAL**: Must be `False` in production. |
| `SECRET_KEY` | Dev fallback | Strong 50+ random characters | Cryptographic signing key. |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | `yourdomain.com,.onrender.com` | Comma-separated list of allowed hostnames. |
| `CSRF_TRUSTED_ORIGINS` | Auto-derived from `ALLOWED_HOSTS` | `https://yourdomain.com,https://*.onrender.com` | Comma-separated HTTPS origins permitted to POST. |
| `DATABASE_URL` | None | `mysql://user:pass@host:3306/dbname` or `postgres://...` | Connection URI parsed by `dj-database-url`. |
| `USE_SQLITE` | `False` | `False` (or `True` for simple demo instances) | Forces SQLite backend if set to `True`. |
| `SECURE_SSL_REDIRECT` | `False` (when `DEBUG=True`) | `True` | Redirects all HTTP traffic to HTTPS. |
| `SECURE_HSTS_SECONDS` | None | `31536000` (1 year) | Enforces HTTP Strict Transport Security. |
| `RESTAURANT_NAME` | `Nutrient – The Super Food` | `Nutrient – The Super Food` | Restaurant brand display name. |
| `RESTAURANT_LOCATION` | `Hyderabad, Telangana, India` | `Hyderabad, Telangana, India` | Restaurant operational city/address. |
| `RESTAURANT_PHONE` | `+91 7993476624` | `+91 7993476624` | Customer support & contact phone number. |

---

## Option 1: One-Click Deploy on Render

### Using Render Blueprint (`render.yaml`)

1. Push your repository to GitHub or GitLab.
2. In the [Render Dashboard](https://dashboard.render.com/), select **New** > **Blueprint**.
3. Connect your repository. Render automatically reads [`render.yaml`](render.yaml):
   - Provisions a Web Service running `gunicorn food_delivery.wsgi:application --bind 0.0.0.0:$PORT`.
   - Provisions a managed database and injects `DATABASE_URL`.
   - Runs [`build.sh`](build.sh) which runs `pip install`, `collectstatic`, `migrate`, and `seed_nutrient_data`.
4. Click **Apply**. Your platform will be live at `https://nutrient-food-delivery.onrender.com` in 2-3 minutes.

### Manual Render Setup

1. **Create Database**:
   - Create a PostgreSQL or MySQL instance in Render.
   - Copy the **Internal Database URL**.
2. **Create Web Service**:
   - Connect repository, choose **Python 3** environment.
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn food_delivery.wsgi:application --bind 0.0.0.0:$PORT`
   - **Environment Variables**:
     - `PYTHON_VERSION`: `3.13.7`
     - `DEBUG`: `False`
     - `SECRET_KEY`: `<Generate secure 50+ char random string>`
     - `ALLOWED_HOSTS`: `.onrender.com,yourdomain.com`
     - `DATABASE_URL`: `<Internal Database URL from Step 1>`
     - `USE_SQLITE`: `False`

---

## Option 2: Deploy on Railway

1. Install the Railway CLI or connect via the [Railway Dashboard](https://railway.app/).
2. Create a new project and connect your GitHub repository.
3. Railway automatically detects `Procfile` and [`railway.json`](railway.json):
   - Builder: Nixpacks with Python 3.13.
   - Build Command: `./build.sh`
   - Start Command: `gunicorn food_delivery.wsgi:application --bind 0.0.0.0:$PORT`
4. In the Railway Dashboard:
   - Click **+ New** > **Database** > **Add MySQL** (or PostgreSQL).
   - In your web service settings, add environment variables:
     - `DATABASE_URL`: `${{ MySQL.DATABASE_URL }}`
     - `DEBUG`: `False`
     - `SECRET_KEY`: `<Generate secure random string>`
     - `ALLOWED_HOSTS`: `.railway.app,.up.railway.app,yourdomain.com`
5. Deploy. Railway executes migrations and seeds the database automatically via `build.sh`.

---

## Option 3: Production VPS Deployment (Ubuntu 22.04 / 24.04 LTS)

### 1. Install System Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev nginx pkg-config libmysqlclient-dev
```

### 2. Clone & Setup Workspace
```bash
cd /var/www
git clone <your-repo-url> nutrient
cd /var/www/nutrient
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Production `.env`
```bash
cat <<EOF > /var/www/nutrient/.env
DEBUG=False
SECRET_KEY=$(openssl rand -hex 32)
ALLOWED_HOSTS=nutrient.yourdomain.com,www.nutrient.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://nutrient.yourdomain.com,https://www.nutrient.yourdomain.com
DB_NAME=nutrient_production
DB_USER=nutrient_user
DB_PASSWORD=StrongPasswordHere@2026
DB_HOST=127.0.0.1
DB_PORT=3306
USE_SQLITE=False
SECURE_SSL_REDIRECT=True
EOF
```

### 4. Build, Migrate & Seed
```bash
./build.sh
```

### 5. Configure Systemd Service
Create `/etc/systemd/system/nutrient.service`:
```ini
[Unit]
Description=Nutrient – The Super Food Gunicorn Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/nutrient
ExecStart=/var/www/nutrient/venv/bin/gunicorn \
          --workers 3 \
          --bind unix:/var/www/nutrient/nutrient.sock \
          --access-logfile /var/log/nutrient_access.log \
          --error-logfile /var/log/nutrient_error.log \
          food_delivery.wsgi:application

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nutrient
```

### 6. Configure Nginx Reverse Proxy
Create `/etc/nginx/sites-available/nutrient`:
```nginx
server {
    server_name nutrient.yourdomain.com;

    client_max_body_size 20M;

    # Media files (food photography & banner uploads)
    location /media/ {
        alias /var/www/nutrient/media/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Static files served directly by Nginx or fall back to WhiteNoise
    location /static/ {
        alias /var/www/nutrient/staticfiles/;
        expires 365d;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    # Gunicorn WSGI pass-through
    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/nutrient/nutrient.sock;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Enable the site and obtain Let's Encrypt SSL certificate:
```bash
sudo ln -s /etc/nginx/sites-available/nutrient /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo certbot --nginx -d nutrient.yourdomain.com
```

---

## Media Files & User Uploads Strategy

On ephemeral PaaS containers (such as Render or Railway free tiers), files uploaded to the local filesystem are discarded upon dyno restart.
For production deployments handling user uploads:
1. **Render Persistent Disk**: Attach a persistent disk mounted to `/var/data` and point `MEDIA_ROOT = '/var/data/media'` in `settings.py`.
2. **Object Storage (Recommended for High Traffic)**: Use AWS S3 or Cloudinary with `django-storages`:
   ```python
   # In settings.py (optional Cloudinary / S3 integration)
   # pip install django-storages boto3
   DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
   AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
   ```

---

## Default Seeded Credentials

When deployed, the database initializes with the following default accounts (Password: `Nutrient@2026`):

- **Head Chef & Operations Admin**: `admin` / `Nutrient@2026`
- **Delivery Partner 1**: `rider_rajesh` / `Nutrient@2026`
- **Delivery Partner 2**: `rider_vikram` / `Nutrient@2026`
- **Customer 1**: `ananya_sharma` / `Nutrient@2026`
- **Customer 2**: `rohit_verma` / `Nutrient@2026`

**Active Promotional Codes**:
- `CLEAN20`: 20% OFF up to ₹80 (Min ₹200)
- `HIGHPROTEIN`: Flat ₹50 OFF (Min ₹300)
- `NUTRIENT10`: 10% OFF up to ₹50 (Min ₹199)

---

## Pre-Launch Verification Checklist

- [x] Gunicorn WSGI configuration validated (`gunicorn --check-config`).
- [x] WhiteNoise asset compression and manifest digest generation validated (`collectstatic`).
- [x] Dynamic `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` configured.
- [x] Security deployment check passed (`manage.py check --deploy`).
- [x] All 54 automated unit tests passing across all 7 platform applications.
- [x] Idempotent seed data script verified for automated container bootstrap.
