#!/usr/bin/env bash
# Cài VPS staging lần đầu (Ubuntu 24.04, chạy bằng root): Docker, user deploy, SSH chỉ bằng key, ufw, swap.
# Dùng:  sudo bash bootstrap.sh /đường/dẫn/khoa-công-khai.pub
# Chạy lại được nhiều lần. Xem docs/staging.md trước khi chạy.
# Phụ trách: TV1 · [S3] Staging trên VPS
set -euo pipefail

PUBKEY_FILE=${1:?Thiếu đường dẫn file khóa công khai SSH (.pub) của người deploy}
DEPLOY_USER=${DEPLOY_USER:-deploy}
SWAP_GB=${SWAP_GB:-2}

[ "$(id -u)" = 0 ] || { echo "Cần chạy bằng root (sudo)."; exit 1; }
grep -qE '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-)' "$PUBKEY_FILE" || {
  echo "$PUBKEY_FILE không giống khóa công khai SSH. Không dùng khóa riêng (private key)."
  exit 1
}

echo "==> 1/5 Docker (kho apt chính thức)"
if ! command -v docker >/dev/null; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg git ufw
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
apt-get install -y git ufw >/dev/null

echo "==> 2/5 User $DEPLOY_USER (không có sudo, chỉ thuộc nhóm docker)"
id "$DEPLOY_USER" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$DEPLOY_USER"
usermod -aG docker "$DEPLOY_USER"
home=$(getent passwd "$DEPLOY_USER" | cut -d: -f6)
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$home/.ssh"
touch "$home/.ssh/authorized_keys"
grep -qxF "$(cat "$PUBKEY_FILE")" "$home/.ssh/authorized_keys" || cat "$PUBKEY_FILE" >>"$home/.ssh/authorized_keys"
chown "$DEPLOY_USER:$DEPLOY_USER" "$home/.ssh/authorized_keys"
chmod 600 "$home/.ssh/authorized_keys"

echo "==> 3/5 SSH: chỉ đăng nhập bằng khóa, tắt root và mật khẩu"
cat >/etc/ssh/sshd_config.d/10-staging.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
EOF
sshd -t
systemctl reload ssh

echo "==> 4/5 Tường lửa ufw: chỉ mở 22, 80, 443"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> 5/5 Swap ${SWAP_GB} GB (build ảnh web và nạp model cần đỉnh RAM ngắn hạn)"
if ! swapon --show | grep -q .; then
  fallocate -l "${SWAP_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
  sysctl -w vm.swappiness=10 >/dev/null
  echo 'vm.swappiness=10' >/etc/sysctl.d/99-staging.conf
fi

cat <<EOF

Xong. TRƯỚC KHI đóng phiên root này, mở một cửa sổ khác và thử:
  ssh $DEPLOY_USER@<ip-vps>
Chỉ khi vào được mới đóng phiên root (nếu không sẽ tự khóa mình bên ngoài).
Docker mở cổng bằng iptables riêng và bỏ qua ufw: vì vậy compose staging chỉ công khai 80/443 (Caddy),
các cổng còn lại gắn vào 127.0.0.1. Đừng thêm "ports" công khai cho dịch vụ khác.
EOF
