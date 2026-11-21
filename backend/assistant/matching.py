import re, unicodedata, json, hashlib
from .models import AREAS

WEIGHTS = {
    "function": 30,
    "essential": 30,
    "seniority": 20,
    "desirable": 10,
    "preferences": 10,
}


def normalized(v):
    return re.sub(
        r"\s+",
        " ",
        "".join(
            c
            for c in unicodedata.normalize("NFKD", v.lower())
            if not unicodedata.combining(c)
        ),
    ).strip()


def exact_quote(quote, text):
    return bool(quote.strip()) and re.sub(r"\s+", " ", quote).strip() in re.sub(
        r"\s+", " ", text
    )


def fingerprint(profile, job, settings):
    payload = {
        "profile": profile,
        "job": {
            k: job.get(k)
            for k in [
                "title",
                "company",
                "url",
                "description",
                "area",
                "area_reviewed",
                "modality",
                "contract",
                "location",
                "salary",
                "recipient",
                "country",
                "application_url",
                "email_subject",
                "instructions_reviewed",
            ]
        },
        "policy": {
            k: settings.get(k)
            for k in ["threshold", "minimum_confidence", "ai_model", "ai_url"]
        },
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def hard_blocks(p, j):
    b = []
    if j.get("country", "BR") != "BR":
        b.append("Confirme que a vaga aceita candidatura no Brasil.")
    if j.get("company") in ["Revisar empresa", "Empresa não informada"]:
        b.append("Confirme a empresa responsável pela vaga.")
    if not p.get("confirmed"):
        b.append("Confirme seu perfil antes de candidatar.")
    if not p.get("facts"):
        b.append("Perfil sem fatos profissionais confirmados.")
    if not p.get("roles"):
        b.append("Defina os cargos pretendidos.")
    if not j.get("area_reviewed"):
        b.append("Revise a área profissional da vaga.")
    if not j.get("area") or j["area"] not in p.get("areas", []):
        b.append("Área fora dos objetivos profissionais.")
    if j.get("area") in p.get("excluded_areas", []):
        b.append("Área explicitamente excluída.")
    if p.get("modalities") and j.get("modality") not in p["modalities"]:
        b.append("Modalidade incompatível ou não informada.")
    if p.get("contracts") and j.get("contract") not in p["contracts"]:
        b.append("Contratação incompatível ou não informada.")
    if (
        p.get("locations")
        and j.get("modality") != "Remoto"
        and not any(
            normalized(x) in normalized(j.get("location", "")) for x in p["locations"]
        )
    ):
        b.append("Localidade incompatível ou não informada.")
    if p.get("minimum_salary", 0) > 0 and (
        j.get("salary") is None or j["salary"] < p["minimum_salary"]
    ):
        b.append("Remuneração abaixo do mínimo ou não informada.")
    return b


def validate_analysis(raw, p, j):
    facts = {f["id"]: f for f in p["facts"]}
    criteria = {}
    for key, weight in WEIGHTS.items():
        row = raw.get("criteria", {}).get(key, {})
        grade = row.get("grade")
        refs = row.get("fact_ids", [])
        quote = row.get("job_quote", "")
        if (
            not isinstance(grade, (int, float))
            or isinstance(grade, bool)
            or not 0 <= grade <= 100
        ):
            raise ValueError("A IA retornou uma nota inválida.")
        if not isinstance(refs, list) or any(x not in facts for x in refs):
            raise ValueError("A IA citou fatos inexistentes.")
        if grade > 0 and (
            not refs or not exact_quote(quote, j["description"] + " " + j["title"])
        ):
            raise ValueError("A IA não apresentou evidência verificável para a nota.")
        criteria[key] = {
            "grade": round(grade),
            "weight": weight,
            "fact_ids": refs,
            "job_quote": quote,
            "reason": str(row.get("reason", ""))[:1500],
        }
    selected = raw.get("resume_fact_ids", [])
    if (
        not isinstance(selected, list)
        or not selected
        or any(x not in facts for x in selected)
    ):
        raise ValueError("Seleção de currículo inválida.")
    confidence = raw.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 100
    ):
        raise ValueError("Confiança inválida.")
    return {
        "score": round(
            sum(row["grade"] * row["weight"] / 100 for row in criteria.values())
        ),
        "confidence": round(confidence),
        "criteria": criteria,
        "resume_fact_ids": list(dict.fromkeys(selected)),
        "gaps": str(raw.get("gaps", ""))[:3000],
    }


TITLE_RULES = {
    "Projetos e Agilidade": r"\b(scrum master|agile master|agile coach|pmo|governanca de projetos|gerente de projetos)\b",
    "Desenvolvimento": r"\b(desenvolvedor|desenvolvedora|developer|programador|programadora|software engineer|engenheir[oa] de software)\b",
    "Dados": r"\b(cientista de dados|analista de dados|engenheir[oa] de dados|data scientist|data engineer)\b",
    "Financeiro": r"\b(financeiro|financeira|contabil|contador|contadora|contabilidade)\b",
    "Comercial": r"\b(vendedor|vendedora|comercial|vendas|sales|sdr|bdr)\b",
    "Marketing": r"\b(marketing|social media)\b",
    "Recursos Humanos": r"\b(recursos humanos|recrutador|recrutadora|rh)\b",
    "Infraestrutura": r"\b(devops|sre|infraestrutura)\b",
    "Produto e Design": r"\b(product manager|product designer|ux|ui|designer)\b",
}


def infer_area(title):
    matched = [
        a for a, pattern in TITLE_RULES.items() if re.search(pattern, normalized(title))
    ]
    return matched[0] if len(matched) == 1 else ""
