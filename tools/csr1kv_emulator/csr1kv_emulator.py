#!/usr/bin/env python3
"""Эмулятор CLI маршрутизатора Cisco CSR1000v (IOS XE 16.9) для лабораторных работ.

Образ CSR1000v выдаёт только преподаватель (шаг 1 лабораторной 7.0.3), поэтому
для повторяемых прогонов в CI используется этот эмулятор. Он поднимает SSH-сервер
(paramiko) и реализует подмножество команд IOS XE, которое нужно в лабораторных
7.0.3, 7.4.7 и 7.6.3: show version, show running-config, show ip interface brief,
show ipv6 interface [brief], режим конфигурации интерфейса, IPv6-адреса и т.д.

Состояние устройства хранится в памяти: изменения, внесённые через Ansible или
вручную, сразу видны в выводе show-команд.

Запуск:  python3 csr1kv_emulator.py --host 192.168.56.101 --port 22
"""

import argparse
import datetime as dt
import hashlib
import ipaddress
import logging
import os
import secrets
import socket
import sys
import threading
import time

import paramiko

LOG = logging.getLogger("csr1kv")

BANNER = (
    "\r\n"
    "*                                           *\r\n"
    "**                                         **\r\n"
    "***                                       ***\r\n"
    "***  Cisco Networking Academy             ***\r\n"
    "***                                       ***\r\n"
    "***  This software is provided for        ***\r\n"
    "***   Educational Purposes                ***\r\n"
    "***    Only in Networking Academies       ***\r\n"
    "***                                       ***\r\n"
    "**                                         **\r\n"
    "*                                           *\r\n"
    "\r\n"
)

INVALID = "% Invalid input detected at '^' marker."
INCOMPLETE = "% Incomplete command."

CISCO_B64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def cisco_b64(data):
    """Кодирование base64 с алфавитом Cisco (как в хэшах type 8/9)."""
    bits = 0
    nbits = 0
    out = []
    for byte in data:
        bits = (bits << 8) | byte
        nbits += 8
        while nbits >= 6:
            nbits -= 6
            out.append(CISCO_B64[(bits >> nbits) & 0x3F])
    if nbits:
        out.append(CISCO_B64[(bits << (6 - nbits)) & 0x3F])
    return "".join(out)


def type9_hash(password):
    """Хэш пароля Cisco type 9 (scrypt N=16384, r=1, p=1)."""
    salt = "".join(secrets.choice(CISCO_B64) for _ in range(14))
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=1, p=1, dklen=32)
    return "$9${}${}".format(salt, cisco_b64(digest))


def fmt_uptime(seconds):
    """Формат аптайма как в IOS: '2 days, 6 hours, 26 minutes'."""
    minutes = int(seconds // 60)
    weeks, minutes = divmod(minutes, 7 * 24 * 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    parts = []
    for value, unit in ((weeks, "week"), (days, "day"), (hours, "hour")):
        if value:
            parts.append("{} {}{}".format(value, unit, "" if value == 1 else "s"))
    parts.append("{} minute{}".format(minutes, "" if minutes == 1 else "s"))
    return ", ".join(parts)


def solicited_node(addr):
    """Адрес multicast-группы solicited-node для IPv6-адреса (FF02::1:FFxx:xxxx)."""
    low24 = int(addr) & 0xFFFFFF
    return ipaddress.IPv6Address((0xFF02 << 112) | (1 << 32) | (0xFF << 24) | low24)


def v6(addr):
    return str(ipaddress.IPv6Address(addr)).upper()


class Interface(object):
    def __init__(self, name, mac, description="", ipv4=None, ipv4_mask=None, ipv4_method="DHCP"):
        self.name = name
        self.mac = mac  # строка вида 0800.2773.d79f
        self.description = description
        self.ipv4 = ipv4
        self.ipv4_mask = ipv4_mask
        self.ipv4_method = ipv4_method
        self.dhcp = ipv4_method == "DHCP"
        self.shutdown = False
        self.ipv6_global = []  # список IPv6Interface
        self.ipv6_link_local = None  # IPv6Address, если задан вручную
        self.ipv6_enable = False

    @property
    def ipv6_enabled(self):
        return bool(self.ipv6_global or self.ipv6_link_local or self.ipv6_enable)

    def eui64_link_local(self):
        raw = bytes.fromhex(self.mac.replace(".", ""))
        eui = bytes([raw[0] ^ 0x02]) + raw[1:3] + b"\xff\xfe" + raw[3:]
        return ipaddress.IPv6Address(b"\xfe\x80" + b"\x00" * 6 + eui)

    def link_local(self):
        return self.ipv6_link_local or self.eui64_link_local()

    def status(self):
        return ("administratively down", "down") if self.shutdown else ("up", "up")


class Device(object):
    def __init__(self, hostname="CSR1kv", username="cisco", password="cisco123!", ipv4="192.168.56.101",
                 serial="9K8P1OFYE3D", boot_offset=0):
        self.lock = threading.RLock()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.secret_hash = type9_hash(password)
        self.serial = serial
        self.boot_time = time.time() - boot_offset
        self.last_change = dt.datetime.utcnow().replace(microsecond=0)
        self.last_change_by = None
        self.logging_console = False
        self.interfaces = {
            "GigabitEthernet1": Interface("GigabitEthernet1", "0800.2773.d79f", "VBox", ipv4, "255.255.255.0", "DHCP"),
        }

    # ---------- вывод show-команд ----------
    def show_version(self):
        up = fmt_uptime(time.time() - self.boot_time)
        up_cp = fmt_uptime(time.time() - self.boot_time + 60)
        lines = [
            "Cisco IOS XE Software, Version 16.09.05",
            "Cisco IOS Software [Fuji], Virtual XE Software (X86_64_LINUX_IOSD-UNIVERSALK9-M), Version 16.9.5, RELEASE SOFTWARE (fc1)",
            "Technical Support: http://www.cisco.com/techsupport",
            "Copyright (c) 1986-2020 by Cisco Systems, Inc.",
            "Compiled Thu 30-Jan-20 18:48 by mcpre",
            "",
            "",
            "Cisco IOS-XE software, Copyright (c) 2005-2020 by cisco Systems, Inc.",
            "All rights reserved.  Certain components of Cisco IOS-XE software are",
            "licensed under the GNU General Public License (\"GPL\") Version 2.0.  The",
            "software code licensed under GPL Version 2.0 is free software that comes",
            "with ABSOLUTELY NO WARRANTY.  You can redistribute and/or modify such",
            "GPL code under the terms of GPL Version 2.0.  For more details, see the",
            "documentation or \"License Notice\" file accompanying the IOS-XE software,",
            "or the applicable URL provided on the flyer accompanying the IOS-XE",
            "software.",
            "",
            "",
            "ROM: IOS-XE ROMMON",
            "",
            "{} uptime is {}".format(self.hostname, up),
            "Uptime for this control processor is {}".format(up_cp),
            "System returned to ROM by reload",
            "System image file is \"bootflash:packages.conf\"",
            "Last reload reason: reload",
            "",
            "",
            "",
            "This product contains cryptographic features and is subject to United",
            "States and local country laws governing import, export, transfer and",
            "use. Delivery of Cisco cryptographic products does not imply",
            "third-party authority to import, export, distribute or use encryption.",
            "Importers, exporters, distributors and users are responsible for",
            "compliance with U.S. and local country laws. By using this product you",
            "agree to comply with applicable laws and regulations. If you are unable",
            "to comply with U.S. and local laws, return this product immediately.",
            "",
            "A summary of U.S. laws governing Cisco cryptographic products may be found at:",
            "http://www.cisco.com/wwl/export/crypto/tool/stqrg.html",
            "",
            "If you require further assistance please contact us by sending email to",
            "export@cisco.com.",
            "",
            "License Level: ax",
            "License Type: Default. No valid license found.",
            "Next reload license Level: ax",
            "",
            "",
            "Smart Licensing Status: Smart Licensing is DISABLED",
            "",
            "cisco CSR1000V (VXE) processor (revision VXE) with 2182252K/3075K bytes of memory.",
            "Processor board ID {}".format(self.serial),
            "{} Gigabit Ethernet interface".format(len(self.interfaces)),
            "32768K bytes of non-volatile configuration memory.",
            "3985032K bytes of physical memory.",
            "7774207K bytes of virtual hard disk at bootflash:.",
            "0K bytes of WebUI ODM Files at webui:.",
            "",
            "Configuration register is 0x2102",
            "",
        ]
        return "\r\n".join(lines)

    def show_ip_int_brief(self):
        out = ["{:<23}{:<16}{:<4}{:<7}{:<22}{}".format("Interface", "IP-Address", "OK?", "Method", "Status", "Protocol")]
        for name in sorted(self.interfaces):
            itf = self.interfaces[name]
            st, pr = itf.status()
            ip = itf.ipv4 or "unassigned"
            method = "DHCP" if itf.dhcp else ("manual" if itf.ipv4 else "unset")
            out.append("{:<23}{:<16}{:<4}{:<7}{:<22}{:<8}".format(name, ip, "YES", method, st, pr))
        return "\r\n".join(out)

    def show_ipv6_int_brief(self):
        out = []
        for name in sorted(self.interfaces):
            itf = self.interfaces[name]
            st, pr = itf.status()
            out.append("{:<23}[{}/{}]".format(name, "administratively down" if itf.shutdown else "up", pr))
            if itf.ipv6_enabled:
                out.append("    " + v6(itf.link_local()))
                for g in itf.ipv6_global:
                    out.append("    " + v6(g.ip))
            else:
                out.append("    unassigned")
        return "\r\n".join(out)

    def show_ipv6_interface(self, name=None):
        out = []
        names = [name] if name else sorted(self.interfaces)
        for n in names:
            itf = self.interfaces[n]
            if not itf.ipv6_enabled:
                continue
            st, pr = itf.status()
            ll = itf.link_local()
            groups = [ipaddress.IPv6Address("ff02::1")]
            groups += [solicited_node(g.ip) for g in itf.ipv6_global]
            groups.append(solicited_node(ll))
            groups = sorted(set(groups), key=int)
            out.append("{} is {}, line protocol is {}".format(n, st, pr))
            out.append("  IPv6 is enabled, link-local address is {}".format(v6(ll)))
            out.append("  No Virtual link-local address(es):")
            if itf.description:
                out.append("  Description: {}".format(itf.description))
            if itf.ipv6_global:
                out.append("  Global unicast address(es):")
                for g in itf.ipv6_global:
                    out.append("    {}, subnet is {}".format(v6(g.ip), str(g.network).upper()))
            else:
                out.append("  No global unicast address is configured")
            out.append("  Joined group address(es):")
            for grp in groups:
                out.append("    " + v6(grp))
            out += [
                "  MTU is 1500 bytes",
                "  ICMP error messages limited to one every 100 milliseconds",
                "  ICMP redirects are enabled",
                "  ICMP unreachables are sent",
                "  ND DAD is enabled, number of DAD attempts: 1",
                "  ND reachable time is 30000 milliseconds (using 30000)",
                "  ND NS retransmit interval is 1000 milliseconds",
            ]
        return "\r\n".join(out)

    def running_config_body(self):
        c = [
            "!",
            "! Last configuration change at {}{}".format(
                self.last_change.strftime("%H:%M:%S UTC %a %b %d %Y"),
                " by {}".format(self.last_change_by) if self.last_change_by else ""),
            "!",
            "version 16.9",
            "service timestamps debug datetime msec",
            "service timestamps log datetime msec",
            "platform qfp utilization monitor load 80",
            "no platform punt-keepalive disable-kernel-core",
            "platform console virtual",
            "!",
            "hostname {}".format(self.hostname),
            "!",
            "boot-start-marker",
            "boot-end-marker",
            "!",
            "!",
        ]
        if not self.logging_console:
            c.append("no logging console")
        c += [
            "!",
            "no aaa new-model",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "ip domain name example.netacad.com",
            "!",
            "!",
            "!",
            "login on-success log",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "subscriber templating",
            "! ",
            "! ",
            "! ",
            "! ",
            "!",
            "multilink bundle-name authenticated",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "license udi pid CSR1000V sn {}".format(self.serial),
            "no license smart enable",
            "diagnostic bootup level minimal",
            "!",
            "spanning-tree extend system-id",
            "!",
            "netconf-yang",
            "!",
            "restconf",
            "!",
            "username {} privilege 15 secret 9 {}".format(self.username, self.secret_hash),
            "!",
            "redundancy",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "! ",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "! ",
            "! ",
            "!",
            "!",
        ]
        for name in sorted(self.interfaces):
            itf = self.interfaces[name]
            c.append("interface {}".format(name))
            if itf.description:
                c.append(" description {}".format(itf.description))
            if itf.dhcp:
                c.append(" ip address dhcp")
            elif itf.ipv4:
                c.append(" ip address {} {}".format(itf.ipv4, itf.ipv4_mask))
            else:
                c.append(" no ip address")
            if itf.shutdown:
                c.append(" shutdown")
            c.append(" negotiation auto")
            if itf.ipv6_link_local:
                c.append(" ipv6 address {} link-local".format(v6(itf.ipv6_link_local)))
            for g in itf.ipv6_global:
                c.append(" ipv6 address {}/{}".format(v6(g.ip), g.network.prefixlen))
            if itf.ipv6_enable:
                c.append(" ipv6 enable")
            c.append(" no mop enabled")
            c.append(" no mop sysid")
            c.append("!")
        c += [
            "ip forward-protocol nd",
            "ip http server",
            "ip http authentication local",
            "ip http secure-server",
            "ip route 0.0.0.0 0.0.0.0 GigabitEthernet1 dhcp",
            "!",
            "ip ssh rsa keypair-name ssh-key",
            "ip ssh version 2",
            "ip scp server enable",
            "!",
            "!",
            "!",
            "!",
            "!",
            "control-plane",
            "!",
            "!",
            "!",
            "!",
            "!",
            "banner motd ^C",
        ]
        c += [l for l in BANNER.replace("\r", "").split("\n") if l.strip()]
        c += [
            "^C",
            "!",
            "line con 0",
            " exec-timeout 0 0",
            " logging synchronous",
            " stopbits 1",
            "line vty 0 4",
            " login local",
            " transport input ssh",
            "!",
            "!",
            "!",
            "!",
            "!",
            "!",
            "end",
        ]
        return c

    def show_running_config(self):
        body = self.running_config_body()
        size = sum(len(l) + 1 for l in body)
        return "\r\n".join(["Building configuration...", "", "Current configuration : {} bytes".format(size)] + body)

    def mark_changed(self, user):
        self.last_change = dt.datetime.utcnow().replace(microsecond=0)
        self.last_change_by = user


# ---------------- разбор команд ----------------

def match_kw(token, keywords):
    """Сопоставление сокращённого ключевого слова (как в IOS): 'sh' -> 'show'."""
    t = token.lower()
    if t in keywords:
        return t
    cands = [k for k in keywords if k.startswith(t)]
    if len(cands) == 1:
        return cands[0]
    return None


def parse_interface(tokens):
    """Разбирает имя интерфейса: 'gig 1', 'g1', 'GigabitEthernet1'. Возвращает (имя, израсходовано токенов)."""
    if not tokens:
        return None, 0
    first = tokens[0].lower()
    num = ""
    used = 1
    letters = first.rstrip("0123456789/.")
    num = first[len(letters):]
    if not num and len(tokens) > 1 and tokens[1][:1].isdigit():
        num = tokens[1]
        used = 2
    if letters and "gigabitethernet".startswith(letters) and num:
        return "GigabitEthernet" + num, used
    if letters and "loopback".startswith(letters) and len(letters) >= 2 and num:
        return "Loopback" + num, used
    return None, 0


class Session(object):
    """Одна CLI-сессия пользователя (vty)."""

    def __init__(self, device, chan, user, peer):
        self.dev = device
        self.chan = chan
        self.user = user
        self.peer = peer
        self.mode = "exec"  # exec | config | config-if | config-line
        self.cur_if = None
        self.buf = ""
        self.history = []

    def prompt(self):
        h = self.dev.hostname
        return {
            "exec": h + "#",
            "config": h + "(config)#",
            "config-if": h + "(config-if)#",
            "config-line": h + "(config-line)#",
        }[self.mode]

    def send(self, text):
        try:
            self.chan.sendall(text.encode("utf-8"))
        except Exception:
            pass

    def run(self):
        self.send(BANNER)
        self.send("\r\n" + self.prompt())
        prev = b""
        while True:
            try:
                data = self.chan.recv(4096)
            except Exception:
                break
            if not data:
                break
            for ch in data:
                c = bytes([ch])
                if c in (b"\r", b"\n"):
                    if c == b"\n" and prev == b"\r":
                        prev = c
                        continue
                    line = self.buf
                    self.buf = ""
                    self.send("\r\n")
                    keep = self.execute(line)
                    if not keep:
                        try:
                            self.chan.send_exit_status(0)
                        except Exception:
                            pass
                        self.close()
                        return
                    self.send(self.prompt())
                elif c in (b"\x7f", b"\x08"):
                    if self.buf:
                        self.buf = self.buf[:-1]
                        self.send("\b \b")
                elif c == b"\x1a":  # Ctrl+Z
                    self.buf = ""
                    if self.mode != "exec":
                        self.mode = "exec"
                        self.cur_if = None
                    self.send("^Z\r\n" + self.prompt())
                elif c == b"\x03":  # Ctrl+C
                    self.buf = ""
                    self.send("^C\r\n" + self.prompt())
                elif c == b"\x15":  # Ctrl+U
                    self.send("\b \b" * len(self.buf))
                    self.buf = ""
                elif ch >= 32 and ch < 127:
                    self.buf += c.decode()
                    self.send(c.decode())
                prev = c

    def close(self):
        try:
            self.chan.close()
        except Exception:
            pass

    def out(self, text):
        if text and self.pipe:
            text = self.apply_pipe(text)
        if text:
            self.send(text.replace("\r\n", "\n").replace("\n", "\r\n") + "\r\n")

    pipe = None

    def apply_pipe(self, text):
        """Фильтры вывода IOS: | include, | exclude, | begin, | section."""
        import re as _re
        lines = text.replace("\r\n", "\n").split("\n")
        for kind, expr in self.pipe:
            try:
                rx = _re.compile(expr)
            except _re.error:
                rx = _re.compile(_re.escape(expr))
            if kind == "include":
                lines = [l for l in lines if rx.search(l)]
            elif kind == "exclude":
                lines = [l for l in lines if not rx.search(l)]
            elif kind == "begin":
                for i, l in enumerate(lines):
                    if rx.search(l):
                        lines = lines[i:]
                        break
                else:
                    lines = []
            elif kind == "section":
                res, keep = [], False
                for l in lines:
                    if l and not l.startswith(" "):
                        keep = bool(rx.search(l))
                    if keep:
                        res.append(l)
                lines = res
        return "\n".join(lines)

    def invalid(self, line, pos=0):
        caret = " " * (len(self.prompt()) + pos) + "^"
        self.out(caret + "\r\n" + INVALID)

    # ---- выполнение строки ----
    def execute(self, line):
        raw = line
        line = line.strip()
        if not line or line.startswith("!"):
            return True
        LOG.info("[%s %s] %s: %s", self.peer, self.user, self.mode, line)
        self.history.append(line)
        self.pipe = None
        if "|" in line:
            # как в IOS: один фильтр, всё после ключевого слова считается регулярным выражением
            head, _, rest = line.partition("|")
            words = rest.strip().split(None, 1)
            kind = match_kw(words[0], ["include", "exclude", "begin", "section"]) if len(words) == 2 else None
            if not kind:
                self.invalid(raw, raw.find("|") + 2)
                return True
            self.pipe = [(kind, words[1].strip())]
            line = head.strip()
            raw = head
        tokens = line.split()
        with self.dev.lock:
            if self.mode == "exec":
                return self.exec_cmd(tokens, raw)
            if tokens[0].lower() == "do" and len(tokens) > 1:
                return self.exec_cmd(tokens[1:], raw, from_config=True)
            if match_kw(tokens[0], ["end"]) == "end" and len(tokens) == 1:
                self.mode = "exec"
                self.cur_if = None
                self.dev.mark_changed(self.user)
                return True
            if match_kw(tokens[0], ["exit"]) == "exit" and len(tokens) == 1:
                if self.mode in ("config-if", "config-line"):
                    self.mode = "config"
                    self.cur_if = None
                else:
                    self.mode = "exec"
                    self.dev.mark_changed(self.user)
                return True
            if self.mode == "config":
                return self.global_cfg(tokens, raw)
            if self.mode == "config-if":
                ok = self.if_cfg(tokens, raw)
                if ok is None:
                    # IOS позволяет вводить глобальные команды из подрежима
                    return self.global_cfg(tokens, raw)
                return ok
            if self.mode == "config-line":
                ok = self.line_cfg(tokens, raw)
                if ok is None:
                    return self.global_cfg(tokens, raw)
                return ok
        return True

    def exec_cmd(self, t, raw, from_config=False):
        kw = match_kw(t[0], ["show", "configure", "terminal", "exit", "logout", "quit", "write", "copy", "ping",
                             "enable", "disable", "end", "clock"])
        if kw is None:
            self.invalid(raw)
            return True
        if kw in ("exit", "logout", "quit") and not from_config:
            return False
        if kw in ("enable", "end"):
            return True
        if kw == "terminal":
            if len(t) >= 2 and match_kw(t[1], ["length", "width", "monitor", "no"]):
                return True
            self.out(INCOMPLETE)
            return True
        if kw == "configure":
            if len(t) == 1 or match_kw(t[1], ["terminal"]) == "terminal":
                self.out("Enter configuration commands, one per line.  End with CNTL/Z.")
                self.mode = "config"
                return True
            self.invalid(raw)
            return True
        if kw == "write":
            if len(t) == 1 or match_kw(t[1], ["memory"]):
                self.out("Building configuration...\r\n[OK]")
                return True
            self.invalid(raw)
            return True
        if kw == "ping":
            self.out("Type escape sequence to abort.\r\nSending 5, 100-byte ICMP Echos to {}, timeout is 2 seconds:\r\n!!!!!\r\n"
                     "Success rate is 100 percent (5/5), round-trip min/avg/max = 1/1/2 ms".format(t[1] if len(t) > 1 else "?"))
            return True
        if kw == "show":
            return self.show(t[1:], raw)
        self.invalid(raw)
        return True

    def show(self, t, raw):
        if not t:
            self.out(INCOMPLETE)
            return True
        kw = match_kw(t[0], ["version", "running-config", "ip", "ipv6", "interfaces", "clock", "privilege",
                             "users", "startup-config", "history", "hostname"])
        if kw == "version":
            self.out(self.dev.show_version())
        elif kw in ("running-config", "startup-config"):
            self.out(self.dev.show_running_config())
        elif kw == "privilege":
            self.out("Current privilege level is 15")
        elif kw == "clock":
            self.out(dt.datetime.utcnow().strftime("*%H:%M:%S.%f")[:-3] + dt.datetime.utcnow().strftime(" UTC %a %b %d %Y"))
        elif kw == "history":
            self.out("\r\n".join("  " + h for h in self.history[-20:]))
        elif kw == "users":
            self.out("    Line       User       Host(s)              Idle       Location\r\n"
                     "*  1 vty 0     {:<10} idle                 00:00:00 {}".format(self.user, self.peer))
        elif kw == "ip":
            if len(t) >= 3 and match_kw(t[1], ["interface"]) and match_kw(t[2], ["brief"]):
                self.out(self.dev.show_ip_int_brief())
            else:
                self.invalid(raw)
        elif kw == "ipv6":
            if len(t) >= 2 and match_kw(t[1], ["interface"]) == "interface":
                rest = t[2:]
                if rest and match_kw(rest[0], ["brief"]) == "brief":
                    self.out(self.dev.show_ipv6_int_brief())
                elif rest:
                    name, used = parse_interface(rest)
                    if name and name in self.dev.interfaces:
                        self.out(self.dev.show_ipv6_interface(name))
                    else:
                        self.invalid(raw)
                else:
                    self.out(self.dev.show_ipv6_interface())
            else:
                self.invalid(raw)
        else:
            self.invalid(raw, max(0, raw.find(t[0])))
        return True

    def global_cfg(self, t, raw):
        kw = match_kw(t[0], ["interface", "hostname", "line", "no", "logging", "ip", "ipv6", "username",
                             "service", "banner"])
        if kw == "interface":
            name, used = parse_interface(t[1:])
            if not name:
                self.invalid(raw)
                return True
            if name not in self.dev.interfaces:
                if name.startswith("Loopback"):
                    self.dev.interfaces[name] = Interface(name, "0000.0000.0000", "", None, None, "unset")
                    self.dev.interfaces[name].dhcp = False
                else:
                    self.invalid(raw)
                    return True
            self.mode = "config-if"
            self.cur_if = name
            return True
        if kw == "hostname" and len(t) == 2:
            self.dev.hostname = t[1]
            return True
        if kw == "line":
            self.mode = "config-line"
            return True
        if kw == "no" and len(t) >= 2 and match_kw(t[1], ["logging"]) == "logging":
            self.dev.logging_console = False
            return True
        if kw == "logging":
            if len(t) >= 2 and match_kw(t[1], ["console"]):
                self.dev.logging_console = True
            return True
        if kw in ("ip", "ipv6", "service", "username", "banner", "no"):
            return True  # принимается без изменения модели
        self.invalid(raw)
        return True

    def if_cfg(self, t, raw):
        itf = self.dev.interfaces[self.cur_if]
        neg = False
        if t[0].lower() == "no":
            neg = True
            t = t[1:]
            if not t:
                self.out(INCOMPLETE)
                return True
        kw = match_kw(t[0], ["description", "ip", "ipv6", "shutdown", "negotiation", "mop", "duplex", "speed"])
        if kw is None:
            return None
        if kw == "description":
            text = raw.strip().split(None, 2 if neg else 1)
            itf.description = "" if neg else (text[1] if len(text) > 1 else "")
            return True
        if kw == "shutdown":
            itf.shutdown = not neg
            return True
        if kw in ("negotiation", "mop", "duplex", "speed"):
            return True
        if kw == "ip":
            if len(t) >= 2 and match_kw(t[1], ["address"]) == "address":
                if neg:
                    itf.ipv4 = None
                    itf.dhcp = False
                    return True
                if len(t) == 3 and match_kw(t[2], ["dhcp"]) == "dhcp":
                    itf.dhcp = True
                    return True
                if len(t) == 4:
                    try:
                        ipaddress.IPv4Address(t[2])
                        ipaddress.IPv4Network("0.0.0.0/" + t[3])
                    except ValueError:
                        self.invalid(raw)
                        return True
                    itf.ipv4, itf.ipv4_mask, itf.dhcp = t[2], t[3], False
                    return True
            self.invalid(raw)
            return True
        if kw == "ipv6":
            if len(t) >= 2 and match_kw(t[1], ["enable"]) == "enable":
                itf.ipv6_enable = not neg
                return True
            if len(t) >= 2 and match_kw(t[1], ["address"]) == "address":
                if neg and len(t) == 2:
                    itf.ipv6_global = []
                    itf.ipv6_link_local = None
                    return True
                if len(t) >= 3:
                    addr = t[2]
                    if len(t) == 4 and match_kw(t[3], ["link-local"]) == "link-local":
                        try:
                            ll = ipaddress.IPv6Address(addr)
                        except ValueError:
                            self.invalid(raw)
                            return True
                        if not ll.is_link_local:
                            self.out("% {} is not a valid link-local address".format(addr.upper()))
                            return True
                        itf.ipv6_link_local = None if neg else ll
                        return True
                    try:
                        net = ipaddress.IPv6Interface(addr)
                    except ValueError:
                        self.invalid(raw)
                        return True
                    if "/" not in addr:
                        self.out(INCOMPLETE)
                        return True
                    itf.ipv6_global = [g for g in itf.ipv6_global if g.ip != net.ip]
                    if not neg:
                        itf.ipv6_global.append(net)
                    return True
            self.invalid(raw)
            return True
        return None

    def line_cfg(self, t, raw):
        kw = match_kw(t[0], ["exec-timeout", "logging", "login", "transport", "stopbits", "privilege", "password", "no"])
        if kw is None:
            return None
        return True


class SshServer(paramiko.ServerInterface):
    def __init__(self, device):
        self.dev = device
        self.shell_event = threading.Event()
        self.user = None

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username):
        return "keyboard-interactive,password"

    def check_auth_password(self, username, password):
        if username == self.dev.username and password == self.dev.password:
            self.user = username
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_interactive(self, username, submethods):
        self._ki_user = username
        return paramiko.server.InteractiveQuery("", "", ("Password: ", False))

    def check_auth_interactive_response(self, responses):
        if getattr(self, "_ki_user", None) == self.dev.username and responses and responses[0] == self.dev.password:
            self.user = self._ki_user
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True

    def check_channel_shell_request(self, channel):
        self.shell_event.set()
        return True

    def check_channel_exec_request(self, channel, command):
        self.exec_command = command.decode() if isinstance(command, bytes) else command
        self.shell_event.set()
        return True


def handle_client(sock, addr, device, host_key):
    peer = addr[0]
    transport = paramiko.Transport(sock)
    transport.local_version = "SSH-2.0-Cisco-1.25"
    transport.add_server_key(host_key)
    server = SshServer(device)
    try:
        transport.start_server(server=server)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("SSH negotiation failed from %s: %s", peer, exc)
        return
    chan = transport.accept(30)
    if chan is None:
        transport.close()
        return
    server.shell_event.wait(15)
    LOG.info("session opened: %s from %s", server.user, peer)
    sess = Session(device, chan, server.user or "cisco", peer)
    cmd = getattr(server, "exec_command", None)
    if cmd:
        sess.execute(cmd)
        chan.send_exit_status(0)
        chan.close()
    else:
        sess.run()
    time.sleep(0.2)
    transport.close()
    LOG.info("session closed: %s", peer)


def main():
    ap = argparse.ArgumentParser(description="CSR1000v IOS XE CLI emulator (SSH)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=22)
    ap.add_argument("--hostname", default="CSR1kv")
    ap.add_argument("--username", default="cisco")
    ap.add_argument("--password", default=os.environ.get("CSR_PASSWORD", "cisco123!"))
    ap.add_argument("--ipv4", default="192.168.56.101", help="адрес GigabitEthernet1 в show-командах")
    ap.add_argument("--host-key", default=None, help="файл RSA-ключа хоста (создаётся при отсутствии)")
    ap.add_argument("--boot-offset", type=int, default=0, help="сколько секунд устройство 'уже работает'")
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    handlers = [logging.StreamHandler(sys.stdout)]
    if args.log:
        handlers.append(logging.FileHandler(args.log))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", handlers=handlers)
    # проверки доступности порта без SSH-рукопожатия не должны засорять журнал
    logging.getLogger("paramiko").setLevel(logging.CRITICAL)

    if args.host_key and os.path.exists(args.host_key):
        host_key = paramiko.RSAKey(filename=args.host_key)
    else:
        host_key = paramiko.RSAKey.generate(2048)
        if args.host_key:
            host_key.write_private_key_file(args.host_key)

    device = Device(args.hostname, args.username, args.password, args.ipv4, boot_offset=args.boot_offset)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(20)
    LOG.info("CSR1kv emulator listening on %s:%d", args.host, args.port)
    while True:
        sock, addr = srv.accept()
        threading.Thread(target=handle_client, args=(sock, addr, device, host_key), daemon=True).start()


if __name__ == "__main__":
    main()
