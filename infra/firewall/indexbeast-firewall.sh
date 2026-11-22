#!/bin/sh
# Rule chống DoS cho IndexBeast trong chain DOCKER-USER (ufw không lọc cổng Docker mở). Chạy lại nhiều lần không trùng.
# Chạy bởi indexbeast-firewall.service sau docker.service. Danh sách IP chặn: /etc/indexbeast/blocked-ips (mỗi dòng một IP/CIDR).
set -eu
add() { iptables -C DOCKER-USER "$@" 2>/dev/null || iptables -I DOCKER-USER "$@"; }
# Mỗi IP tối đa ~20 kết nối mới/giây vào 80/443 (trình duyệt dùng HTTP/2, một kết nối)
add -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -m hashlimit --hashlimit-name web --hashlimit-mode srcip --hashlimit-above 20/second --hashlimit-burst 40 -j DROP
if [ -f /etc/indexbeast/blocked-ips ]; then
  grep -vE '^\s*(#|$)' /etc/indexbeast/blocked-ips | while read -r ip; do add -s "$ip" -j DROP; done
fi
