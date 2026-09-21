#!/usr/bin/env bash
# VPS 侧 WireGuard 中继落地脚本（Linux）。
#
# 用途：PC 在 CGNAT 后、手机无法直连 PC 时，用一台公网 VPS 转发两者的 UDP。
# 只做转发：不跑 opc-web、不终止 HTTP，WireGuard 端到端加密，VPS 看不到明文。
#
# 用法：
#   sudo bash mobile-wg-relay.sh --conf /path/to/relay-wg0.conf
#   （relay-wg0.conf 由 opc-web 设置页「移动端接入 → 中继模式 → 导出」生成）
#
# 幂等：重复执行只覆盖 wg0.conf 并重建接口，不会重复插入 iptables 规则。

set -euo pipefail

CONF=""
IFACE="wg0"
WG_PORT="51820"

while [ $# -gt 0 ]; do
  case "$1" in
    --conf) CONF="${2:-}"; shift 2 ;;
    --iface) IFACE="${2:-}"; shift 2 ;;
    --port) WG_PORT="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

if [ -z "$CONF" ]; then
  echo "缺少 --conf（relay-wg0.conf 路径）" >&2
  exit 2
fi
if [ ! -f "$CONF" ]; then
  echo "配置文件不存在：$CONF" >&2
  exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "需要 root（会改网络配置）" >&2
  exit 2
fi
if ! command -v wg-quick >/dev/null 2>&1; then
  echo "缺少 wg-quick：apt install wireguard  /  yum install wireguard-tools" >&2
  exit 2
fi

install -d -m 700 /etc/wireguard
install -m 600 "$CONF" "/etc/wireguard/${IFACE}.conf"

# 转发必须开：中继的全部工作就是转发
if ! grep -qx 'net.ipv4.ip_forward=1' /etc/sysctl.d/99-wireguard-relay.conf 2>/dev/null; then
  echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-wireguard-relay.conf
fi
sysctl -q --system

# 接口若已存在先摘掉，保证幂等
if ip link show "$IFACE" >/dev/null 2>&1; then
  wg-quick down "$IFACE" || true
fi
wg-quick up "$IFACE"

# 放行 UDP 与转发。规则先删后加，重复执行不会堆积。
SUBNET="10.9.0.0/24"
if command -v ufw >/dev/null 2>&1; then
  ufw allow "${WG_PORT}/udp" || true
else
  iptables -C INPUT -p udp --dport "$WG_PORT" -j ACCEPT 2>/dev/null || \
    iptables -A INPUT -p udp --dport "$WG_PORT" -j ACCEPT
fi

iptables -C FORWARD -i "$IFACE" -o "$IFACE" -s "$SUBNET" -d "$SUBNET" -j ACCEPT 2>/dev/null || \
  iptables -A FORWARD -i "$IFACE" -o "$IFACE" -s "$SUBNET" -d "$SUBNET" -j ACCEPT
iptables -C FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
  iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT

# 开机自动起隧道（wg-quick 会装这个 unit，enabled 需要显式开）
systemctl enable "wg-quick@${IFACE}" >/dev/null 2>&1 || true

echo
echo "中继已就绪。"
echo "  接口：$IFACE   监听：udp/$WG_PORT   转发网段：$SUBNET"
echo "  对端状态：wg show $IFACE"
echo
echo "注意：iptables 规则在重启后会丢。持久化按发行版选一个："
echo "  Debian/Ubuntu: apt install iptables-persistent && netfilter-persistent save"
echo "  RHEL 系:       systemctl enable --now firewalld && firewall-cmd --permanent --add-port=${WG_PORT}/udp"
