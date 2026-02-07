#!/usr/bin/env python3
import os
import sys
import json

MAILBOX = os.environ.get("MAILBOX", "").strip()

def emit(k, v):
    if isinstance(v, bool):
        v = "true" if v else "false"
    print(f"{k}={v}")

mapping = {
    "SMTP_SERVER": "server",
    "SMTP_PORT": "port",
    "SMTP_USERNAME": "username",
    "SMTP_PASSWORD": "password",
    "SMTP_FROM": "from",
    "MAIL_TO": "to",
    "SMTP_SECURE": "secure",
}

def from_json(s):
    try:
        cfg = json.loads(s)
    except Exception:
        return False
    for env_key, json_key in mapping.items():
        emit(env_key, cfg.get(json_key, ""))
    return True

def from_env(s):
    vals = {}
    for line in s.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip()
    # 输出并设置默认
    for k in [
        "SMTP_SERVER",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "MAIL_TO",
    ]:
        emit(k, vals.get(k, ""))
    emit("SMTP_SECURE", vals.get("SMTP_SECURE", "true"))
    return True

def main():
    if not MAILBOX:
        print("MAILBOX is empty", file=sys.stderr)
        sys.exit(1)
    if MAILBOX.startswith("{"):
        ok = from_json(MAILBOX)
    else:
        ok = from_env(MAILBOX)
    if not ok:
        print("Failed to parse MAILBOX", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()