"""Deterministic, bounded statistics from persisted synthetic simulation events.

Wall-clock timestamps are execution event times, NOT simulated scenario dates.
Never infer an actual conversation partner without a recorded recipient field.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import json
import re

MAX_EVENTS = 25000
MAX_FILE_BYTES = 16 * 1024 * 1024
ACTION_RE = re.compile(r"^sim_[A-Za-z0-9_-]{1,90}$")

def _day_and_hour(timestamp):
    if not isinstance(timestamp, str) or len(timestamp) < 10:
        return None, None
    try:
        stamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    return stamp.date().isoformat(), f"{stamp.hour:02d}"

def _safe_text(value, limit=90):
    return re.sub(r"[\x00-\x1f]+", " ", str(value or ""))[:limit].strip()

def summarize(events, *, source, truncated=False, available=True):
    by_day, by_hour, by_round, by_type, by_platform = map(Counter, [{}]*5)
    participants = {}
    edges = Counter()
    messages = []
    first, last, conversations = None, None, 0
    types_for_talk = {"CREATE_POST","CREATE_COMMENT","REPLY","REPLY_POST","COMMENT","POST"}
    for event in events:
        kind = _safe_text(event.get("action_type"), 48).upper()
        sender = event.get("agent_id") or event.get("actor_uuid")
        if sender is None:
            continue
        key = str(sender)[:100]
        name = _safe_text(event.get("agent_name") or event.get("actor_type") or key)
        rec = participants.setdefault(key, {"id":key,"name":name,"actions":0,"messages":0})
        rec["actions"] += 1
        if kind in types_for_talk:
            rec["messages"] += 1
            conversations += 1
        by_type[kind or "OTHER"] += 1
        by_platform[_safe_text(event.get("platform") or source, 25)] += 1
        rnd = event.get("round_num",event.get("round",event.get("phase",0)))
        try:
            rnd = int(rnd)
            if 0 <= rnd <= 100000: by_round[str(rnd)] += 1
        except (TypeError,ValueError):
            pass
        stamp = event.get("timestamp") or event.get("created_at")
        day,hour = _day_and_hour(stamp)
        if day:
            by_day[day] += 1
            by_hour[hour] += 1
            first = min(first, stamp) if first else stamp
            last = max(last, stamp) if last else stamp
        args = event.get("action_args")
        if not isinstance(args,dict): args = {}
        target = args.get("target_agent_id") or event.get("target_agent_id")
        if target is not None and str(target) != key:
            edges[(key,str(target)[:100])] += 1
        if kind in types_for_talk and len(messages) < 50:
            message = args.get("content") or event.get("action_text")
            if isinstance(message,str) and message.strip():
                messages.append({"participant":name,"round":rnd if isinstance(rnd,int) else None,
                                 "excerpt":_safe_text(message,240),"timestamp":stamp})
    return {
        "source":source,
        "metric_basis":"eventos sintéticos persistidos; no son personas ni conversaciones reales",
        "date_basis":"timestamp de ejecución; no es fecha del escenario simulado",
        "available":available,
        "partial":truncated,
        "total_actions":sum(by_type.values()),
        "message_actions":conversations,
        "active_participants":len(participants),
        "recorded_interaction_pairs":len(edges),
        "first_event":first,"last_event":last,
        "by_day":[{"date":k,"count":v} for k,v in sorted(by_day.items())],
        "by_hour":[{"hour":f"{i:02d}","count":by_hour.get(f"{i:02d}",0)} for i in range(24)],
        "by_round":[{"round":k,"count":v} for k,v in sorted(by_round.items(),key=lambda x:int(x[0]))],
        "by_type":[{"type":k,"count":v} for k,v in by_type.most_common()],
        "by_platform":[{"platform":k,"count":v} for k,v in by_platform.most_common()],
        "participants":sorted(participants.values(),key=lambda p:(-p["actions"],p["name"]))[:100],
        "interactions":[{"from":a,"to":b,"count":n} for (a,b),n in edges.most_common(50)],
        "messages":messages,
    }

def legacy_metrics(simulation_id, simulation_dir):
    if not isinstance(simulation_id,str) or not ACTION_RE.fullmatch(simulation_id):
        raise ValueError("Identificador inválido")
    base = Path(simulation_dir)
    if not base.is_dir():
        return summarize([],source="oasis",available=False)
    files = [(base/"twitter"/"actions.jsonl","twitter"),
             (base/"reddit"/"actions.jsonl","reddit")]
    if not any(p.is_file() for p,_ in files):
        files=[(base/"actions.jsonl","oasis")]
    events=[]
    truncated=False
    for path,platform in files:
        if not path.is_file(): continue
        with path.open(encoding="utf-8",errors="replace") as stream:
            read=0
            for line in stream:
                read+=len(line.encode("utf-8"))
                if read>MAX_FILE_BYTES or len(events)>=MAX_EVENTS:
                    truncated=True;break
                if not line.strip() or len(line)>16000:continue
                try: event=json.loads(line)
                except (ValueError,TypeError):continue
                if not isinstance(event,dict) or "event_type" in event or "agent_id" not in event:
                    continue
                event["platform"]=event.get("platform") or platform
                events.append(event)
        if truncated:break
    return summarize(events,source="oasis",truncated=truncated)

def native_metrics(actions):
    return summarize(({
        "agent_id":a.get("actor_uuid"),"agent_name":a.get("actor_type"),
        "action_type":"DECISION","action_text":a.get("action_text"),
        "round_num":a.get("phase"),"timestamp":a.get("created_at"),
        "platform":"getangiru"
    } for a in actions),source="getangiru")
