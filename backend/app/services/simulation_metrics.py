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
    candidate_edges = Counter()
    platform_participants = defaultdict(set)
    messages = []
    first, last, conversations = None, None, 0
    types_for_talk = {"CREATE_POST","CREATE_COMMENT","REPLY","REPLY_POST","COMMENT","POST"}
    for event in events:
        kind = _safe_text(event.get("action_type"), 48).upper()
        sender = event.get("agent_id")
        if sender is None:
            sender = event.get("actor_uuid")
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
        platform_name = _safe_text(event.get("platform") or source, 25)
        by_platform[platform_name] += 1
        platform_participants[platform_name].add(key)
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
        target = args.get("target_agent_id")
        if target is None:
            target = event.get("target_agent_id")
        # Count only explicitly directed replies to another participant.
        # Mentions, self-replies and arbitrary missing IDs are not proof of dialogue.
        if kind in {"CREATE_COMMENT", "REPLY", "REPLY_POST", "COMMENT"} and target is not None and str(target) != key:
            candidate_edges[(platform_name,key,str(target)[:100])] += 1
        if kind in types_for_talk and len(messages) < 250:
            message = args.get("content") or event.get("action_text")
            if isinstance(message,str) and message.strip():
                target_id = target if target is not None and str(target) != key else None
                messages.append({
                    "participant":name, "participant_id":key,
                    "round":rnd if isinstance(rnd,int) else None,
                    "excerpt":_safe_text(message,360), "timestamp":stamp,
                    "platform":platform_name,
                    "type":kind,
                    "target_id":str(target_id)[:100] if target_id is not None else None,
                    "action_id":_safe_text(args.get("synthetic_action_id") or args.get("reply_to_action_id"),110) or None,
                    "synthetic":str(event.get("source_mode") or "").startswith("sintetico_"),
                })
    for (platform_name, sender_id, target_id), count in candidate_edges.items():
        if sender_id in platform_participants[platform_name] and target_id in platform_participants[platform_name]:
            edges[(sender_id, target_id)] += count
    cross_messages = sum(edges.values())
    active = len(participants)
    max_share = round(max((p["actions"] for p in participants.values()), default=0)
                      * 100 / max(1, sum(p["actions"] for p in participants.values())), 1)
    missing = []
    if active < 2:
        missing.append("Se requieren al menos 2 participantes activos.")
    if not edges:
        missing.append("Se requiere al menos 1 par de interacción explícito.")
    if cross_messages < 2:
        missing.append("Se requieren al menos 2 respuestas dirigidas entre perfiles.")
    if source == "getangiru":
        status = "not_applicable"
    elif not available:
        status = "unavailable"
    elif truncated:
        status = "unverified"
    elif missing:
        status = "insufficient"
    elif active >= 3 and len(edges) >= 2 and max_share <= 60:
        status = "good"
    else:
        status = "acceptable"
    quality = {
        "status": status,
        "label": {"good":"Interacción diversa", "acceptable":"Interacción aceptable",
                  "insufficient":"Completado con calidad insuficiente",
                  "unverified":"Calidad no verificable (datos parciales)",
                  "unavailable":"Calidad no verificable (sin eventos)",
                  "not_applicable":"No aplica: decisiones sin conversación"}[status],
        "active_participants": active,
        "interaction_pairs": len(edges),
        "cross_agent_messages": cross_messages,
        "maximum_action_share_percent": max_share,
        "diversity": ("baja" if active < 2 or max_share > 80 else
                      "media" if active < 3 or max_share > 60 else "alta"),
        "valid_multiagent_interaction": status in ("acceptable", "good"),
        "issues": missing if status == "insufficient" else (
            ["El registro es parcial; no se puede certificar la interacción."] if truncated
            else ["No hay eventos para evaluar."] if not available else []),
        "synthetic_only": True
    }
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
        "cross_agent_messages":cross_messages,
        "interaction_quality":quality,
        "first_event":first,"last_event":last,
        "by_day":[{"date":k,"count":v} for k,v in sorted(by_day.items())],
        "by_hour":[{"hour":f"{i:02d}","count":by_hour.get(f"{i:02d}",0)} for i in range(24)],
        "by_round":[{"round":k,"count":v} for k,v in sorted(by_round.items(),key=lambda x:int(x[0]))],
        "by_type":[{"type":k,"count":v} for k,v in by_type.most_common()],
        "by_platform":[{"platform":k,"count":v} for k,v in by_platform.most_common()],
        "participants":sorted(participants.values(),key=lambda p:(-p["actions"],p["name"]))[:120],
        "interactions":[{"from":a,"to":b,"count":n} for (a,b),n in edges.most_common(50)],
        "messages":messages,
        "messages_sample_limit":250,
        "messages_sample_truncated":conversations>len(messages),
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

def followup_metrics(path, simulation_id):
    """Aggregate private post-report synthetic chat/survey records separately."""
    counts=Counter()
    dates=Counter()
    actors={}
    scanned=0
    partial=False
    questions=[]
    path=Path(path)
    if not path.is_file():
        return {"available":False,"chat_turns":0,"surveys":0,
                "survey_answers":0,"participant_turns":0,
                "participants":[],"by_day":[],"questions":[],"partial":False}
    with path.open(encoding="utf-8",errors="replace") as handle:
        for line in handle:
            if scanned>=MAX_EVENTS:
                partial=True
                break
            scanned+=1
            if len(line)>16000:continue
            try:record=json.loads(line)
            except (TypeError,ValueError):continue
            if not isinstance(record,dict) or record.get("simulation_id")!=simulation_id:
                continue
            day,_=_day_and_hour(record.get("created_at"))
            if day:dates[day]+=1
            kind=record.get("kind")
            if kind=="survey":
                counts["surveys"]+=1
                results=record.get("results")
                for r in (results if isinstance(results,list) else []):
                    if not isinstance(r,dict) or not isinstance(r.get("answer"),str) or not r["answer"].strip():continue
                    key=str(r.get("agent_id"))[:80]
                    item=actors.setdefault(key,{"id":key,"name":_safe_text(r.get("agent_name") or key),"responses":0})
                    item["responses"]+=1
                    counts["survey_answers"]+=1
            elif kind=="chat":
                counts["chat_turns"]+=1
                if record.get("target")=="participant" and record.get("agent_id") is not None:
                    key=str(record.get("agent_id"))[:80]
                    item=actors.setdefault(key,{"id":key,"name":"Participante "+key,"responses":0})
                    item["responses"]+=1
                    counts["participant_turns"]+=1
            if isinstance(record.get("question"),str) and len(questions)<30:
                questions.append({"date":day,"kind":str(kind or "")[:20],
                                  "question":_safe_text(record["question"],180)})
    return {"available":True,"chat_turns":counts["chat_turns"],
            "surveys":counts["surveys"],"survey_answers":counts["survey_answers"],
            "participant_turns":counts["participant_turns"],
            "participants":sorted(actors.values(),key=lambda x:-x["responses"])[:100],
            "by_day":[{"date":k,"count":n} for k,n in sorted(dates.items())],
            "questions":questions,"partial":partial}
