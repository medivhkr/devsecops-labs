#!/usr/bin/env python3
"""Эмулятор коммутатора S2 (Catalyst 2960) для лабораторной 5.5.7.

Построен на эмуляторе IOS из репозитория (tools/csr1kv_emulator/csr1kv_emulator.py):
используются его классы Device/Session/SshServer, а здесь добавлено то, что нужно
в частях 3 и 4 методички:

  * режим пользователя "S2>" и команда enable с паролем (enable secret);
  * консоль (аналог вкладки CLI в Packet Tracer): Unix-сокет, к которому
    подключается клиент pt-console;
  * порт 23 принимает соединение и сразу закрывает его, как IOS при
    "transport input ssh" (Telnet запрещён, разрешён только SSH);
  * ntp server <адрес>: настоящий NTP-клиент (RFC 5905, режим 3) опрашивает
    сервер по UDP/123; часы устройства устанавливаются по первому корректному
    ответу (упрощение в духе SNTP, реальный IOS синхронизируется за минуты);
  * show clock [detail], show ntp associations, show ntp status.

До синхронизации часы идут от "аппаратного календаря": как у коммутатора без
батарейки, отсчёт начинается с 00:00 UTC 1 марта 1993 года в момент запуска.

Запуск (в пространстве имён S2):
  python3 s2_switch.py --host 192.168.1.4 --hostname S2 --username administrator \
      --password cisco --enable-secret cisco --console /run/labnet/S2-console.sock
"""

import argparse
import calendar
import datetime as dt
import logging
import os
import socket
import struct
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (HERE, os.path.join(HERE, "..", "..", "..", "tools", "csr1kv_emulator")):
    if os.path.exists(os.path.join(_cand, "csr1kv_emulator.py")):
        sys.path.insert(0, os.path.abspath(_cand))
        break

import csr1kv_emulator as base  # noqa: E402
import paramiko  # noqa: E402

LOG = logging.getLogger("s2")

NTP_DELTA = 2208988800  # секунд между 1900-01-01 (эпоха NTP) и 1970-01-01 (эпоха Unix)
HW_CALENDAR_START = calendar.timegm((1993, 3, 1, 0, 0, 0))
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def ntp_ts(hi, lo):
    """64-битная метка времени NTP -> секунды эпохи Unix (float)."""
    return hi - NTP_DELTA + lo / 4294967296.0


def ntp_query(server, source=None, timeout=2.0, port=123):
    """Один обмен NTP (клиент, режим 3). Возвращает словарь с параметрами ответа."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        if source:
            try:
                sock.bind((source, 0))
            except OSError:
                pass
        t1 = time.time()
        sec = int(t1) + NTP_DELTA
        frac = int((t1 - int(t1)) * 4294967296.0) & 0xFFFFFFFF
        # LI=0, VN=4, Mode=3; stratum 0; poll 6 (64 c); precision -20; далее 11 слов
        pkt = struct.pack("!BBbb11I", (0 << 6) | (4 << 3) | 3, 0, 6, -20,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, sec, frac)
        sock.sendto(pkt, (server, port))
        while True:
            data, addr = sock.recvfrom(1024)
            if addr[0] == server:
                break
        t4 = time.time()
    finally:
        sock.close()
    if len(data) < 48:
        raise ValueError("short NTP packet ({} bytes)".format(len(data)))
    f = struct.unpack("!BBbb11I", data[:48])
    li, mode, stratum = f[0] >> 6, f[0] & 7, f[1]
    if mode != 4:
        raise ValueError("not a server reply (mode {})".format(mode))
    if (f[9], f[10]) != (sec, frac):
        raise ValueError("origin timestamp mismatch")
    if li == 3 or not 1 <= stratum <= 15:
        raise ValueError("server is not synchronized (LI={}, stratum={})".format(li, stratum))
    if f[13] == 0 and f[14] == 0:
        raise ValueError("zero transmit timestamp")
    t2 = ntp_ts(f[11], f[12])
    t3 = ntp_ts(f[13], f[14])
    if stratum == 1:
        refid = "." + struct.pack("!I", f[6]).rstrip(b"\0").decode("ascii", "replace") + "."
    else:
        refid = socket.inet_ntoa(struct.pack("!I", f[6]))
    return {
        "stratum": stratum,
        "refid": refid,
        "offset": ((t2 - t1) + (t3 - t4)) / 2.0,
        "delay": (t4 - t1) - (t3 - t2),
        "disp": (f[5] >> 16) + (f[5] & 0xFFFF) / 65536.0,
        "poll": f[2],
    }


class NtpAssociation(object):
    """Сопоставление с NTP-сервером (ntp server X) и поток опроса."""

    def __init__(self, dev, server):
        self.dev = dev
        self.server = server
        self.stop = threading.Event()
        self.reach = 0
        self.poll = 64
        self.last_rx = None
        self.stratum = 16
        self.refid = ".INIT."
        self.offset = self.delay = self.disp = 0.0
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop.is_set():
            ok = False
            try:
                res = ntp_query(self.server, self.dev.mgmt_ip)
                ok = True
            except Exception as exc:  # noqa: BLE001
                LOG.info("NTP %s: no valid reply (%s)", self.server, exc)
            with self.dev.lock:
                if self.stop.is_set():
                    break
                self.reach = ((self.reach << 1) | (1 if ok else 0)) & 0xFF
                if ok:
                    self.stratum, self.refid = res["stratum"], res["refid"]
                    self.offset, self.delay, self.disp = res["offset"], res["delay"], res["disp"]
                    self.last_rx = time.monotonic()
                    first = self.dev.ntp_peer is not self
                    self.dev.set_clock(time.time() + res["offset"], "NTP")
                    self.dev.ntp_peer = self
                    if first:
                        LOG.info("NTP: clock synchronized to %s (stratum %d, refid %s, offset %.3f ms, "
                                 "delay %.3f ms)", self.server, self.stratum, self.refid,
                                 self.offset * 1000, self.delay * 1000)
            # до первого ответа - повтор каждые 2 с, затем обычный интервал опроса 64 с
            self.stop.wait(self.poll if self.last_rx is not None else 2)


class Switch(base.Device):
    def __init__(self, hostname, username, password, enable_secret, mgmt_ip):
        base.Device.__init__(self, hostname=hostname, username=username, password=password, ipv4=mgmt_ip)
        self.enable_secret = enable_secret
        self.mgmt_ip = mgmt_ip
        self.clock_mono = time.monotonic()
        self.clock_base = float(HW_CALENDAR_START)
        self.time_source = "hardware calendar"
        self.ntp_assocs = {}
        self.ntp_peer = None

    def now(self):
        with self.lock:
            return self.clock_base + (time.monotonic() - self.clock_mono)

    def set_clock(self, value, source):
        with self.lock:
            self.clock_mono = time.monotonic()
            self.clock_base = value
            self.time_source = source

    def ntp_server(self, server, remove=False):
        with self.lock:
            assoc = self.ntp_assocs.pop(server, None)
            if assoc:
                assoc.stop.set()
                if self.ntp_peer is assoc:
                    self.ntp_peer = None
            if not remove:
                assoc = NtpAssociation(self, server)
                self.ntp_assocs[server] = assoc
                assoc.thread.start()
                LOG.info("ntp server %s configured", server)

    def show_clock(self, detail=False):
        now = self.now()
        d = dt.datetime.fromtimestamp(now, dt.timezone.utc)
        ms = int((now - int(now)) * 1000)
        star = "" if self.time_source == "NTP" else "*"
        line = "{}{:02d}:{:02d}:{:02d}.{:03d} UTC {} {} {} {}".format(
            star, d.hour, d.minute, d.second, ms, DAYS[d.weekday()], MONTHS[d.month - 1], d.day, d.year)
        if detail:
            line += "\r\nTime source is " + self.time_source
        return line

    def show_ntp_associations(self):
        out = ["  address         ref clock       st   when   poll reach  delay  offset   disp"]
        with self.lock:
            for server in sorted(self.ntp_assocs):
                a = self.ntp_assocs[server]
                mark = "*" if self.ntp_peer is a else " "
                when = "-" if a.last_rx is None else str(int(time.monotonic() - a.last_rx))
                out.append("{}~{:<15} {:<15} {:>2} {:>6} {:>6} {:>5o} {:>6.3f} {:>7.3f} {:>6.3f}".format(
                    mark, server, a.refid, a.stratum, when, a.poll, a.reach,
                    a.delay * 1000, a.offset * 1000, a.disp * 1000))
        out.append(" * sys.peer, # selected, + candidate, - outlyer, x falseticker, ~ configured")
        return "\r\n".join(out)

    def show_ntp_status(self):
        with self.lock:
            peer = self.ntp_peer
            if peer is None:
                return "Clock is unsynchronized, stratum 16, no reference clock"
            return "Clock is synchronized, stratum {}, reference is {}".format(peer.stratum + 1, peer.server)


class SwitchSession(base.Session):
    """CLI-сессия коммутатора: режимы S2> / S2#, пароль enable, консоль."""

    def __init__(self, device, chan, user, peer, console=False):
        base.Session.__init__(self, device, chan, user, peer)
        self.priv = 1
        self.console = console
        self.pw_mode = False
        self.pw_tries = 0

    def prompt(self):
        if self.mode == "exec":
            return self.dev.hostname + ("#" if self.priv >= 15 else ">")
        return base.Session.prompt(self)

    def con0_banner(self):
        return "\r\n{} con0 is now available\r\n\r\n\r\n\r\n\r\n\r\nPress RETURN to get started.\r\n".format(
            self.dev.hostname)

    def wait_return(self):
        while True:
            try:
                data = self.chan.recv(1024)
            except Exception:  # noqa: BLE001
                return False
            if not data:
                return False
            if b"\r" in data or b"\n" in data:
                return True

    def finish(self):
        if self.console:
            self.send(self.con0_banner())
        try:
            self.chan.send_exit_status(0)
        except Exception:  # noqa: BLE001
            pass
        self.close()

    def run(self):
        if self.console:
            self.send(self.con0_banner())
            if not self.wait_return():
                self.close()
                return
            LOG.info("console session opened")
        self.send("\r\n" + self.prompt())
        prev = b""
        while True:
            try:
                data = self.chan.recv(4096)
            except Exception:  # noqa: BLE001
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
                    if self.pw_mode:
                        keep = self.check_enable(line)
                    else:
                        keep = self.execute(line)
                    if not keep:
                        LOG.info("session closed by 'exit' (%s)", self.peer)
                        self.finish()
                        return
                    self.send("Password: " if self.pw_mode else self.prompt())
                elif c in (b"\x7f", b"\x08"):
                    if self.buf:
                        self.buf = self.buf[:-1]
                        if not self.pw_mode:
                            self.send("\b \b")
                elif c == b"\x1a":  # Ctrl+Z
                    self.buf = ""
                    self.pw_mode = False
                    if self.mode != "exec":
                        self.mode = "exec"
                        self.cur_if = None
                    self.send("^Z\r\n" + self.prompt())
                elif c == b"\x03":  # Ctrl+C
                    self.buf = ""
                    self.pw_mode = False
                    self.send("^C\r\n" + self.prompt())
                elif 32 <= ch < 127:
                    self.buf += c.decode()
                    if not self.pw_mode:
                        self.send(c.decode())
                prev = c
        self.close()

    def check_enable(self, secret):
        if secret == self.dev.enable_secret:
            self.pw_mode = False
            self.pw_tries = 0
            self.priv = 15
            LOG.info("[%s %s] enable: privilege level 15", self.peer, self.user)
            return True
        self.pw_tries += 1
        LOG.info("[%s %s] enable: wrong password (attempt %d)", self.peer, self.user, self.pw_tries)
        if self.pw_tries >= 3:
            self.pw_mode = False
            self.pw_tries = 0
            self.out("% Bad secrets")
        return True

    def exec_cmd(self, t, raw, from_config=False):
        if self.priv < 15 and not from_config:
            kw = base.match_kw(t[0], ["enable", "exit", "logout", "quit", "show", "ping", "terminal", "disable"])
            if kw is None:
                self.invalid(raw)
                return True
            if kw == "enable":
                self.pw_mode = True
                self.pw_tries = 0
                return True
            if kw in ("exit", "logout", "quit"):
                return False
            if kw in ("disable", "terminal"):
                return True
            if kw == "show":
                return self.show(t[1:], raw)
            return base.Session.exec_cmd(self, t, raw, from_config)
        if base.match_kw(t[0], ["show", "configure", "terminal", "exit", "logout", "quit", "write", "copy",
                                "ping", "enable", "disable", "end", "clock"]) == "disable":
            if not from_config:
                self.priv = 1
            return True
        return base.Session.exec_cmd(self, t, raw, from_config)

    def show(self, t, raw):
        if t:
            kw = base.match_kw(t[0], ["version", "running-config", "ip", "ipv6", "interfaces", "clock", "privilege",
                                      "users", "startup-config", "history", "hostname", "ntp"])
            if kw == "clock":
                detail = len(t) > 1 and base.match_kw(t[1], ["detail"]) == "detail"
                self.out(self.dev.show_clock(detail))
                return True
            if kw == "ntp":
                sub = base.match_kw(t[1], ["associations", "status"]) if len(t) > 1 else None
                if sub == "associations":
                    self.out(self.dev.show_ntp_associations())
                elif sub == "status":
                    self.out(self.dev.show_ntp_status())
                elif len(t) == 1:
                    self.out(base.INCOMPLETE)
                else:
                    self.invalid(raw)
                return True
            if kw == "privilege":
                self.out("Current privilege level is {}".format(self.priv))
                return True
            if self.priv < 15 and kw in ("running-config", "startup-config"):
                self.invalid(raw)
                return True
        return base.Session.show(self, t, raw)

    def global_cfg(self, t, raw):
        neg = base.match_kw(t[0], ["no"]) == "no" and len(t) > 1
        tt = t[1:] if neg else t
        if base.match_kw(tt[0], ["ntp"]) == "ntp":
            if len(tt) >= 2 and base.match_kw(tt[1], ["server"]) == "server":
                if len(tt) < 3:
                    self.out(base.INCOMPLETE)
                    return True
                try:
                    socket.inet_aton(tt[2])
                    if tt[2].count(".") != 3:
                        raise OSError
                except OSError:
                    self.invalid(raw)
                    return True
                self.dev.ntp_server(tt[2], remove=neg)
                return True
            self.invalid(raw)
            return True
        return base.Session.global_cfg(self, t, raw)


class SockChannel(object):
    """Обёртка над сокетом консоли с интерфейсом канала paramiko."""

    def __init__(self, sock):
        self.sock = sock

    def sendall(self, data):
        self.sock.sendall(data)

    def recv(self, n):
        return self.sock.recv(n)

    def send_exit_status(self, code):
        pass

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


def console_server(path, device):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.unlink(path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    os.chmod(path, 0o600)
    srv.listen(2)
    LOG.info("console line con 0 on %s", path)
    while True:
        conn, _ = srv.accept()
        sess = SwitchSession(device, SockChannel(conn), "console", "console", console=True)
        threading.Thread(target=sess.run, daemon=True).start()


def telnet_refuser(host):
    """TCP/23: соединение принимается и сразу закрывается (transport input ssh)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, 23))
    srv.listen(5)
    while True:
        conn, addr = srv.accept()
        LOG.info("telnet from %s: vty lines accept SSH only (transport input ssh), connection closed", addr[0])
        conn.close()


def handle_ssh(sock, addr, device, host_key):
    peer = addr[0]
    transport = paramiko.Transport(sock)
    transport.local_version = "SSH-2.0-Cisco-1.25"
    transport.add_server_key(host_key)
    server = base.SshServer(device)
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
    LOG.info("SSH session opened: %s from %s", server.user, peer)
    SwitchSession(device, chan, server.user or device.username, peer).run()
    time.sleep(0.2)
    transport.close()
    LOG.info("SSH session closed: %s", peer)


def main():
    ap = argparse.ArgumentParser(description="S2 switch emulator (SSH, console, NTP client)")
    ap.add_argument("--host", required=True, help="management IP (interface Vlan1)")
    ap.add_argument("--hostname", default="S2")
    ap.add_argument("--username", default="administrator")
    ap.add_argument("--password", default="cisco")
    ap.add_argument("--enable-secret", default="cisco")
    ap.add_argument("--host-key", default=None)
    ap.add_argument("--console", default=None, help="Unix socket path of the console line")
    ap.add_argument("--no-telnet-listener", action="store_true")
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    handlers = [logging.StreamHandler(sys.stdout)]
    if args.log:
        handlers.append(logging.FileHandler(args.log))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", handlers=handlers)
    logging.getLogger("paramiko").setLevel(logging.CRITICAL)

    if args.host_key and os.path.exists(args.host_key):
        host_key = paramiko.RSAKey(filename=args.host_key)
    else:
        host_key = paramiko.RSAKey.generate(2048)
        if args.host_key:
            host_key.write_private_key_file(args.host_key)

    device = Switch(args.hostname, args.username, args.password, args.enable_secret, args.host)
    if args.console:
        threading.Thread(target=console_server, args=(args.console, device), daemon=True).start()
    if not args.no_telnet_listener:
        threading.Thread(target=telnet_refuser, args=(args.host,), daemon=True).start()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, 22))
    srv.listen(20)
    LOG.info("%s emulator: SSH on %s:22, user %s", args.hostname, args.host, args.username)
    while True:
        sock, addr = srv.accept()
        threading.Thread(target=handle_ssh, args=(sock, addr, device, host_key), daemon=True).start()


if __name__ == "__main__":
    main()
