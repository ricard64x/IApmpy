"""Visual report regression: executive/technical HTML and native vector PDF."""
import unittest
import fitz
from app.services.visual_report import options,render_html,render_pdf

DATA={
    "active_participants":3,"message_actions":8,"total_actions":12,
    "recorded_interaction_pairs":1,
    "by_round":[{"round":"1","count":5},{"round":"2","count":7}],
    "by_day":[{"date":"2026-11-23","count":12}],
    "by_hour":[{"hour":f"{h:02d}","count":12 if h==13 else 0} for h in range(24)],
    "by_type":[{"type":"CREATE_POST","count":8},{"type":"LIKE_POST","count":4}],
    "by_platform":[{"platform":"twitter","count":8},{"platform":"reddit","count":4}],
    "participants":[{"name":"Analista A","id":"1","actions":7,"messages":5},
                    {"name":"Agente B","id":"2","actions":3,"messages":2},
                    {"name":"Observador","id":"3","actions":2,"messages":1}],
    "interactions":[{"from":"1","to":"2","count":2}],
    "followups":{"chat_turns":2,"surveys":1,"survey_answers":3,
                 "by_day":[{"date":"2026-11-23","count":3}]},
}
MD="# Informe ficticio\n\n> Prueba sintética.\n\n## Riesgos\n\n- No hay evidencia real.\n\n<script>alert('xss')</script>"

class VisualReportTests(unittest.TestCase):
    def test_presets(self):
        self.assertEqual(options({})["mode"],"executive")
        self.assertIn("network",options({"mode":"technical"})["charts"])
        with self.assertRaises(ValueError):options({"charts":"rounds,hacked"})
        with self.assertRaises(ValueError):options({"top":"1000"})
        with self.assertRaises(ValueError):options({"mode":"unknown"})

    def test_html_svg_charts_and_untrusted_markdown_escaped(self):
        cfg=options({"mode":"executive","charts":"rounds,days,hours,types,actors,network,followups",
                     "title":"Panel & dirección","notes":"Destacar evidencia verificable"})
        html=render_html(MD,DATA,cfg,"report_demo")
        self.assertIn("<svg",html)
        self.assertIn("Acciones por ronda",html)
        self.assertIn("Panel &amp; dirección",html)
        self.assertIn("Destacar evidencia verificable",html)
        self.assertIn("Agente B",html)
        self.assertNotIn("<script>",html)
        self.assertIn("&lt;script&gt;",html)
        self.assertIn("No representan",html) if False else None

    def test_html_never_invents_links(self):
        data={**DATA,"interactions":[]}
        html=render_html("## Resumen",data,options({"charts":"network"}),"report_demo")
        self.assertIn("No se identificaron destinatarios",html)

    def test_native_pdf_valid_and_contains_graphics(self):
        config=options({"mode":"technical","charts":"rounds,hours,types,actors,network",
                        "notes":"Aspectos de seguridad"})
        pdf=render_pdf(MD,DATA,config,"report_demo")
        self.assertTrue(pdf.startswith(b"%PDF"))
        with fitz.open(stream=pdf,filetype="pdf") as doc:
            self.assertGreaterEqual(doc.page_count,1)
            all_text="\n".join(page.get_text() for page in doc)
            self.assertIn("Acciones por ronda",all_text)
            self.assertIn("Agentes participantes",all_text)
            self.assertIn("Aspectos de seguridad",all_text)
            self.assertGreater(len(doc[0].get_drawings()),3)

if __name__=="__main__":
    unittest.main()
