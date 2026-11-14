#!/bin/sh
# Скрипт для busybox udhcpc на ПК стенда (аналог IP Configuration > DHCP в Packet Tracer).
# udhcpc вызывает его с аргументом deconfig | bound | renew | leasefail | nak и передаёт
# параметры аренды в переменных окружения: interface ip subnet mask router dns lease serverid.
# Адрес и маршрут назначаются интерфейсу в текущем сетевом пространстве имён,
# DNS-серверы записываются в /etc/netns/<ПК>/resolv.conf (resolv.conf этого ПК).

ns="$(ip netns identify 2>/dev/null)"

mask2prefix() {
    n=0
    for octet in $(echo "$1" | tr '.' ' '); do
        case "$octet" in
            255) n=$((n + 8)) ;; 254) n=$((n + 7)) ;; 252) n=$((n + 6)) ;;
            248) n=$((n + 5)) ;; 240) n=$((n + 4)) ;; 224) n=$((n + 3)) ;;
            192) n=$((n + 2)) ;; 128) n=$((n + 1)) ;;
        esac
    done
    echo "$n"
}

case "$1" in
    deconfig)
        ip link set "$interface" up
        ip -4 addr flush dev "$interface"
        ;;
    bound|renew)
        prefix="${mask:-$(mask2prefix "$subnet")}"
        ip -4 addr flush dev "$interface"
        ip addr add "$ip/$prefix" dev "$interface"
        if [ -n "$router" ]; then
            ip route replace default via "${router%% *}" dev "$interface"
        fi
        if [ -n "$ns" ] && [ -d "/etc/netns/$ns" ]; then
            {
                [ -n "$domain" ] && echo "search $domain"
                for server in $dns; do echo "nameserver $server"; done
            } > "/etc/netns/$ns/resolv.conf"
        fi
        echo "$ns: $1 IP $ip/$prefix (mask $subnet), gateway ${router:-none}, DNS ${dns:-none}," \
             "lease ${lease:-?} s from DHCP server ${serverid:-?}"
        ;;
    leasefail|nak)
        echo "$ns: DHCP $1 ${message:-}" >&2
        ;;
esac
exit 0
