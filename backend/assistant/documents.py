import re
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm


SECTION_TITLES = {
    "experience": "Experiência profissional",
    "education": "Formação",
    "course": "Cursos e certificações",
    "skill": "Competências e idiomas",
    "other": "Outras qualificações",
}


def resume_sections(profile, analysis):
    facts = {fact["id"]: fact for fact in profile["facts"]}
    sections = {}
    for key in analysis.get("resume_fact_ids", []):
        if key in facts:
            fact = facts[key]
            title = SECTION_TITLES.get(fact.get("category"), SECTION_TITLES["other"])
            sections.setdefault(title, []).append(fact["text"])
    if not sections:
        raise ValueError("Currículo sem fatos selecionados.")
    return sections


def resume_contact_line(profile):
    return " | ".join(
        profile[key]
        for key in ("email", "phone", "city", "linkedin_url")
        if profile.get(key)
    )


def resume_pdf(profile, analysis):
    sections = resume_sections(profile, analysis)
    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 11
    styles["Normal"].leading = 16
    styles["Title"].textColor = colors.HexColor("#102b36")
    story = [Paragraph(escape(profile["name"]), styles["Title"])]
    contact = resume_contact_line(profile)
    if contact:
        story.append(Paragraph(escape(contact), styles["Normal"]))
    for title, statements in sections.items():
        story.extend([Spacer(1, 0.4 * cm), Paragraph(title, styles["Heading2"])])
        for statement in statements:
            story.extend(
                [
                    Paragraph(
                        escape(statement).replace("\n", "<br/>"), styles["Normal"]
                    ),
                    Spacer(1, 0.3 * cm),
                ]
            )
    SimpleDocTemplate(
        stream,
        pagesize=(21 * cm, 29.7 * cm),
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        bottomMargin=2 * cm,
        topMargin=2 * cm,
    ).build(story)
    return stream.getvalue()


def resume_docx(profile, analysis):
    """Write a simple editable Office Open XML document from the same factual sections."""
    from zipfile import ZIP_DEFLATED, ZipFile

    def paragraph(text, size, bold=False):
        safe_lines = [
            escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", line))
            for line in text.splitlines()
        ]
        runs = "<w:br/>".join(
            f'<w:t xml:space="preserve">{line}</w:t>' for line in safe_lines
        )
        emphasis = "<w:b/>" if bold else ""
        return f'<w:p><w:r><w:rPr>{emphasis}<w:sz w:val="{size}"/></w:rPr>{runs}</w:r></w:p>'

    body = [paragraph(profile["name"], 38, True)]
    contact = resume_contact_line(profile)
    if contact:
        body.append(paragraph(contact, 20))
    for title, statements in resume_sections(profile, analysis).items():
        body.append(paragraph(title, 26, True))
        body.extend(paragraph(statement, 22) for statement in statements)
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""",
        )
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            + "".join(body)
            + "</w:body></w:document>",
        )
    return output.getvalue()


def resume_contacts(text):
    """Read only recognizable contact information near the start of the PDF."""
    lines = [line.strip() for line in text.splitlines() if line.strip()][:30]
    header = "\n".join(lines)
    contacts = {}

    def unique(field, values, limit):
        candidates = {
            value.strip() for value in values if 0 < len(value.strip()) <= limit
        }
        if len(candidates) == 1:
            contacts[field] = candidates.pop()

    emails = re.findall(r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}", header)
    unique("email", emails, 254)
    linkedin_ids = re.findall(
        r"(?<![\w@./-])(?:https?://)?(?:www\.)?linkedin\.com/in/([\w%.-]+)",
        header,
        re.I,
    )
    unique(
        "linkedin_url",
        [
            "https://www.linkedin.com/in/" + slug.rstrip(".")
            for slug in linkedin_ids
            if slug.strip(".")
        ],
        500,
    )

    phone_pattern = (
        r"(?:\+?55[ .-]*)?\(?[1-9][0-9]\)?[ .-]*[2-9][0-9]{3,4}[ .-]?[0-9]{4}"
    )
    phones = []
    for line in lines:
        match = re.fullmatch(
            rf"(?:(?:telefone|celular|whatsapp|phone|mobile|tel\.?)\s*[:–-]\s*)?({phone_pattern})(?:\s*\((?:mobile|celular)\))?",
            line,
            re.I,
        )
        if match:
            phones.append(match[1])
    unique("phone", phones, 50)

    for line in lines:
        match = re.fullmatch(r"(?:nome(?: completo)?|full name)\s*:\s*(.+)", line, re.I)
        if match:
            unique("name", [match[1]], 150)
            break
    else:
        first = next(
            (
                line
                for line in lines
                if not re.fullmatch(
                    r"contato|contact|curr[ií]culo|resume|profile", line, re.I
                )
            ),
            "",
        )
        words = first.split()
        common_headings = {
            "engenheiro",
            "engenheira",
            "analista",
            "desenvolvedor",
            "desenvolvedora",
            "consultor",
            "consultora",
            "curriculum",
            "experiência",
            "resumo",
            "professional",
            "software",
            "scrum",
            "product",
            "projetos",
            "formação",
        }
        if (
            2 <= len(words) <= 7
            and not any(word.casefold() in common_headings for word in words)
            and all(
                word.lower() in {"da", "de", "do", "das", "dos", "e"}
                or (
                    word[0].isupper()
                    and re.fullmatch(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*", word)
                )
                for word in words
            )
        ):
            unique("name", [first], 150)

    cities = []
    for line in lines[:16]:
        match = re.fullmatch(
            r"(?:cidade(?: / UF)?|localiza[cç][aã]o|location)\s*:\s*(.+)", line, re.I
        )
        if match:
            cities.append(match[1])
        elif re.fullmatch(
            r"[^\W\d_][\w .’'-]+\s*[,/-]\s*(?:[A-Z]{2}|[\w .’'-]+, (?:Brasil|Brazil))",
            line,
        ):
            cities.append(line)
    unique("city", cities, 150)
    return contacts
