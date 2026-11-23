"""Printable, self-contained executive HTML for synthetic simulation reports.

Escapes all model/document text and uses no scripts, external assets or fonts.
Charts are generated from persisted event counts; nothing is estimated.
"""
from __future__ import annotations

import html
import re


def _e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _n(value):
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _bar_rows(rows, *, name_key, unit):
    rows = rows[:35] if isinstance(rows, list) else []
    maximum = max([float(r.get("count", 0) or 0) for r in rows] + [1])
    parts = []
    for row in rows:
        count = max(0, float(row.get("count", 0) or 0))
        width = min(100, count * 100 / maximum)
        parts.append(
            '<div class="barrow"><span>' + _e(row.get(name_key, "—")) +
            '</span><div class="track"><div class="bar" style="width:' + f"{width:.2f}" +
            '%"></div></div><strong>' + _n(count) + '</strong></div>'
        )
    return "".join(parts) if parts else '<p class="muted">No se registraron datos para este indicador.</p>'


def _safe_markdown(md):
    """Readable headings/paragraphs, while keeping all untrusted markup inert."""
    result = []
    in_code = False
    for original in (md or "").splitlines():
        line = original.strip()
        if line.startswith("&&&"):
            continue
        if line.startswith("```"):
            if in_code:
                result.append("</pre>")
                in_code = False
            else:
                result.append('<pre class="code">')
                in_code = True
            continue
        if in_code:
            result.append(_e(original) + "\n")
            continue
        if not line:
            result.append('<div class="paragraph-space"></div>')
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            level = min(4, len(heading.group(1)) + 1)
            result.append(f"<h{level}>" + _e(heading.group(2)) + f"</h{level}>")
        elif line.startswith("- "):
            result.append('<p class="bullet">• ' + _e(line[2:]) + '</p>')
        elif line.startswith("|"):
            result.append('<p class="table-line">' + _e(line) + '</p>')
        else:
            result.append('<p>' + _e(line) + '</p>')
    if in_code:
        result.append("</pre>")
    return "".join(result)


def render_executive_html(markdown: str, metrics: dict, report_id: str):
    quality = metrics.get("interaction_quality") or {}
    active = int(metrics.get("active_participants") or 0)
    messages = int(metrics.get("message_actions") or 0)
    replies = int(metrics.get("cross_agent_messages") or 0)
    pairs = int(metrics.get("recorded_interaction_pairs") or 0)
    valid = bool(quality.get("valid_multiagent_interaction"))
    status = quality.get("label") or "Sin evaluación"
    issues = quality.get("issues") or []
    summary = (
        f"Se registraron {_n(metrics.get('total_actions'))} acciones de {_n(active)} "
        f"personajes ficticios, con {_n(messages)} mensajes. "
        f"Las respuestas dirigidas registradas suman {_n(replies)} y los pares explícitos {_n(pairs)}."
    )
    quality_text = (
        "Los eventos respaldan la interacción estructural mínima; no prueban opiniones reales."
        if valid else
        "No se acredita una conversación multiagente suficiente para considerarla una simulación conversacional válida."
    )
    people = metrics.get("participants") or []
    archive = metrics.get("conversation_archive") or {}
    aliases = {str(p.get("id")): p.get("name") for p in archive.get("nodes", [])}
    occupations = {str(p.get("id")): p.get("profession") for p in archive.get("nodes", [])}
    total = max(1, int(metrics.get("total_actions") or 0))
    rows = "".join(
        '<tr><td>' + _e(aliases.get(str(p.get("id"))) or p.get("name")) +
        '<span class="occupation"> · ' + _e(occupations.get(str(p.get("id")),"Profesión no indicada")) +
        '</span></td><td>' + _n(p.get("actions")) +
        '</td><td>' + _n(p.get("messages")) + '</td><td>' +
        f"{100*float(p.get('actions') or 0)/total:.1f}%" + '</td></tr>'
        for p in people[:120]
    )
    interactions = metrics.get("interactions") or []
    names = {str(p.get("id")): str(p.get("name")) for p in people}
    edges = "".join(
        '<tr><td>' + _e(aliases.get(str(item.get("from")),names.get(str(item.get("from")), item.get("from")))) +
        '</td><td>' + _e(aliases.get(str(item.get("to")),names.get(str(item.get("to")), item.get("to")))) +
        '</td><td>' + _n(item.get("count")) + '</td></tr>'
        for item in interactions[:50]
    )
    social_names = {
        "plaza":"Plaza","foro":"Foro abierto","profesional":"Comunidad profesional",
        "grupos":"Grupo social","videos":"Comentarios a videos",
        "twitter":"Plaza","reddit":"Comunidad",
    }
    rooms = metrics.get("by_social_space") or []
    location_rows = "".join(
        "<tr><td>" + _e(social_names.get(row.get("space"), row.get("space")))
        + "</td><td>" + _n(row.get("count")) + "</td></tr>"
        for row in rooms
    )
    transcript = "".join(
        '<article class="dialog-record"><div class="dialog-meta"><b>'
        + _e(m.get("author")) + "</b> <span>" + _e(m.get("profession") or "Profesión no indicada")
        + "</span> <span>" + _e(social_names.get(m.get("channel"), m.get("channel")))
        + "</span> <span>Ronda " + _e(m.get("round") or "—") + "</span></div>"
        + ('<div class="reply-record">Respondió a ' + _e(m.get("recipient")) + '</div>'
           if m.get("recipient") else '<div class="reply-record">Publicación inicial</div>')
        + "<p>" + _e(m.get("content")) + "</p></article>"
        for m in (archive.get("messages") or [])[:600]
    )
    disclaimer = (
        "Datos sintéticos conservados de la ejecución. Los personajes no representan "
        "personas reales; las fechas son del registro, no del calendario ficticio. "
        "Las conclusiones y opiniones generadas no son datos de encuesta ni predicciones."
    )
    css = """
      :root{color-scheme:light}*{box-sizing:border-box}
      body{font:14px/1.6 system-ui,Arial,sans-serif;background:#f3f6fa;color:#183550;margin:0}
      .sheet{max-width:1000px;margin:28px auto;padding:40px;background:#fff;border-radius:15px}
      .eyebrow{font-size:11px;color:#12758a;letter-spacing:2px;font-weight:800}
      h1{font-size:29px;line-height:1.2;margin:9px 0 6px;color:#133e5e}
      h2{font-size:20px;color:#164d6c;margin:27px 0 12px}
      h3{font-size:16px;color:#164b6a;margin:20px 0 10px}
      h4{font-size:14px;margin:18px 0 7px}
      .muted,.subtitle{color:#637e90;font-size:12px}.subtitle{margin-top:3px}
      .banner{border:1px solid #d3e1ed;background:#eef7fa;border-radius:12px;padding:17px;margin:23px 0}
      .banner.warning{background:#fff1e8;border:2px solid #d79d73;color:#7d381f}
      .banner p{margin:5px 0}.banner strong{font-size:15px}
      .cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}
      .card{background:#eff6f9;border:1px solid #dceaf0;border-radius:11px;padding:15px}
      .card b{font-size:28px;display:block;line-height:1.2;color:#153e5e}
      .card span{font-size:11px;color:#4c6b80}
      .two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:17px}
      .panel{border:1px solid #dce6ee;border-radius:11px;padding:18px;margin:12px 0;min-width:0}
      .barrow{display:grid;grid-template-columns:90px 1fr 35px;gap:9px;align-items:center;font-size:11px;margin:8px 0}
      .barrow>span{overflow-wrap:anywhere}.barrow strong{text-align:right}
      .track{background:#ecf2f6;border-radius:8px;height:11px;overflow:hidden}
      .bar{height:100%;background:linear-gradient(90deg,#185fb5,#0fb5b3);border-radius:8px}
      table{width:100%;border-collapse:collapse;font-size:12px}
      th{text-align:left;background:#eef4f7;color:#3c5d75}th,td{padding:10px;border-bottom:1px solid #e4ebef}
      .note{font-size:12px;color:#61798d;line-height:1.65}
      .report-content{font-size:13px;line-height:1.65}
      .report-content p{margin:6px 0;white-space:pre-wrap;overflow-wrap:anywhere}
      .report-content .paragraph-space{height:7px}
      .report-content .bullet{padding-left:15px}
      .report-content .table-line{font:11px/1.45 ui-monospace,monospace;white-space:pre-wrap}
      pre.code{padding:11px;overflow:auto;border:1px solid #dbe5ea;background:#f5f8fa;white-space:pre-wrap}
      .occupation{font-size:10px;color:#6c8394;white-space:normal}
      .dialog-record{border:1px solid #e0eaf0;border-radius:10px;padding:13px;margin:11px 0;break-inside:avoid}
      .dialog-meta{display:flex;gap:6px 13px;align-items:center;flex-wrap:wrap}
      .dialog-meta b{color:#174e6c;font-size:13px}
      .dialog-meta span{font-size:11px;color:#59788f}
      .reply-record{margin:6px 0;color:#137c9c;font-size:11px}
      .dialog-record p{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65;margin:7px 0}
      footer{border-top:1px solid #e5ebef;margin-top:40px;padding-top:13px;color:#74899a;font-size:10px}
      @media(max-width:700px){.sheet{margin:0;padding:18px}.cards{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
      @page{size:A4;margin:13mm}
      @media print{body{background:#fff}.sheet{margin:0;padding:0;max-width:none;box-shadow:none}
        .two{display:block}.panel{break-inside:avoid}.cards{break-inside:avoid}
        h2,h3{break-after:avoid}table{break-inside:auto}tr{break-inside:avoid}}
    """
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
        '<title>Tenonderã — Resultados de simulación</title><style>'+css+'</style></head><body>'
        '<main class="sheet"><header><div class="eyebrow">TENONDERÃ · INFORME EJECUTIVO</div>'
        '<h1>Resultados de la simulación</h1><p class="subtitle">Expediente ' + _e(report_id) +
        ' · Información obtenida de eventos persistidos</p></header>'
        '<section class="banner '+('' if valid else 'warning')+'"><strong>'+_e(status)+'</strong>'
        '<p>'+_e(quality_text)+'</p><p>'+_e(" ".join(issues))+'</p></section>'
        '<section><h2>Resumen ejecutivo basado en datos</h2><p>'+_e(summary)+'</p>'
        '<div class="cards"><div class="card"><b>'+_n(active)+'</b><span>Participantes activos</span></div>'
        '<div class="card"><b>'+_n(messages)+'</b><span>Mensajes</span></div>'
        '<div class="card"><b>'+_n(replies)+'</b><span>Respuestas dirigidas</span></div>'
        '<div class="card"><b>'+_n(pairs)+'</b><span>Relaciones explícitas</span></div></div>'
        '<p class="note">'+_e(disclaimer)+'</p></section>'
        '<section class="two"><div class="panel"><h3>Acciones por ronda</h3>'
        + _bar_rows(metrics.get("by_round") or [],name_key="round",unit="ronda")+
        '</div><div class="panel"><h3>Tipos de actividad</h3>'
        + _bar_rows(metrics.get("by_type") or [],name_key="type",unit="acción")+'</div></section>'
        '<section><h2>Participación por perfil</h2><p class="note">'
        'La distribución no refleja opiniones públicas, solo el volumen de acciones simuladas.</p>'
        '<table><thead><tr><th>Personaje del escenario</th><th>Acciones</th><th>Mensajes</th><th>Participación</th>'
        '</tr></thead><tbody>'+rows+'</tbody></table></section>'
        '<section><h2>Respuestas con destinatario registrado</h2>'
        + ('<table><thead><tr><th>Emisor</th><th>Destinatario</th><th>Respuestas</th></tr></thead><tbody>'+edges+'</tbody></table>'
           if edges else '<p class="note">No se encontraron pares dirigidos verificables.</p>')+
        '</section><section><h2>Dónde se desarrollaron las conversaciones</h2>'
        '<p class="note">Los espacios son escenarios de simulación, no redes sociales reales.</p>'
        '<table><thead><tr><th>Espacio</th><th>Intervenciones</th></tr></thead><tbody>'
        + location_rows + '</tbody></table>'
        '<h3>Registro de lo que se dijeron</h3>'
        + (transcript if transcript else '<p class="note">No se registraron mensajes para mostrar.</p>')
        + ('<p class="note">Se presenta una muestra del historial; las acciones originales se conservan.</p>'
           if archive.get("total_actions", 0) > len(archive.get("messages") or []) else '')
        + '</section><section class="report-content"><h2>Interpretación y capítulos del informe</h2>'
        +_safe_markdown(markdown)+'</section>'
        '<footer>Tenonderã · Informe sintético · Los indicadores son descriptivos y reproducibles desde el historial guardado.</footer>'
        '</main></body></html>'
    )
