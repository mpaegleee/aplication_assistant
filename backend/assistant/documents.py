from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm


def resume_pdf(profile, analysis):
    selected = set(analysis.get("resume_fact_ids", []))
    # Selection only: never render model-written professional statements.
    facts = {f["id"]: f for f in profile["facts"]}
    ordered = [facts[i] for i in analysis.get("resume_fact_ids", []) if i in facts]
    if not selected or not ordered:
        raise ValueError("Currículo sem fatos selecionados.")
    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 11
    styles["Normal"].leading = 16
    styles["Title"].textColor = colors.HexColor("#102b36")
    story = [Paragraph(escape(profile["name"]), styles["Title"])]
    contact = " | ".join(
        x
        for x in [profile.get("email"), profile.get("phone"), profile.get("city")]
        if x
    )
    if contact:
        story.append(Paragraph(escape(contact), styles["Normal"]))
    story += [
        Spacer(1, 0.5 * cm),
        Paragraph("Experiência e qualificações", styles["Heading2"]),
    ]
    for fact in ordered:
        story += [
            Paragraph(escape(fact["text"]).replace("\n", "<br/>"), styles["Normal"]),
            Spacer(1, 0.3 * cm),
        ]
    SimpleDocTemplate(
        stream,
        pagesize=(21 * cm, 29.7 * cm),
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    ).build(story)
    return stream.getvalue()
