"""Self-contained, print-friendly executive and technical report rendering.

Only recorded simulation metrics drive graphics. All elements are SVG/vector,
with no external CDN, JavaScript, tracker or untrusted model HTML.
"""
from __future__ import annotations
import html
import io
import math
import re
from datetime import datetime,timezone
from urllib.parse import urlencode

CHARTS=("rounds","days","hours","types","platforms","actors","network","followups")
SECTIONS=("summary","charts","participants","interactions","narrative","methodology")
PALETTE=("#1867ab","#17a2a4","#f4a44d","#795fc7","#d76085","#67a86d","#6783a5")
DEFAULT_EXEC=("rounds","types","actors","days","network")
DEFAULT_TECH=CHARTS

def clean(value):
    return html.escape(str(value if value is not None else ""),quote=True)

def options(query):
    mode=query.get("mode","executive")
    if mode not in ("executive","technical"):
        raise ValueError("Modo no disponible")
    def subset(key,available,default):
        raw=query.get(key)
        if raw is None:return list(default)
        if not isinstance(raw,str) or len(raw)>180:raise ValueError("Selección demasiado larga")
        vals=[x for x in raw.split(",") if x]
        if any(x not in available for x in vals) or len(vals)!=len(set(vals)):
            raise ValueError("Gráfico o sección no compatible")
        return vals
    heading=str(query.get("title") or "Informe de simulación — Tenonderã").strip()
    note=str(query.get("notes") or "").strip()
    if len(heading)>110 or len(note)>600:
        raise ValueError("Título o nota excede el límite")
    try:limit=int(query.get("top","12"))
    except (ValueError,TypeError):raise ValueError("Top de participantes inválido")
    if not 3<=limit<=30:raise ValueError("Top debe estar entre 3 y 30")
    return {"mode":mode,"title":heading,"notes":note,"top":limit,
            "charts":subset("charts",CHARTS,DEFAULT_EXEC if mode=="executive" else DEFAULT_TECH),
            "sections":subset("sections",SECTIONS,SECTIONS if mode=="technical" else ("summary","charts","participants","narrative","methodology"))}

def _esc_label(value,limit=26):
    x=str(value or "")
    return clean(x[:limit]+("…" if len(x)>limit else ""))

def _svg_bars(rows,label_key="round",title="",max_rows=20,rotate=False):
    rows=rows[:max_rows]
    if not rows or not any(int(x.get("count",0)) for x in rows):
        return '<p class="missing">Sin datos suficientes para este gráfico.</p>'
    width=760;height=290;left=55;right=24;top=30;bottom=76
    plot_w=width-left-right;plot_h=height-top-bottom
    topval=max(1,max(int(x.get("count",0)) for x in rows))
    step=plot_w/len(rows);barw=min(44,step*.62)
    parts=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{clean(title)}" xmlns="http://www.w3.org/2000/svg">']
    for i in range(5):
        y=top+plot_h*i/4
        val=round(topval*(4-i)/4)
        parts.append(f'<path d="M{left} {y:.1f}H{width-right}" stroke="#e2ebf2" stroke-width="1"/>'
                     f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" fill="#66788a" font-size="12">{val}</text>')
    for i,row in enumerate(rows):
        val=max(0,int(row.get("count",0)))
        x=left+(i+.5)*step-barw/2
        bh=plot_h*val/topval;y=top+plot_h-bh
        color=PALETTE[i%len(PALETTE)]
        label=str(row.get(label_key,""))
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{barw:.1f}" height="{bh:.1f}" fill="{color}" rx="4"/>')
        parts.append(f'<text x="{x+barw/2:.1f}" y="{max(14,y-5):.1f}" fill="#244461" text-anchor="middle" font-size="11">{val}</text>')
        # Hide alternate labels when dense; full values stay available in the table.
        if len(rows)<=12 or i%max(1,math.ceil(len(rows)/12))==0:
            parts.append(f'<text x="{x+barw/2:.1f}" y="{height-43}" fill="#536b80" text-anchor="middle" font-size="11">{_esc_label(label,10)}</text>')
    parts.append('</svg>')
    return "".join(parts)

def _svg_horizontal(rows,label_key="name",max_rows=12):
    rows=rows[:max_rows]
    if not rows:return '<p class="missing">Sin participantes registrados.</p>'
    width=760;height=max(110,40+len(rows)*31)
    left=235;right=55;maxvalue=max(1,max(int(r.get("actions",r.get("count",0))) for r in rows))
    parts=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Ranking de agentes sintéticos" xmlns="http://www.w3.org/2000/svg">']
    for i,row in enumerate(rows):
        y=15+i*31;n=int(row.get("actions",row.get("count",0)))
        bw=(width-left-right)*n/maxvalue
        parts.append(f'<text x="{left-10}" y="{y+17}" text-anchor="end" font-size="11" fill="#294766">{_esc_label(row.get(label_key),32)}</text>')
        parts.append(f'<rect x="{left}" y="{y+3}" width="{bw:.1f}" height="21" rx="5" fill="{PALETTE[i%len(PALETTE)]}"/>')
        parts.append(f'<text x="{left+bw+8:.1f}" y="{y+18}" font-size="12" fill="#294766">{n}</text>')
    return "".join(parts)+ "</svg>"

def _svg_donut(rows):
    rows=[r for r in rows if int(r.get("count",0))>0][:7]
    if not rows:return '<p class="missing">No se registraron categorías.</p>'
    total=sum(int(r["count"]) for r in rows)
    angle=-math.pi/2
    circles=[]
    legends=[]
    radius=86;cx=135;cy=130
    for i,row in enumerate(rows):
        fraction=int(row["count"])/total
        arc=2*math.pi*fraction
        startx=cx+radius*math.cos(angle);starty=cy+radius*math.sin(angle)
        endx=cx+radius*math.cos(angle+arc);endy=cy+radius*math.sin(angle+arc)
        if fraction>=.9999:
            path=f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{PALETTE[i%len(PALETTE)]}" stroke-width="31"/>'
        else:
            path=(f'<path d="M{startx:.2f},{starty:.2f} A{radius},{radius} 0 {1 if arc>math.pi else 0},1 {endx:.2f},{endy:.2f}" '
                  f'fill="none" stroke="{PALETTE[i%len(PALETTE)]}" stroke-width="31"/>')
        circles.append(path);angle+=arc
        name=row.get("type",row.get("platform","Otro"))
        legends.append(f'<rect x="280" y="{36+i*30}" width="13" height="13" rx="3" fill="{PALETTE[i%len(PALETTE)]}"/>'
                       f'<text x="300" y="{47+i*30}" font-size="13" fill="#2e4b65">{_esc_label(name,28)} · {fraction*100:.1f}%</text>')
    return ('<svg viewBox="0 0 690 270" role="img" aria-label="Distribución de categorías" xmlns="http://www.w3.org/2000/svg">'
            + "".join(circles)
            +f'<circle cx="{cx}" cy="{cy}" r="65" fill="#fff"/>'
            +f'<text x="{cx}" y="127" text-anchor="middle" font-size="28" font-weight="700" fill="#153b5d">{total}</text>'
            +f'<text x="{cx}" y="149" text-anchor="middle" font-size="12" fill="#648097">acciones</text>'
            +"".join(legends)+"</svg>")

def _svg_network(metrics):
    edges=metrics.get("interactions") or []
    if not edges:
        return '<p class="missing">No se identificaron destinatarios explícitos en los registros. No se dibujan relaciones supuestas.</p>'
    counts={}
    for edge in edges[:25]:
        a=str(edge.get("from",""));b=str(edge.get("to",""))
        counts[a]=counts.get(a,0)+int(edge.get("count",0))
        counts[b]=counts.get(b,0)+int(edge.get("count",0))
    names=sorted(counts,key=counts.get,reverse=True)[:14]
    n=len(names)
    if not n:return '<p class="missing">Sin relaciones verificables.</p>'
    nodes={name:(350+235*math.cos(2*math.pi*i/n),210+154*math.sin(2*math.pi*i/n)) for i,name in enumerate(names)}
    parts=['<svg viewBox="0 0 700 430" role="img" aria-label="Grafo de interacciones registradas" xmlns="http://www.w3.org/2000/svg">']
    for edge in edges:
        a,b=str(edge.get("from","")),str(edge.get("to",""))
        if a in nodes and b in nodes:
            ax,ay=nodes[a];bx,by=nodes[b]
            parts.append(f'<path d="M{ax:.1f},{ay:.1f}L{bx:.1f},{by:.1f}" stroke="#9bbad0" stroke-width="{min(6,1+int(edge.get("count",1)))}"/>')
    for i,(name,(x,y)) in enumerate(nodes.items()):
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="17" fill="{PALETTE[i%len(PALETTE)]}"/>'
                     f'<text x="{x:.1f}" y="{y+31:.1f}" font-size="11" text-anchor="middle" fill="#234861">{_esc_label(name,15)}</text>')
    return "".join(parts)+"</svg>"

def _table(rows,keys,labels,limit=30):
    if not rows:return '<p class="missing">Sin datos registrados.</p>'
    head="<tr>"+"".join(f"<th>{clean(label)}</th>" for label in labels)+"</tr>"
    cells="".join("<tr>"+"".join(f"<td>{clean(row.get(key,''))}</td>" for key in keys)+"</tr>" for row in rows[:limit])
    return f"<div class='table-scroll'><table><thead>{head}</thead><tbody>{cells}</tbody></table></div>"

def _render_markdown(md,include_full=False):
    """Plain Markdown subset; never interpret raw LLM HTML."""
    if not md:return "<p>El informe no tiene narrativa guardada.</p>"
    pieces=[]
    lines=md.splitlines()
    in_list=False
    in_quote=False
    for row in lines[:(1500 if include_full else 190)]:
        s=row.strip()
        if not s:
            if in_list:pieces.append("</ul>");in_list=False
            if in_quote:pieces.append("</blockquote>");in_quote=False
            continue
        if s.startswith("|"):continue # structured metric tables have dedicated visualizations
        if s.startswith("---"):pieces.append("<hr>");continue
        m=re.match(r"^(#{1,4})\s+(.+)$",s)
        if m:
            if in_list:pieces.append("</ul>");in_list=False
            lvl=min(4,len(m.group(1))+1)
            pieces.append(f"<h{lvl}>{clean(m.group(2))}</h{lvl}>")
        elif s.startswith("- "):
            if not in_list:pieces.append("<ul>");in_list=True
            pieces.append("<li>"+clean(s[2:])+"</li>")
        elif s.startswith(">"):
            if not in_quote:pieces.append("<blockquote>");in_quote=True
            pieces.append("<p>"+clean(s.lstrip("> "))+"</p>")
        else:pieces.append("<p>"+clean(s)+"</p>")
    if in_list:pieces.append("</ul>")
    if in_quote:pieces.append("</blockquote>")
    return "".join(pieces)

def render_html(markdown,metrics,opts,report_id):
    """Portable document: inline SVG/CSS, printable offline, no JS or fetch."""
    mode=opts["mode"];charts=set(opts["charts"]);sections=set(opts["sections"])
    heading=opts["title"]
    kpis=(("👥","Participantes",metrics.get("active_participants",0)),
          ("💬","Mensajes sintéticos",metrics.get("message_actions",0)),
          ("⚙","Acciones",metrics.get("total_actions",0)),
          ("🔗","Pares explícitos",metrics.get("recorded_interaction_pairs",0)))
    cards="".join(f"<div class='kpi'><span>{clean(icon)} {clean(label)}</span><strong>{clean(value)}</strong></div>" for icon,label,value in kpis)
    blocks=[]
    def panel(title,body,info=""):
        blocks.append(f'<section class="panel"><h2>{clean(title)}</h2>{("<p class=hint>"+clean(info)+"</p>") if info else ""}{body}</section>')
    if "charts" in sections:
        if "rounds" in charts: panel("📊 Acciones por ronda",_svg_bars(metrics.get("by_round",[]),"round","Acciones por ronda",30))
        if "days" in charts:panel("📅 Histograma por fecha real de ejecución",_svg_bars(metrics.get("by_day",[]),"date","Acciones por día",30))
        if "hours" in charts:panel("🕒 Distribución horaria",_svg_bars(metrics.get("by_hour",[]),"hour","Acciones por hora",24))
        if "types" in charts:panel("🍩 Distribución por tipo de acción",_svg_donut(metrics.get("by_type",[])))
        if "platforms" in charts:panel("🥧 Plataformas de interacción",_svg_donut(metrics.get("by_platform",[])))
        if "actors" in charts:panel("👥 Participantes más activos",_svg_horizontal(metrics.get("participants",[]),max_rows=opts["top"]))
        if "network" in charts:panel("🕸 Red de interacción",_svg_network(metrics),"Se representan únicamente relaciones con destinatario explícito.")
        if "followups" in charts:
            follow=metrics.get("followups") or {}
            panel("💬 Charlas y encuestas posteriores",
                  '<div class="mini"><span>Chats: <b>'+clean(follow.get("chat_turns",0))+'</b></span>'
                  '<span>Encuestas: <b>'+clean(follow.get("surveys",0))+'</b></span>'
                  '<span>Respuestas: <b>'+clean(follow.get("survey_answers",0))+'</b></span></div>'
                  +_svg_bars(follow.get("by_day",[]),"date","Interacciones posteriores",30))
    if "participants" in sections:
        panel("📋 Quiénes participaron",
              _table(metrics.get("participants",[]),("name","id","actions","messages"),
                     ("Agente sintético","ID","Acciones","Mensajes"),opts["top"]))
    if "interactions" in sections:
        panel("🔗 Interacciones identificadas",
              _table(metrics.get("interactions",[]),("from","to","count"),
                     ("Emisor","Destinatario","Acciones")))
    if "narrative" in sections:
        panel("📝 "+("Hallazgos y contexto del informe" if mode=="executive" else "Informe técnico y evidencia narrativa"),
              _render_markdown(markdown,include_full=(mode=="technical")))
    if "methodology" in sections:
        panel("ℹ Metodología y alcance",
              "<p>Estos actores, mensajes y opiniones son <strong>sintéticos</strong>, "
              "no personas reales ni resultados de encuestas públicas. Los horarios se refieren "
              "a la ejecución registrada, no al calendario ficticio. Las ausencias de datos no se estiman.</p>"
              "<p>Los gráficos se generan a partir de registros históricos sin modificar el informe original.</p>")
    if opts["notes"]:blocks.insert(0,'<section class="panel"><h2>🎯 Enfoque solicitado</h2><p>'+clean(opts["notes"])+'</p></section>')
    import datetime as _datetime
    timestamp=_datetime.datetime.now(_datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    css="""
      *{box-sizing:border-box}body{margin:0;background:#f1f5f9;color:#163450;font-family:Arial,Helvetica,sans-serif}
      .page{max-width:1100px;margin:auto;padding:28px}.hero{background:#113b67;color:white;border-radius:19px;padding:30px;margin-bottom:20px}
      .hero h1{font-size:28px;margin:10px 0}.hero p{margin:7px 0;color:#dbeaf5;font-size:13px}
      .eyebrow{letter-spacing:2px;font-size:11px;font-weight:700;color:#86d7e3}
      .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:22px}
      .kpi{padding:19px;background:#fff;border:1px solid #e1eaf2;border-radius:13px}
      .kpi span{display:block;color:#536e83;font-size:12px}.kpi strong{display:block;color:#125e91;font-size:31px;margin-top:8px}
      .panels{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
      .panel{background:white;border-radius:13px;border:1px solid #e0e9f1;padding:19px;min-width:0;break-inside:avoid}
      .panel:has(.table-scroll),.panel:has(blockquote){grid-column:1/-1}.panel h2{font-size:17px;margin:0 0 12px}
      .panel svg{max-width:100%;height:auto;display:block}.hint,.missing{font-size:12px;color:#6d8498}
      .table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:11px}th,td{border-bottom:1px solid #e5edf3;text-align:left;padding:8px;overflow-wrap:anywhere}
      th{background:#eaf3f8;color:#194e78}.panel p,.panel li{font-size:13px;line-height:1.65;overflow-wrap:anywhere}
      .panel h3{font-size:15px;margin-top:18px}.panel blockquote{margin:10px 0;padding:10px 16px;background:#edf6fa;border-left:4px solid #2397b4}
      .mini{display:flex;gap:12px;flex-wrap:wrap}.mini span{border:1px solid #dbe7ef;padding:8px 12px;border-radius:9px}
      .footer{color:#73879a;font-size:11px;text-align:center;margin:30px 0 8px}
      @media(max-width:740px){.page{padding:12px}.kpis{grid-template-columns:repeat(2,1fr)}.panels{grid-template-columns:1fr}.hero h1{font-size:23px}}
      @page{size:A4;margin:14mm}
      @media print{body{background:white}.page{max-width:none;padding:0}.hero{border-radius:0;print-color-adjust:exact;-webkit-print-color-adjust:exact}
       .panel,.kpi{break-inside:avoid;box-shadow:none}.panels{grid-template-columns:1fr 1fr;gap:9px}
       .panel{padding:12px}.kpis{gap:8px}.kpi{padding:10px}.kpi strong{font-size:22px}
       svg{break-inside:avoid}thead{display:table-header-group}}
    """
    # Description and counter reflect only explicitly measured events.
    note=("Resumen para decisiones" if mode=="executive" else "Detalle técnico y trazabilidad")
    return ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:">'
            '<title>'+clean(heading)+'</title><style>'+css+'</style></head><body><main class="page">'
            '<header class="hero"><div class="eyebrow">TENONDERÃ · '+clean(mode.upper())+'</div><h1>'+clean(heading)+'</h1>'
            '<p>'+clean(note)+' · ID '+clean(report_id)+' · '+clean(timestamp)+'</p>'
            '<p>Simulación sintética · Métricas de registros almacenados · No equivale a opinión pública real</p></header>'
            +('<div class="kpis">'+cards+'</div>' if "summary" in sections else "")
            +'<div class="panels"> '+"".join(blocks)+'</div>'
            '<footer class="footer">Tenonderã · Informe visual reproducible · Datos sintéticos · Exportación sin dependencias externas</footer>'
            '</main></body></html>')

def render_pdf(markdown,metrics,opts,report_id):
    """Generate compact native PDF charts using installed PyMuPDF, no Chromium/CDNs."""
    import fitz
    doc=fitz.open()
    pw,ph=fitz.paper_size("a4")
    margin=43
    page=None;y=0
    def ensure(required=30):
        nonlocal page,y
        if page is None or y+required>ph-margin-24:
            page=doc.new_page(width=pw,height=ph)
            page.draw_rect(fitz.Rect(0,0,pw,74),color=None,fill=(.065,.215,.38))
            page.insert_text((margin,31),"TENONDERA  /  INFORME VISUAL",fontsize=15,fontname="hebo",color=(1,1,1))
            page.insert_text((margin,53),opts["mode"].upper()+"  |  "+str(report_id)[:60],fontsize=9,color=(.73,.87,.96))
            y=95
        return page
    def line(text,size=10,heavy=False,indent=0):
        nonlocal y
        text=str(text).encode("latin-1","replace").decode("latin-1") # preserve Spanish accents; unsupported pictograms become placeholders
        words=text.split()
        if not words:return
        maxchars=max(15,int((pw-2*margin-indent)/(size*.53)))
        parts=[]
        while words:
            fragment=[]
            while words and len(" ".join(fragment+[words[0]]))<=maxchars:
                fragment.append(words.pop(0))
            if not fragment:fragment=[words.pop(0)[:maxchars]]
            parts.append(" ".join(fragment))
        ensure(len(parts)*(size+5)+6)
        for part in parts:
            page.insert_text((margin+indent,y),part,fontsize=size,fontname="hebo" if heavy else "helv",color=(.10,.24,.37))
            y+=size+5
    def separator():
        nonlocal y
        ensure(28);y+=8
        page.draw_line(fitz.Point(margin,y),fitz.Point(pw-margin,y),color=(.85,.90,.94),width=1);y+=18
    def bars(title,rows,key,limit=14):
        nonlocal y
        rows=rows[:limit]
        line(title,13,True)
        if not rows or not any(int(r.get("count",0))>0 for r in rows):
            line("No hay eventos registrados para este grafico",9);separator();return
        maxval=max(1,max(int(r.get("count",0)) for r in rows))
        for r in rows:
            ensure(19)
            label=str(r.get(key,""))[:22]
            page.insert_text((margin,y),label.encode("latin-1","replace").decode("latin-1"),fontsize=8,color=(.21,.37,.5))
            w=(pw-margin*2-225)*max(0,int(r.get("count",0)))/maxval
            page.draw_rect(fitz.Rect(margin+145,y-9,margin+145+w,y+2),fill=(.10,.47,.70),color=None)
            page.insert_text((pw-margin-31,y),str(r.get("count",0)),fontsize=8,color=(.1,.3,.5))
            y+=19
        separator()
    def donut(title,rows):
        """Vector pie with legend, drawn entirely inside the PDF."""
        nonlocal y
        rows=[r for r in rows if int(r.get("count",0))>0][:7]
        line(title,13,True)
        if not rows:
            line("Sin categorias registradas.",9);separator();return
        ensure(205)
        center=fitz.Point(margin+92,y+91);radius=65
        total=sum(int(r["count"]) for r in rows)
        angle=-math.pi/2
        for i,row in enumerate(rows):
            sweep=2*math.pi*int(row["count"])/total
            p=[center]
            parts=max(4,math.ceil(sweep/(math.pi/24)))
            for j in range(parts+1):
                theta=angle+sweep*j/parts
                p.append(fitz.Point(center.x+radius*math.cos(theta),
                                    center.y+radius*math.sin(theta)))
            rgb=tuple(int(PALETTE[i%len(PALETTE)][k:k+2],16)/255 for k in (1,3,5))
            page.draw_polyline(p,color=(1,1,1),fill=rgb,closePath=True,width=.7)
            label=str(row.get("type",row.get("platform","Otro")))[:28]
            page.draw_rect(fitz.Rect(margin+190,y+12+i*22,margin+201,y+23+i*22),
                           color=None,fill=rgb)
            page.insert_text((margin+211,y+22+i*22),
                             re.sub(r"[^\x20-\x7e]"," ",label)[:27]+f" {100*int(row['count'])/total:.0f}%",
                             fontsize=9,color=(.12,.28,.44))
            angle+=sweep
        # White center transforms the native pie into a donut.
        page.draw_circle(center,radius*0.55,color=None,fill=(1,1,1))
        page.insert_text((center.x-15,center.y+5),str(total),fontsize=18,fontname="hebo",color=(.08,.23,.39))
        y+=195
        separator()

    def graph(edges):
        """Draw a network only when recorded actor-to-actor edges exist."""
        nonlocal y
        line("Red de interacciones registradas",13,True)
        edges=edges[:25]
        if not edges:
            line("No hay destinatarios explicitos: no se dibujan vinculos supuestos.",9)
            separator()
            return
        nodes=sorted(set(str(e.get(k,"")) for e in edges for k in ("from","to")))[:12]
        if not nodes:
            separator();return
        ensure(250)
        cx=pw/2;cy=y+112
        r=88
        coords={name:fitz.Point(cx+r*math.cos(2*math.pi*i/len(nodes)),
                                cy+r*math.sin(2*math.pi*i/len(nodes))) for i,name in enumerate(nodes)}
        for edge in edges:
            a,b=str(edge.get("from","")),str(edge.get("to",""))
            if a in coords and b in coords:
                page.draw_line(coords[a],coords[b],color=(.61,.74,.83),
                               width=min(4,1+int(edge.get("count",1))))
        for i,name in enumerate(nodes):
            center=coords[name]
            rgb=tuple(int(PALETTE[i%len(PALETTE)][k:k+2],16)/255 for k in (1,3,5))
            page.draw_circle(center,12,color=None,fill=rgb)
            label=name.encode("latin-1","replace").decode("latin-1")[:13]
            page.insert_text((center.x-23,center.y+23),label,fontsize=7,color=(.1,.3,.45))
        y+=238
        separator()

    line(opts["title"],19,True);line("SIMULACION SINTETICA - NO REPRESENTA PERSONAS REALES",9)
    if opts["notes"]:line("Enfoque: "+opts["notes"],10)
    separator()
    if "summary" in opts["sections"]:
        for label,k in (("Agentes participantes","active_participants"),("Acciones","total_actions"),
                        ("Mensajes simulados","message_actions"),("Pares con destinatario","recorded_interaction_pairs")):
            line(f"{label}: {metrics.get(k,0)}",12,True)
        separator()
    if "charts" in opts["sections"]:
        selected=set(opts["charts"])
        for name,title,rows,key in (
            ("rounds","Acciones por ronda",metrics.get("by_round",[]),"round"),
            ("days","Actividad por fecha de ejecucion",metrics.get("by_day",[]),"date"),
            ("hours","Acciones por hora de ejecucion",metrics.get("by_hour",[]),"hour"),

            ("followups","Actividad de chats posteriores",(metrics.get("followups") or {}).get("by_day",[]),"date"),
        ):
            if name in selected:bars(title,rows,key)
        if "types" in selected:donut("Tipos de accion (grafico circular)",metrics.get("by_type",[]))
        if "platforms" in selected:donut("Distribucion por plataforma",metrics.get("by_platform",[]))
        if "actors" in selected:
            rows=[{"name":r["name"],"count":r["actions"]} for r in metrics.get("participants",[])[:opts["top"]]]
            bars("Participantes mas activos",rows,"name",opts["top"])
        if "network" in selected:graph(metrics.get("interactions",[]))
    if "participants" in opts["sections"]:
        line("Detalle de agentes registrados",13,True)
        for row in metrics.get("participants",[])[:opts["top"]]:
            line(f"{row['name']} | acciones {row['actions']} | mensajes {row['messages']}",9)
        separator()
    if "interactions" in opts["sections"]:
        line("Pares de interaccion registrados",13,True)
        for edge in metrics.get("interactions",[])[:25]:
            line(f"{edge['from']} -> {edge['to']}: {edge['count']}",9)
        separator()
    if "narrative" in opts["sections"]:
        line("Narrativa original - extracto" if opts["mode"]=="executive" else "Narrativa tecnica original",13,True)
        max_lines=90 if opts["mode"]=="executive" else 450
        for raw in markdown.splitlines()[:max_lines]:
            x=raw.strip()
            if x and not x.startswith("|") and not x.startswith("---"):
                line(x.lstrip("#>-* "),9,False)
        separator()
    if "methodology" in opts["sections"]:
        line("Metodo y limites",13,True)
        line("Las fechas reflejan la ejecucion real, no los dias del escenario ficticio.",9)
        line("No se atribuyen conversaciones o contactos sin destinatario registrado.",9)
        line("Los datos originales y sus reportes no se modificaron.",9)
    output=doc.tobytes(garbage=3,deflate=True)
    doc.close()
    return output
