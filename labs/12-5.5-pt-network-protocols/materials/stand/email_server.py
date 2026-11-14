#!/usr/bin/env python3
"""Служба EMAIL сервера Example Server (аналог Services > EMAIL в Packet Tracer).

SMTP (TCP/25) - сервер aiosmtpd: принимает письма для пользователей своего домена
и раскладывает их по почтовым ящикам. POP3 (TCP/110) - минимальная реализация
RFC 1939 (USER/PASS, STAT, LIST, UIDL, RETR, TOP, DELE, RSET, NOOP, QUIT, CAPA).
Ящики хранятся в каталоге SPOOL/<домен>/<пользователь>/new/*.eml.

Настройки - INI-файл, повторяющий поля Packet Tracer:
    [email]
    smtp = on
    pop3 = on
    domain = www.example.com
    address = 64.100.0.10
    [users]
    Student1 = class

Запуск: python3 email_server.py -c email.ini [--daemon] [--log FILE] [--pidfile FILE]
"""

import argparse
import configparser
import email.utils
import logging
import os
import select
import socketserver
import sys
import threading
import time
import uuid

LOG = logging.getLogger("email")


class Config(object):
    def __init__(self, path):
        cp = configparser.ConfigParser()
        cp.optionxform = str  # имена пользователей с учётом регистра, как в PT
        if not cp.read(path, encoding="utf-8"):
            raise SystemExit("cannot read config file " + path)
        sec = cp["email"]
        self.domain = sec.get("domain", "").strip()
        self.address = sec.get("address", "127.0.0.1").strip()
        self.smtp = sec.getboolean("smtp", True)
        self.pop3 = sec.getboolean("pop3", True)
        self.smtp_port = sec.getint("smtp_port", 25)
        self.pop3_port = sec.getint("pop3_port", 110)
        self.spool = sec.get("spool", "/var/spool/pt-mail").strip()
        self.users = dict(cp["users"]) if cp.has_section("users") else {}
        if not self.domain:
            raise SystemExit("domain is not set")

    def canonical_user(self, name):
        for user in self.users:
            if user.lower() == (name or "").lower():
                return user
        return None

    def local_user(self, address):
        local, _, domain = address.strip("<> ").rpartition("@")
        if not local or domain.lower() != self.domain.lower():
            return None
        return self.canonical_user(local)

    def check_password(self, name, password):
        user = self.canonical_user(name)
        if user is not None and self.users[user] == password:
            return user
        return None

    def maildir(self, user):
        return os.path.join(self.spool, self.domain, user, "new")


def deliver(cfg, user, data):
    folder = cfg.maildir(user)
    os.makedirs(folder, exist_ok=True)
    name = "{}.{}.eml".format(time.time_ns(), uuid.uuid4().hex[:8])
    tmp = os.path.join(folder, "." + name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.rename(tmp, os.path.join(folder, name))
    return name


# ---------------------------------------------------------------- SMTP (aiosmtpd)

class SmtpHandler(object):
    def __init__(self, cfg):
        self.cfg = cfg

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if self.cfg.local_user(address) is None:
            LOG.info("SMTP %s: RCPT TO:<%s> rejected (user unknown)", session.peer[0], address)
            return "550 5.1.1 <{}>: Recipient address rejected: User unknown".format(address)
        envelope.rcpt_tos.append(address)
        return "250 2.1.5 OK"

    async def handle_DATA(self, server, session, envelope):
        content = envelope.original_content or envelope.content
        if isinstance(content, str):
            content = content.encode("utf-8")
        trace = ("Return-Path: <{}>\r\nReceived: from {} ([{}]) by {} with SMTP; {}\r\n".format(
            envelope.mail_from, session.host_name or "unknown", session.peer[0], self.cfg.domain,
            email.utils.formatdate(localtime=False))).encode("utf-8")
        for rcpt in envelope.rcpt_tos:
            user = self.cfg.local_user(rcpt)
            name = deliver(self.cfg, user, trace + content)
            LOG.info("SMTP %s: message from <%s> delivered to mailbox %s (%d bytes, %s)",
                     session.peer[0], envelope.mail_from, user, len(content), name)
        return "250 2.0.0 OK: message accepted for delivery"


def start_smtp(cfg):
    from aiosmtpd.controller import Controller
    ctl = Controller(SmtpHandler(cfg), hostname=cfg.address, port=cfg.smtp_port,
                     server_hostname=cfg.domain, ready_timeout=15)
    ctl.start()
    LOG.info("SMTP listening on %s:%d (domain %s)", cfg.address, cfg.smtp_port, cfg.domain)
    return ctl


# ---------------------------------------------------------------- POP3 (RFC 1939)

class Pop3Handler(socketserver.StreamRequestHandler):
    timeout = 600

    def reply(self, line):
        self.wfile.write((line + "\r\n").encode("utf-8"))
        self.wfile.flush()

    def load(self):
        folder = self.server.cfg.maildir(self.user)
        msgs = []
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.endswith(".eml") and not name.startswith("."):
                    path = os.path.join(folder, name)
                    with open(path, "rb") as fh:
                        lines = fh.read().decode("utf-8", "replace").splitlines()
                    size = sum(len(l.encode("utf-8")) + 2 for l in lines)
                    msgs.append({"path": path, "uid": name[:-4], "lines": lines, "size": size})
        return msgs

    def msg(self, arg):
        try:
            n = int(arg)
        except (TypeError, ValueError):
            self.reply("-ERR invalid message number")
            return None
        if n < 1 or n > len(self.msgs) or n in self.deleted:
            self.reply("-ERR no such message")
            return None
        return n

    def send_lines(self, lines):
        for line in lines:
            self.wfile.write((("." + line) if line.startswith(".") else line).encode("utf-8") + b"\r\n")
        self.wfile.write(b".\r\n")
        self.wfile.flush()

    def handle(self):
        cfg = self.server.cfg
        peer = self.client_address[0]
        self.user = None
        self.msgs = []
        self.deleted = set()
        name = None
        LOG.info("POP3 %s: connection", peer)
        self.reply("+OK {} POP3 server ready".format(cfg.domain))
        while True:
            raw = self.rfile.readline(4096)
            if not raw:
                break
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            cmd, _, arg = line.partition(" ")
            cmd = cmd.upper()
            arg = arg.strip()
            LOG.info("POP3 %s: %s", peer, "PASS ****" if cmd == "PASS" else line)
            if cmd == "QUIT":
                if self.user:
                    for n in sorted(self.deleted):
                        try:
                            os.remove(self.msgs[n - 1]["path"])
                        except OSError:
                            pass
                self.reply("+OK {} POP3 server signing off".format(cfg.domain))
                break
            if cmd == "CAPA":
                self.reply("+OK Capability list follows")
                self.send_lines(["USER", "UIDL", "TOP", "IMPLEMENTATION labnet-pop3"])
            elif cmd == "NOOP":
                self.reply("+OK")
            elif self.user is None:
                if cmd == "USER" and arg:
                    name = arg
                    self.reply("+OK send PASS")
                elif cmd == "PASS" and name:
                    user = cfg.check_password(name, arg)
                    if user is None:
                        LOG.info("POP3 %s: authentication failed for %s", peer, name)
                        self.reply("-ERR [AUTH] invalid user name or password")
                        name = None
                    else:
                        self.user = user
                        self.msgs = self.load()
                        LOG.info("POP3 %s: user %s logged in, %d message(s)", peer, user, len(self.msgs))
                        self.reply("+OK {} has {} message(s) ({} octets)".format(
                            user, len(self.msgs), sum(m["size"] for m in self.msgs)))
                else:
                    self.reply("-ERR authenticate first (USER/PASS)")
            elif cmd == "STAT":
                live = [m for i, m in enumerate(self.msgs, 1) if i not in self.deleted]
                self.reply("+OK {} {}".format(len(live), sum(m["size"] for m in live)))
            elif cmd in ("LIST", "UIDL"):
                field = "size" if cmd == "LIST" else "uid"
                if arg:
                    n = self.msg(arg)
                    if n:
                        self.reply("+OK {} {}".format(n, self.msgs[n - 1][field]))
                else:
                    self.reply("+OK")
                    self.send_lines(["{} {}".format(i, m[field]) for i, m in enumerate(self.msgs, 1)
                                     if i not in self.deleted])
            elif cmd == "RETR":
                n = self.msg(arg)
                if n:
                    m = self.msgs[n - 1]
                    self.reply("+OK {} octets".format(m["size"]))
                    self.send_lines(m["lines"])
            elif cmd == "TOP":
                parts = arg.split()
                n = self.msg(parts[0] if parts else None)
                if n:
                    count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    lines = self.msgs[n - 1]["lines"]
                    head = lines.index("") if "" in lines else len(lines)
                    self.reply("+OK")
                    self.send_lines(lines[:head + 1 + count])
            elif cmd == "DELE":
                n = self.msg(arg)
                if n:
                    self.deleted.add(n)
                    self.reply("+OK message {} deleted".format(n))
            elif cmd == "RSET":
                self.deleted.clear()
                self.reply("+OK")
            else:
                self.reply("-ERR unknown command")
        LOG.info("POP3 %s: connection closed", peer)


class Pop3Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_pop3(cfg):
    srv = Pop3Server((cfg.address, cfg.pop3_port), Pop3Handler)
    srv.cfg = cfg
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    LOG.info("POP3 listening on %s:%d", cfg.address, cfg.pop3_port)
    return srv


def start_all(cfg):
    parts = []
    if cfg.smtp:
        start_smtp(cfg)
        parts.append("SMTP {}:{}".format(cfg.address, cfg.smtp_port))
    if cfg.pop3:
        start_pop3(cfg)
        parts.append("POP3 {}:{}".format(cfg.address, cfg.pop3_port))
    if not parts:
        raise RuntimeError("both SMTP and POP3 are off")
    return "EMAIL service is on: {}; domain {}; users: {}".format(
        ", ".join(parts), cfg.domain, ", ".join(cfg.users) or "-")


def main():
    ap = argparse.ArgumentParser(description="EMAIL service (SMTP + POP3)")
    ap.add_argument("-c", "--config", required=True)
    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--log", default="/var/log/pt-lab/email.log")
    ap.add_argument("--pidfile", default=None)
    args = ap.parse_args()
    cfg = Config(args.config)
    os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)

    if not args.daemon:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s",
                            handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(args.log)])
        print(start_all(cfg), flush=True)
        while True:
            time.sleep(3600)

    rfd, wfd = os.pipe()
    pid = os.fork()
    if pid > 0:  # родитель ждёт, пока служба начнёт принимать соединения
        os.close(wfd)
        status = b""
        deadline = time.time() + 30
        while time.time() < deadline:
            ready, _, _ = select.select([rfd], [], [], max(0.0, deadline - time.time()))
            if not ready:
                break
            chunk = os.read(rfd, 4096)
            if not chunk:
                break
            status += chunk
        text = status.decode("utf-8", "replace").strip()
        if text.startswith("OK "):
            print(text[3:])
            return 0
        print("EMAIL service failed to start: " + (text or "no status from the service process"),
              file=sys.stderr)
        return 1

    os.close(rfd)
    os.setsid()
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s",
                        handlers=[logging.FileHandler(args.log)])
    try:
        status = start_all(cfg)
        if args.pidfile:
            with open(args.pidfile, "w") as fh:
                fh.write("{}\n".format(os.getpid()))
    except BaseException as exc:  # noqa: BLE001
        LOG.exception("start failed")
        os.write(wfd, "ERR {}".format(exc).encode("utf-8"))
        os._exit(1)
    LOG.info(status)
    os.write(wfd, ("OK " + status).encode("utf-8"))
    os.close(wfd)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    sys.exit(main())
