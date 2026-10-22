#!/usr/bin/env bash
# One-time server setup for Amazon Linux 2023 (run as ec2-user, with sudo available).
# Installs: nginx, Node 20, Python 3.12 + uv, ffmpeg (static build), ImageMagick, Playwright Chromium deps,
# certbot; creates 4 GB swap (needed on small instances) and the sketchboard systemd service.
set -euo pipefail
APP=/opt/sketchboard
DOMAIN=${DOMAIN:-yuvin-svg-app.yuverse.co.in}

sudo dnf -y update -q
sudo dnf -y install -q nginx git ImageMagick nodejs20 python3.12 tar xz \
  atk cups-libs libXcomposite libXdamage libXrandr mesa-libgbm pango alsa-lib nss libdrm libxkbcommon at-spi2-atk libXfixes libxshmfence
sudo alternatives --install /usr/bin/node node /usr/bin/node-20 90 2>/dev/null || true
sudo alternatives --install /usr/bin/npm npm /usr/bin/npm-20 90 2>/dev/null || true
sudo alternatives --install /usr/bin/npx npx /usr/bin/npx-20 90 2>/dev/null || true

# ffmpeg static build (not packaged on AL2023)
if ! command -v ffmpeg >/dev/null; then
  curl -sL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | sudo tar -xJ -C /opt
  sudo ln -sf /opt/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg
  sudo ln -sf /opt/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe
fi

# swap: Chromium + ffmpeg need headroom on 1-2 GB instances
if ! swapon --show | grep -q swapfile; then
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

sudo mkdir -p $APP && sudo chown ec2-user:ec2-user $APP
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
export PATH=$HOME/.local/bin:$PATH

# python venv + deps, node deps + Chromium (after code is synced by deploy.sh; safe to re-run)
if [ -f $APP/backend/requirements.txt ]; then
  cd $APP/backend && uv venv .venv -p 3.12 -q && uv pip install -q -p .venv/bin/python -r requirements.txt
  cd $APP && npm ci --omit=dev --silent && npm exec --yes playwright -- install chromium >/dev/null
fi

# certbot in its own venv
if [ ! -x /opt/certbot/bin/certbot ]; then
  sudo python3.12 -m venv /opt/certbot && sudo /opt/certbot/bin/pip install -q certbot certbot-nginx
  sudo ln -sf /opt/certbot/bin/certbot /usr/local/bin/certbot
fi

sudo cp $APP/deploy/sketchboard.service /etc/systemd/system/sketchboard.service
sudo sed "s/__DOMAIN__/$DOMAIN/g" $APP/deploy/nginx.conf | sudo tee /etc/nginx/conf.d/sketchboard.conf >/dev/null
sudo rm -f /etc/nginx/conf.d/default.conf
sudo systemctl daemon-reload
sudo systemctl enable --now nginx sketchboard
sudo nginx -t && sudo systemctl reload nginx
echo "Base install done. Run:  sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m you@example.com --redirect"
