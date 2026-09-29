#!/usr/bin/env python3
import base64, json, os, sys, time, urllib.parse, urllib.request, uuid

NTFY = "https://ntfy.sh"
MAX_ATTACHMENT = 3_000_000
MAX_MESSAGES = 12

def http(url, data=None, headers=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    if data is not None:
        req.method = "POST"
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers)

def fetch_topic(topic, since="20m"):
    q = urllib.parse.urlencode({"poll": "1", "since": since})
    raw, _ = http(f"{NTFY}/{topic}/json?{q}", headers={"User-Agent": "OmniPilot-GitHub-Relay/1"})
    msgs = []
    for line in raw.decode("utf-8", "replace").splitlines():
        try:
            m = json.loads(line)
        except Exception:
            continue
        if m.get("event") != "message":
            continue
        out = {"id": m.get("id"), "time": m.get("time"), "title": m.get("title"), "message": m.get("message")}
        att = m.get("attachment") or {}
        url = att.get("url")
        if url:
            p = urllib.parse.urlparse(url)
            if p.scheme != "https" or p.hostname != "ntfy.sh":
                out["attachment_error"] = "unexpected attachment host"
            else:
                try:
                    b, _ = http(url, headers={"User-Agent": "OmniPilot-GitHub-Relay/1"}, timeout=30)
                    if len(b) > MAX_ATTACHMENT:
                        out["attachment_error"] = "attachment too large"
                    else:
                        out["attachment_b64"] = base64.b64encode(b).decode("ascii")
                        out["attachment_size"] = len(b)
                except Exception as e:
                    out["attachment_error"] = str(e)
        msgs.append(out)
    msgs.sort(key=lambda x: (x.get("time") or 0, x.get("id") or ""))
    return msgs[-MAX_MESSAGES:]

def publish(topic, wire):
    if not isinstance(wire, str) or not wire.startswith("OPR1."):
        raise RuntimeError("request wire is not an OmniPilot envelope")
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Title": "omnipilot-command",
        "Cache": "yes",
        "Firebase": "no",
        "User-Agent": "OmniPilot-GitHub-Relay/1",
    }
    body, _ = http(f"{NTFY}/{topic}", data=wire.encode("utf-8"), headers=headers, timeout=20)
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return {"raw": body.decode("utf-8", "replace")[:500]}

def main():
    req_path = sys.argv[1] if len(sys.argv) > 1 else "relay/request.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "relay/response.json"
    with open(req_path, "r", encoding="utf-8") as f:
        req = json.load(f)
    rid = str(req.get("request_id") or "")
    op = str(req.get("operation") or "")
    started = int(time.time())
    res = {"request_id": rid, "operation": op, "started_epoch": started, "ok": False}
    try:
        if op == "probe":
            topic = "opprobe-" + uuid.uuid4().hex
            marker = "probe-" + uuid.uuid4().hex
            http(
                f"{NTFY}/{topic}",
                data=marker.encode("utf-8"),
                headers={"Content-Type":"text/plain", "Cache":"yes", "Firebase":"no", "User-Agent":"OmniPilot-GitHub-Relay/1"},
                timeout=15,
            )
            msgs = fetch_topic(topic, "2m")
            res.update({"ok": any(m.get("message") == marker for m in msgs), "relay": NTFY})
        elif op == "fetch":
            topic = str(req["topic"])
            since = str(req.get("since") or "20m")
            res.update({"ok": True, "messages": fetch_topic(topic, since)})
        elif op == "send_wait":
            command_topic = str(req["command_topic"])
            result_topic = str(req["result_topic"])
            wire = str(req["wire"])
            pub = publish(command_topic, wire)
            timeout_s = max(2, min(35, int(req.get("timeout_seconds") or 15)))
            min_time = int(req.get("min_result_epoch") or started - 2)
            deadline = time.time() + timeout_s
            messages = []
            while time.time() < deadline:
                messages = [m for m in fetch_topic(result_topic, str(max(0, min_time))) if int(m.get("time") or 0) >= min_time]
                if messages:
                    break
                time.sleep(1.5)
            res.update({"ok": True, "publish": pub, "messages": messages, "timed_out": not bool(messages)})
        else:
            raise RuntimeError("unsupported relay operation")
    except Exception as e:
        res["error"] = str(e)
    res["finished_epoch"] = int(time.time())
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(res, f, separators=(",", ":"), ensure_ascii=False)
    os.replace(tmp, out_path)
    if not res.get("ok"):
        print(json.dumps(res, indent=2), file=sys.stderr)

if __name__ == "__main__":
    main()
