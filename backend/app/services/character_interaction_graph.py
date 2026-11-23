"""Private evidence-backed character interaction graph for one simulation.

Never merge these fictional relationships with entities/edges extracted from
source documents. All edges come from messages with an explicit recipient in
the same recorded space. Character names are display aliases, not identities.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json
import re

from .simulation_metrics import MAX_EVENTS, MAX_FILE_BYTES

_SIM_ID = re.compile(r"^sim_[A-Za-z0-9_-]{1,90}$")
_NAMES = (
    "Valeria Benítez", "Mateo Cabrera", "Camila Franco", "Santiago Vera",
    "Lucía Giménez", "Andrés Sosa", "Renata Arce", "Nicolás Duarte",
    "Paula Villalba", "Thiago Acosta", "Sofía Rojas", "Joaquín Ferreira",
    "Mariana Aquino", "Gabriel López", "Isabel Medina", "Emiliano Ayala",
    "Micaela Gómez", "Tomás Sánchez", "Julieta González", "Bruno Ramírez",
)


def character_alias(agent_id: str | int) -> str:
    """Deterministic readable stage name; never taken as a real-world identity."""
    raw = str(agent_id)
    try:
        index = int(raw)
    except ValueError:
        index = sum((i + 1) * ord(ch) for i, ch in enumerate(raw))
    return _NAMES[index % len(_NAMES)] + (f" · {index // len(_NAMES) + 1}"
                                           if index >= len(_NAMES) else "")


def _text(value, limit=180):
    return re.sub(r"[\x00-\x1f]+", " ", str(value or "")).strip()[:limit]


def _professions(directory: Path):
    path = directory / "reddit_profiles.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, list):
        return {}
    result = {}
    for index, profile in enumerate(raw[:120]):
        if not isinstance(profile, dict):
            continue
        aid = str(profile.get("user_id", index))
        value = (profile.get("profession") or profile.get("occupation")
                 or profile.get("job_title") or profile.get("role")
                 or profile.get("profession_label") or "")
        # Do not infer a profession from free-form biography text.
        result[aid] = _text(value, 80) or "Profesión no indicada"
    return result


def character_graph(simulation_id: str, directory: Path) -> dict:
    if not _SIM_ID.fullmatch(simulation_id):
        raise ValueError("Identificador de simulación no válido.")
    base = Path(directory)
    professions = _professions(base)
    participants = {}
    relations = Counter()
    notes = defaultdict(list)
    messages = []
    valid_ids = defaultdict(set)
    rows = []
    truncated = False
    size_limit = MAX_FILE_BYTES
    for parent in ("twitter", "reddit"):
        path = base / parent / "actions.jsonl"
        if not path.is_file():
            continue
        total_bytes = 0
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                total_bytes += len(line.encode("utf-8"))
                if total_bytes > size_limit or len(rows) >= MAX_EVENTS:
                    truncated = True
                    break
                if not line.strip() or len(line) > 16000:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(record, dict) or "event_type" in record or record.get("agent_id") is None:
                    continue
                if record.get("action_type") not in ("CREATE_POST", "CREATE_COMMENT", "POST", "COMMENT", "REPLY", "REPLY_POST"):
                    continue
                args = record.get("action_args")
                if not isinstance(args, dict):
                    continue
                channel = _text(record.get("social_space") or parent, 40)
                aid = _text(record.get("agent_id"), 50)
                if not aid or not channel:
                    continue
                participants[aid] = {
                    "id":aid,"name":character_alias(aid),
                    "profession":professions.get(aid, "Profesión no indicada"),
                    "stage_name":True,
                }
                valid_ids[channel].add(aid)
                rows.append((record, channel, aid))
        if truncated:
            break
    for record, channel, aid in rows:
        args = record["action_args"]
        target = args.get("target_agent_id")
        target_id = str(target) if target is not None else None
        is_reply = record.get("action_type") in ("CREATE_COMMENT","COMMENT","REPLY","REPLY_POST")
        # No invented replies, unknown identities or cross-room edges.
        qualified = bool(is_reply and target_id and target_id != aid
                         and target_id in valid_ids[channel])
        message = _text(args.get("content") or record.get("action_text"), 440)
        if qualified:
            key = (channel, aid, target_id)
            relations[key] += 1
            if message and len(notes[key]) < 6:
                notes[key].append(message)
        if message and len(messages) < 600:
            messages.append({
                "from":aid,"to":target_id if qualified else None,
                "author":character_alias(aid),
                "recipient":character_alias(target_id) if qualified else None,
                "profession":participants[aid]["profession"],
                "channel":channel,"round":record.get("round"),
                "turn":record.get("conversation_turn"),
                "content":message,
                "action_id":_text(args.get("synthetic_action_id"),120),
                "reply_to":_text(args.get("reply_to_action_id"),120),
                "thread_id":_text(args.get("conversation_thread_id"),120),
                "timestamp":_text(record.get("timestamp"),50),
            })
    edges = [{
        "source":a,"target":b,"channel":ch,"count":count,
        "examples":notes[(ch,a,b)]
    } for (ch,a,b),count in relations.most_common(250)]
    return {
        "nodes":list(participants.values())[:120],
        "edges":edges,
        "messages":messages,
        "transcript_truncated":len(rows)>len(messages),
        "transcript_limit":600,
        "total_actions":len(rows),
        "directed_responses":sum(relations.values()),
        "rooms":sorted(valid_ids.keys()),
        "partial":truncated,
        "stage_names":True,
        "simulated_only":True,
        "notice":"Nombres de escena y conversaciones de un ejercicio simulado; no son identidades ni relaciones reales.",
    }
