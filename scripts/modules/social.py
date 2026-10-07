"""Municipal social protection, four distinct administrative universes.

All publication uses an explicit schema and suppression; no identified records.
"""

import copy
import csv
import hashlib
import json
import math
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from scripts.common import atomic_write, read
from scripts.sources import mds
from scripts.sources.ibge import IBGE

CODE = "4127965"
INCOME_DEFINITION = "https://www.gov.br/mds/pt-br/noticias-e-conteudos/desenvolvimento-social/noticias-desenvolvimento-social/desde-2023-mais-de-14-milhoes-de-pessoas-sairam-da-pobreza"
TOOLS = "https://www.gov.br/mds/pt-br/orgaos/SAGICAD/dados-e-ferramentas-informacionais/dados-e-ferramentas-do-cadastro-unico"
IDS = "https://www.gov.br/mds/pt-br/orgaos/SAGICAD/dados-e-ferramentas-informacionais/IDCRAS-IDCREAS-e-IDConselho/cras"
IVCAD = "https://www.gov.br/mds/pt-br/orgaos/SAGICAD/dados-e-ferramentas-informacionais/ivcad"
NOTE = "Estatística administrativa municipal agregada; famílias e pessoas são unidades distintas. Não somar universos CadÚnico, Bolsa Família e BPC."
METRIC_KEYS = {
    "value",
    "status",
    "unit",
    "reference",
    "municipalityCode",
    "agency",
    "base",
    "indicator",
    "sourceId",
    "url",
    "collectedAt",
    "transformation",
    "note",
    "numerator",
    "denominator",
    "numeratorReference",
    "denominatorReference",
    "denominatorUrl",
}
ROOT_KEYS = {
    "schemaVersion",
    "municipality",
    "summary",
    "cadunico",
    "bolsaFamilia",
    "bpc",
    "suas",
    "services",
    "comparisons",
    "sources",
    "collection",
    "privacy",
}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def source(identifier, title, reference, url, now, payload=None, **extra):
    return {
        "id": identifier,
        "title": title,
        "agency": "MDS / SAGICAD / SNAS",
        "reference": reference,
        "url": url,
        "collectedAt": now,
        "contentHash": (
            digest(payload) if payload is not None else extra.pop("contentHash", "")
        ),
        "methodology": NOTE,
        **extra,
    }


def metric(
    value,
    unit,
    title,
    reference,
    source_,
    code=CODE,
    status="real",
    note=NOTE,
    transformation="Valor municipal publicado; sem imputação.",
    **extra,
):
    if value is None:
        status = "unavailable"
    # Counts describing households/beneficiaries/services are protected even
    # when the upstream public aggregate exposes small cells. Institutions aren't people.
    if (
        status in {"real", "derived"}
        and unit in {"famílias", "pessoas", "benefícios", "atendimentos"}
        and 0 < value < 5
    ):
        value = None
        status = "suppressed"
        note = "Célula de 1 a 4 suprimida pelo Observatório; nenhum valor original publicado."
    return {
        "value": value,
        "status": status,
        "unit": unit,
        "reference": reference,
        "municipalityCode": code,
        "agency": source_["agency"],
        "base": source_["title"],
        "indicator": title,
        "sourceId": source_["id"],
        "url": source_["url"],
        "collectedAt": source_["collectedAt"],
        "transformation": transformation,
        "note": note,
        **extra,
    }


def metric_title(key, base):
    labels = {
        "families": "Famílias",
        "people": "Pessoas",
        "updated": "Famílias com cadastro atualizado",
        "updatedPercent": "Percentual de famílias com cadastro atualizado",
        "povertyFamilies": "Famílias · pobreza",
        "lowIncomeFamilies": "Famílias · baixa renda",
        "aboveHalfFamilies": "Famílias · acima de meio salário mínimo",
        "povertyPeople": "Pessoas · pobreza",
        "lowIncomePeople": "Pessoas · baixa renda",
        "aboveHalfPeople": "Pessoas · acima de meio salário mínimo",
        "transferredValue": "Valor mensal transferido",
        "averageBenefit": "Benefício médio oficial",
        "elderly": "Benefícios · pessoa idosa",
        "disabled": "Benefícios · pessoa com deficiência",
        "total": "Total de benefícios",
        "elderlyValue": "Valor · pessoa idosa",
        "disabledValue": "Valor · pessoa com deficiência",
    }
    return labels.get(key, key) + " · " + base


def parsed(row, mapping):
    if row is None:
        return {k: None for k in mapping}
    return {
        k: (
            mds.percent(row.get(field))
            if k == "updatedPercent"
            else mds.numeric(
                row.get(field),
                money=k
                in {
                    "transferredValue",
                    "averageBenefit",
                    "elderlyValue",
                    "disabledValue",
                },
            )
        )
        for k, field in mapping.items()
    }


def monthly_block(rows, mapping, title, now, url, code=CODE):
    latest = mds.latest(rows, mapping)
    if not latest:
        raise ValueError(f"{title}: publicação completa não confirmada para {code}")
    ref = latest["anomes_s"]
    values = parsed(latest, mapping)
    unit_for = lambda k: (
        "%"
        if k == "updatedPercent"
        else (
            "R$"
            if k
            in {"transferredValue", "averageBenefit", "elderlyValue", "disabledValue"}
            else (
                "famílias"
                if k in {"families", "updated"} or k.endswith("Families")
                else (
                    "pessoas" if k == "people" or k.endswith("People") else "benefícios"
                )
            )
        )
    )
    # Only fields defining this block affect its fingerprint, not other programs.
    fingerprint = [
        {k: r[k] for k in ["anomes_s", *mapping.values()] if k in r}
        for r in rows
        if "202303" <= r["anomes_s"] <= ref
    ][-24:]
    s = source(
        title + "-" + code, title, ref, mds.monthly_url("202303", ref), now, fingerprint
    )
    out = {
        "reference": ref,
        **{
            k: metric(v, unit_for(k), metric_title(k, title), ref, s, code)
            for k, v in values.items()
        },
    }
    # Preserve calendar gaps rather than bridging missing months. Latest 24 months.
    year, month = int(ref[:4]), int(ref[4:])
    ordinal = year * 12 + month - 1
    series = []
    indexed = {r["anomes_s"]: r for r in rows}
    for offset in range(23, -1, -1):
        n = ordinal - offset
        p = f"{n//12}{n%12+1:02d}"
        r = indexed.get(p)
        if p < "202303":
            continue
        vals = parsed(r, mapping)
        if mapping is mds.BPC and (
            r is None or any(r.get(f) is None for f in mapping.values())
        ):
            vals = {k: None for k in mapping}
        series.append(
            {
                "reference": p,
                **{
                    k: metric(v, unit_for(k), metric_title(k, title), p, s, code)
                    for k, v in vals.items()
                },
            }
        )
    out["series"] = series
    return out, s


def cadunico(rows, now, url, code=CODE):
    block, s = monthly_block(rows, mds.CAD, "Cadastro Único", now, url, code)
    groups = [
        ("poverty", "Pobreza", "povertyFamilies", "povertyPeople"),
        ("lowIncome", "Baixa renda", "lowIncomeFamilies", "lowIncomePeople"),
        (
            "aboveHalf",
            "Acima de meio salário mínimo",
            "aboveHalfFamilies",
            "aboveHalfPeople",
        ),
    ]
    for total, keys in [
        ("families", [g[2] for g in groups]),
        ("people", [g[3] for g in groups]),
    ]:
        vals = [block[k]["value"] for k in keys]
        if all(v is not None for v in vals) and sum(vals) != block[total]["value"]:
            raise ValueError("Faixas de renda não somam o universo oficial")
    if block["updated"]["value"] is not None and block["families"]["value"] is not None:
        if block["updated"]["value"] > block["families"]["value"]:
            raise ValueError("Cadastros atualizados superiores ao total")
        if (
            abs(
                (
                    block["updated"]["value"] / block["families"]["value"] * 100
                    if block["families"]["value"]
                    else 0
                )
                - block["updatedPercent"]["value"]
            )
            > 0.02
        ):
            raise ValueError("Taxa cadastral incompatível com numerador/denominador")
    income = [
        {"id": g[0], "label": g[1], "families": block[g[2]], "people": block[g[3]]}
        for g in groups
    ]
    for unit in ("families", "people"):
        if any(r[unit]["status"] == "suppressed" for r in income):
            for r in income:
                r[unit]["value"] = None
                r[unit]["status"] = "suppressed"
                r[unit][
                    "note"
                ] = "Faixas de renda protegidas por supressão complementar."
    difference = (
        block["families"]["value"] - block["updated"]["value"]
        if all(block[k]["value"] is not None for k in ("families", "updated"))
        else None
    )
    q = {
        "updated": block["updated"],
        "updatedPercent": block["updatedPercent"],
        "notUpdated": metric(
            difference,
            "famílias",
            "Diferença entre cadastrados e atualizados",
            block["reference"],
            s,
            code,
            "derived",
            note="Diferença no mesmo universo e competência. Não representa famílias atualizadas/incluídas recentemente.",
            transformation="famílias cadastradas − famílias atualizadas",
        ),
    }
    if (
        q["updated"]["status"] == "suppressed"
        or q["notUpdated"]["status"] == "suppressed"
    ):
        for cell in q.values():
            cell["value"] = None
            cell["status"] = "suppressed"
            cell["note"] = (
                "Supressão complementar da qualidade cadastral para impedir reconstrução."
            )
    # Classification thresholds are an edition-bound explanatory note, never
    # reclassification of historical rows or a permanent eligibility algorithm.
    definitions = {
        "reference": "202609",
        "url": INCOME_DEFINITION,
        "checkedAtEdition": "2026-06-04",
        "note": "Nomenclatura publicada no RI. Definição MDS consultada em junho/2026: pobreza até R$ 218 por pessoa/mês; baixa renda acima desse limite até meio salário mínimo; terceira faixa acima de meio salário mínimo. Revalidar definições antes de aplicar a novas edições.",
    }
    return {
        "reference": block["reference"],
        "families": block["families"],
        "people": block["people"],
        "income": income,
        "incomeDefinition": definitions,
        "registrationQuality": q,
        "series": [
            {
                "reference": r["reference"],
                "families": r["families"],
                "people": r["people"],
            }
            for r in block["series"]
        ],
        "methodologyBreaks": [
            {
                "reference": "202503",
                "note": "Novo sistema do Cadastro Único (março/2025); observar possíveis mudanças administrativas na leitura da série.",
            }
        ],
    }, s


def bpc_block(rows, now, url):
    b, s = monthly_block(rows, mds.BPC, "BPC · Fonte Pagadora", now, url)
    for row in [b, *b["series"]]:
        if all(row[k]["value"] is not None for k in ("total", "elderly", "disabled")):
            if (
                row["total"]["value"]
                != row["elderly"]["value"] + row["disabled"]["value"]
            ):
                raise ValueError("BPC: total incoerente")
        if (
            all(
                row[k]["value"] is not None
                for k in ("elderlyValue", "disabledValue", "transferredValue")
            )
            and abs(
                row["elderlyValue"]["value"]
                + row["disabledValue"]["value"]
                - row["transferredValue"]["value"]
            )
            > 0.011
        ):
            raise ValueError("BPC: valores monetários incoerentes")
        if any(row[k]["status"] == "suppressed" for k in ("elderly", "disabled")):
            # Prevent total/other category from revealing suppressed category.
            for k in (
                "total",
                "elderly",
                "disabled",
                "elderlyValue",
                "disabledValue",
                "transferredValue",
            ):
                row[k]["value"] = None
                row[k]["status"] = "suppressed"
                row[k][
                    "note"
                ] = "Supressão complementar para evitar reconstrução de células pequenas."
    b["methodology"] = (
        "BPC pela Fonte Pagadora, reproduzindo o RI. Não misturar com série por município de residência. Valores monetários lidos dos campos decimais _s; aliases float perdem centavos."
    )
    return b, s


def build(
    now,
    monthly_rows,
    monthly_url,
    census,
    census_year,
    census_sources,
    rma,
    rma_source,
    population,
):
    c, cs = cadunico(monthly_rows[CODE], now, monthly_url)
    bf, bs = monthly_block(
        monthly_rows[CODE], mds.BF, "Programa Bolsa Família", now, monthly_url
    )
    bf["methodology"] = (
        "Programa Bolsa Família desde março/2023; nenhuma união com Auxílio Brasil. Transferências federais às famílias, não receita/despesa municipal. Total transferido e benefício médio oficiais desconsideram famílias suspensas na folha; não recalcular a média usando o total de famílias."
    )
    bpc, bpcs = bpc_block(monthly_rows[CODE], now, monthly_url)
    sources = [cs, bs, bpcs, *census_sources]
    refs = [
        r
        for r in monthly_rows[CODE]
        if r.get("cadsuas_data_extracao_s")
        and r.get(mds.NETWORK["cras"]) is not None
        and r.get(mds.NETWORK["creas"]) is not None
    ]
    if not refs:
        raise ValueError("CadSUAS: extração municipal não confirmada")
    latest = max(refs, key=lambda r: r["cadsuas_data_extracao_s"])
    networkref = latest["cadsuas_data_extracao_s"][:10]
    datetime.strptime(networkref, "%Y-%m-%d")
    ns = source(
        "cadsuas",
        "CadSUAS · unidades cadastradas",
        networkref,
        mds.network_url(latest["cadsuas_data_extracao_s"]),
        now,
        {k: latest.get(k) for k in [*mds.NETWORK.values(), "cadsuas_data_extracao_s"]},
    )
    sources.append(ns)
    counts = {
        k: metric(
            mds.numeric(latest.get(field)), "unidades", mds.LABELS[k], networkref, ns
        )
        for k, field in mds.NETWORK.items()
    }
    units = [u for rows in census.values() for u in rows[CODE]]
    # Council archive has no institution identifier; count municipal response only.
    census_counts = {
        k: metric(
            len(rows[CODE]),
            "unidades",
            mds.LABELS[k],
            census_year,
            next(s for s in census_sources if s["id"] == "censo-" + k),
            note="Unidades respondentes ao Censo, não inventário operacional atual.",
        )
        for k, rows in census.items()
    }
    suas = {
        "reference": census_year,
        "units": units,
        "censusCounts": census_counts,
        "cadSuasReference": networkref,
        "cadSuasCounts": counts,
        "note": "CadSUAS e Censo SUAS têm universos/data de extração diferentes. Ausência de resposta ao Censo não comprova inexistência de equipamento. Endereços apenas institucionais; coordenadas não confirmadas, mapa indisponível.",
    }
    services = {
        "reference": rma_source["reference"] if rma_source else None,
        "paif": [],
        "paefi": {
            "value": None,
            "status": "unavailable",
            "note": "[PENDENTE] Validar exportação pública RMA CREAS e proteção de agregados PAEFI antes da integração.",
        },
    }
    if rma_source:
        sources.append(rma_source)
        for r in rma:
            vals = {
                k: metric(
                    r[field],
                    "atendimentos" if k == "individualAttendances" else "famílias",
                    {
                        "accompaniedFamilies": "Famílias em acompanhamento PAIF",
                        "newFamilies": "Novas famílias PAIF",
                        "individualAttendances": "Atendimentos particularizados CRAS",
                    }[k],
                    r["reference"],
                    rma_source,
                )
                for k, field in [
                    ("accompaniedFamilies", "a1"),
                    ("newFamilies", "a2"),
                    ("individualAttendances", "c1"),
                ]
            }
            services["paif"].append(
                {
                    "reference": r["reference"],
                    "reportingUnits": r["reportingUnits"],
                    **vals,
                }
            )
        services["note"] = (
            "RMA CRAS, Base tratada pelo MDS. A1: famílias em acompanhamento no mês; A2: novas famílias; C1: atendimentos particularizados. Não somar A1 mensal como famílias únicas no ano. Ausência/célula retirada na limpeza não equivale a zero. Cobertura restrita aos formulários públicos válidos; sem recortes individuais."
        )
    comparisons = []
    for code, name in mds.MUNICIPALITIES.items():
        # Enforce identical social competence, not independently latest peer data.
        ref = c["reference"]
        r = next((r for r in monthly_rows[code] if r["anomes_s"] == ref), None)
        if not r:
            raise ValueError("Comparação: competência ausente")
        peer, ps = cadunico([r], now, monthly_url, code)
        if code != CODE:
            sources.append(ps)
        p, pop_source = population[code]
        sources.append(pop_source)
        n = peer["people"]["value"]
        d = p
        compatible = pop_source["reference"] == ref[:4] and d and n is not None
        ratio = metric(
            round(n / d * 100, 2) if compatible else None,
            "pessoas por 100 habitantes",
            "Pessoas no CadÚnico por 100 habitantes",
            ref,
            ps,
            code,
            "derived",
            note="Proporção administrativa aproximada, não percentual de pobreza nem cobertura oficial. CadÚnico mensal e estimativa IBGE de 1º de julho do mesmo ano; datas exatas distintas.",
            transformation="pessoas no CadÚnico / população IBGE estimada × 100",
            numerator=n if compatible else None,
            denominator=d if compatible else None,
            numeratorReference=ref,
            denominatorReference=pop_source["reference"],
            denominatorUrl=pop_source["url"],
        )
        comparisons.append(
            {
                "municipalityCode": code,
                "municipalityName": name,
                "reference": ref,
                "families": peer["families"],
                "people": peer["people"],
                "peoplePer100": ratio,
                "cras": (
                    census_counts["cras"]
                    if code == CODE
                    else metric(
                        len(census["cras"][code]),
                        "unidades",
                        "CRAS respondentes Censo SUAS",
                        census_year,
                        next(s for s in census_sources if s["id"] == "censo-cras"),
                        code,
                    )
                ),
            }
        )
    unavailable = [
        {
            "id": k,
            "title": t,
            "value": None,
            "status": "unavailable",
            "url": url,
            "note": reason,
        }
        for k, t, url, reason in [
            (
                "unipersonal",
                "Famílias unipessoais",
                TOOLS,
                "[PENDENTE] Campo público atual com definição e competência confirmadas; não reutilizar campo legado de beneficiários como total cadastrado.",
            ),
            (
                "recentRegistration",
                "Inclusões e atualizações recentes",
                TOOLS,
                "[PENDENTE] Fluxos recentes não são o estoque de cadastros atualizados.",
            ),
            (
                "idcras",
                "IDCRAS",
                IDS,
                "[PENDENTE] Indicador multidimensional de desenvolvimento do CRAS; validar edição, componentes e exportação por unidade.",
            ),
            (
                "idcreas",
                "IDCREAS",
                IDS,
                "[PENDENTE] Validar edição, metodologia e exportação estruturada por unidade.",
            ),
            (
                "idconselho",
                "IDConselho / Conselho Municipal",
                IDS,
                "[PENDENTE] Validar exportação municipal e agregados institucionais, sem diretório de conselheiros.",
            ),
            (
                "ivcad",
                "IVCAD",
                IVCAD,
                "[PENDENTE] Não reproduzir índice familiar nem consultar área identificada; validar agregado municipal público reutilizável.",
            ),
            (
                "territory",
                "Recortes por bairro / grupos específicos",
                TOOLS,
                "[PENDENTE] Sem publicação: exigir agregados seguros, supressão complementar e finalidade estatística; não mapear beneficiários.",
            ),
        ]
    ]
    return {
        "schemaVersion": 1,
        "municipality": {"code": CODE, "name": "Turvo", "state": "PR"},
        "summary": [
            c["families"],
            c["people"],
            bf["families"],
            bf["transferredValue"],
            bpc["total"],
        ],
        "cadunico": c,
        "bolsaFamilia": bf,
        "bpc": bpc,
        "suas": suas,
        "services": services,
        "comparisons": comparisons,
        "sources": sources,
        "collection": {"attemptedAt": now, "failures": []},
        "privacy": {
            "policy": "Apenas estatísticas municipais agregadas e identificação de equipamentos. Contagens de pessoas/famílias/benefícios/atendimentos de 1 a 4 são suprimidas. BPC aplica supressão complementar; sem cruzamentos sociodemográficos, dados individuais ou membros RH. Não somar universos sobrepostos. Arquivos nacionais ficam fora do repositório e do site.",
            "threshold": 5,
            "unavailable": unavailable,
        },
    }


def privacy_check(value, path=()):
    """Reject unknown fields, not just known personal identifiers (fail closed)."""
    # Keys are the complete public schema. name is allowed only for municipality.
    allowed = (
        ROOT_KEYS
        | METRIC_KEYS
        | {
            "code",
            "name",
            "state",
            "reference",
            "families",
            "people",
            "income",
            "id",
            "label",
            "registrationQuality",
            "updated",
            "updatedPercent",
            "notUpdated",
            "series",
            "methodologyBreaks",
            "incomeDefinition",
            "checkedAtEdition",
            "families",
            "transferredValue",
            "averageBenefit",
            "elderly",
            "disabled",
            "total",
            "elderlyValue",
            "disabledValue",
            "methodology",
            "units",
            "censusCounts",
            "cadSuasCounts",
            "cadSuasReference",
            "cras",
            "creas",
            "centroPop",
            "acolhimento",
            "convivencia",
            "centroDia",
            "cadunicoPost",
            "type",
            "institutionName",
            "institutionalAddress",
            "situation",
            "services",
            "coordinates",
            "coordinateNote",
            "paif",
            "paefi",
            "reportingUnits",
            "accompaniedFamilies",
            "newFamilies",
            "individualAttendances",
            "municipalityName",
            "peoplePer100",
            "title",
            "contentHash",
            "archiveHash",
            "resourceYear",
            "variables",
            "policy",
            "threshold",
            "unavailable",
            "attemptedAt",
            "failures",
        }
    )
    if isinstance(value, dict):
        for k, v in value.items():
            if k not in allowed:
                raise ValueError(
                    "Campo não permitido no snapshot social: " + ".".join((*path, k))
                )
            if k == "name" and path != ("municipality",):
                raise ValueError("Nome pessoal bloqueado")
            if k in {"institutionName", "institutionalAddress"} and not (
                len(path) == 3 and path[:2] == ("suas", "units")
            ):
                raise ValueError(
                    "Identificação permitida somente para equipamento SUAS"
                )
            if (
                "value" in value
                and "unit" in value
                and value.get("status") in {"real", "derived"}
                and value["unit"]
                in {"famílias", "pessoas", "benefícios", "atendimentos"}
                and value["value"] is not None
                and 0 < value["value"] < 5
            ):
                raise ValueError("Célula pequena não suprimida")
            privacy_check(v, (*path, k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            privacy_check(v, (*path, str(i)))


def validate(data):
    privacy_check(data)
    if (
        set(data) != ROOT_KEYS
        or data["schemaVersion"] != 1
        or data["municipality"] != {"code": CODE, "name": "Turvo", "state": "PR"}
    ):
        raise ValueError("Schema/município social divergente")
    sources = {s["id"]: s for s in data["sources"]}
    if len(sources) != len(data["sources"]):
        raise ValueError("Fonte duplicada")

    def walk(obj):
        if isinstance(obj, dict):
            if "unit" in obj and "value" in obj:
                if set(obj) - METRIC_KEYS or not METRIC_KEYS.difference(
                    {
                        "numerator",
                        "denominator",
                        "numeratorReference",
                        "denominatorReference",
                        "denominatorUrl",
                    }
                ).issubset(obj):
                    raise ValueError("Metadados do indicador incompletos")
                if (
                    obj["municipalityCode"] not in mds.MUNICIPALITIES
                    or obj["sourceId"] not in sources
                    or not obj["url"].startswith("https://")
                ):
                    raise ValueError("Território/fonte do indicador inválido")
                if obj["status"] not in {
                    "real",
                    "derived",
                    "unavailable",
                    "suppressed",
                }:
                    raise ValueError("Status social inválido")
                v = obj["value"]
                if obj["status"] in {"unavailable", "suppressed"} and v is not None:
                    raise ValueError("Ausência/supressão com valor")
                if obj["status"] in {"real", "derived"} and (
                    not isinstance(v, (float, int))
                    or isinstance(v, bool)
                    or not math.isfinite(v)
                    or v < 0
                ):
                    raise ValueError("Valor social inválido")
                if obj["unit"] == "%" and v is not None and v > 100:
                    raise ValueError("Percentual inválido")
                if (
                    obj["unit"]
                    in {"famílias", "pessoas", "benefícios", "atendimentos", "unidades"}
                    and v is not None
                    and int(v) != v
                ):
                    raise ValueError("Contagem não inteira")
                ref = obj["reference"]
                if not (
                    mds.valid_month(ref)
                    or len(ref) == 4
                    and ref.isdigit()
                    or len(ref) == 10
                    and datetime.strptime(ref, "%Y-%m-%d")
                ):
                    raise ValueError("Referência inválida")
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    seen = set()
    for u in data["suas"]["units"]:
        key = (u["type"], u["id"])
        if (
            key in seen
            or u["municipalityCode"] != CODE
            or u["state"] != "PR"
            or u["coordinates"] is not None
        ):
            raise ValueError("Unidade institucional duplicada/inválida")
        seen.add(key)
    for block in ("cadunico", "bolsaFamilia", "bpc"):
        refs = [r["reference"] for r in data[block]["series"]]
        if refs != sorted(set(refs)):
            raise ValueError("Histórico social duplicado/desordenado")
    for r in data["comparisons"]:
        m = r["peoplePer100"]
        if m["status"] == "derived" and (
            m["denominatorReference"] != m["numeratorReference"][:4]
            or abs(m["value"] - m["numerator"] / m["denominator"] * 100) > 0.011
        ):
            raise ValueError("Proporção/denominador temporal inválido")
    return data


def exports(data, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    fields = [
        "municipalityCode",
        "reference",
        "indicator",
        "value",
        "unit",
        "status",
        "sourceId",
        "url",
        "collectedAt",
        "transformation",
        "note",
    ]
    for filename, key in [
        ("cadunico", "cadunico"),
        ("bolsa-familia", "bolsaFamilia"),
        ("bpc", "bpc"),
        ("services", "services"),
    ]:
        rows = data[key]["paif"] if key == "services" else data[key]["series"]
        with (directory / f"social-{filename}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            for row in rows:
                for cell in row.values():
                    if isinstance(cell, dict) and "unit" in cell:
                        w.writerow({k: cell[k] for k in fields})
            if key == "cadunico":
                for row in data[key]["income"]:
                    for k in ("families", "people"):
                        cell = row[k]
                        w.writerow(
                            {**{k: cell[k] for k in fields}, "indicator": row["label"]}
                        )
                for cell in data[key]["registrationQuality"].values():
                    w.writerow({k: cell[k] for k in fields})
    with (directory / "social-suas.csv").open("w", newline="", encoding="utf-8") as f:
        fields = [
            "municipalityCode",
            "reference",
            "type",
            "id",
            "institutionName",
            "institutionalAddress",
            "situation",
            "sourceId",
        ]
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for row in data["suas"]["units"]:
            w.writerow({k: row[k] for k in fields})


def catalog(data, stage):
    p = Path(stage) / "indicators.json"
    d = read(p, None)
    if not d:
        return
    d["indicators"] = [i for i in d["indicators"] if i["module"] != "social"]
    for identifier, title, c in zip(
        ["cad-families", "cad-people", "bf-families", "bf-transferred", "bpc-total"],
        [
            "Famílias cadastradas no Cadastro Único",
            "Pessoas cadastradas no Cadastro Único",
            "Famílias beneficiárias do Bolsa Família",
            "Valor mensal transferido pelo Bolsa Família",
            "Benefícios BPC · Fonte Pagadora",
        ],
        data["summary"],
    ):
        if c["status"] != "real":
            continue
        d["indicators"].append(
            {
                "id": "social-" + identifier,
                "module": "social",
                "title": title,
                "value": c["value"],
                "unit": c["unit"],
                "source": c["base"],
                "agency": c["agency"],
                "reference": c["reference"],
                "url": c["url"],
                "collectedAt": c["collectedAt"],
                "municipalityCode": CODE,
                "status": "real",
                "series": [{"period": c["reference"], "value": c["value"]}],
                "note": NOTE,
            }
        )
    d["indicators"].sort(key=lambda r: (r["module"], r["id"]))
    atomic_write(p, d)


def update(directory, offline=False, force=False, cache=None):
    directory = Path(directory)
    previous = read(directory / "social.json", None)
    if previous:
        validate(previous)
    if offline:
        if not previous:
            raise ValueError("Snapshot social ausente")
        return previous
    now = datetime.now(timezone.utc).isoformat()
    moment = datetime.now(timezone.utc)
    end = moment.strftime("%Y%m")
    start = f"{moment.year-3}{moment.month:02d}"
    cache = Path(cache or ".mds-cache")
    try:
        monthly_rows, url = mds.monthly(start, end)
        with tempfile.TemporaryDirectory(prefix="turvo-social-catalog-") as temporary:
            path = Path(temporary) / "catalog.html"
            mds.download(mds.CENSO, path, 5_000_000)
            year, resources, rma = mds.resources(path.read_text(encoding="utf-8"))
        census = {}
        sources = []
        # Councils have no NU_IDENTIFICADOR in current open export; leave
        # unavailable until a distinct schema is implemented rather than guessing.
        for kind in (
            "cras",
            "creas",
            "centroPop",
            "acolhimento",
            "convivencia",
            "centroDia",
            "cadunicoPost",
        ):
            if kind not in resources:
                raise ValueError("Censo: tipo não publicado " + kind)
            p, info = mds.acquire(resources[kind], cache, force)
            census[kind] = mds.institutional(
                mds.census_rows(p), kind, year, "censo-" + kind
            )
            sources.append(
                source(
                    "censo-" + kind,
                    "Censo SUAS · " + mds.LABELS[kind],
                    year,
                    resources[kind],
                    now,
                    {c: rows for c, rows in census[kind].items()},
                    archiveHash=info["sha256"],
                    resourceYear=year,
                    variables=[
                        "IBGE",
                        "IBGE7",
                        "UF",
                        "NU_IDENTIFICADOR",
                        "q0_1",
                        "q0_2",
                        "q0_3",
                        "q0_4",
                        "q0_6",
                    ]
                    + (
                        ["q12_13"]
                        if kind == "cras"
                        else ["q12_3"] if kind == "creas" else []
                    ),
                )
            )
        rma_rows = []
        rs = None
        if rma:
            y, u = rma
            p, info = mds.acquire(u, cache, force)
            rma_rows = mds.paif(p, y)
            rs = source(
                "rma-cras",
                "RMA CRAS · Base tratada",
                y,
                u,
                now,
                rma_rows,
                archiveHash=info["sha256"],
                variables=["IBGE", "IBGE7", "UF_A", "ano", "mes", "a1", "a2", "c1"],
            )
        client = IBGE(now)
        population = {}
        ref = mds.latest(monthly_rows[CODE], mds.CAD)["anomes_s"]
        pop_year = ref[:4]
        for code in mds.MUNICIPALITIES:
            try:
                rows = client.aggregate(
                    "population-" + code,
                    "6579",
                    {"9324": ("População residente estimada", "Pessoas")},
                    {},
                    [pop_year],
                    code=code,
                )
                p = rows[0]["value"]
                s = client.sources[-1]
                ps = source(
                    s["id"],
                    "IBGE · Estimativa populacional",
                    pop_year,
                    s["url"],
                    now,
                    rows,
                )
                ps["agency"] = "IBGE"
            except Exception:
                old_source = next(
                    (
                        item
                        for item in (previous or {}).get("sources", [])
                        if item["id"] == "population-" + code
                        and item["reference"] == pop_year
                    ),
                    None,
                )
                old_comparison = next(
                    (
                        item
                        for item in (previous or {}).get("comparisons", [])
                        if item["municipalityCode"] == code
                        and item["peoplePer100"].get("denominatorReference") == pop_year
                    ),
                    None,
                )
                if (
                    old_source
                    and old_comparison
                    and old_comparison["peoplePer100"].get("denominator")
                ):
                    population[code] = (
                        old_comparison["peoplePer100"]["denominator"],
                        copy.deepcopy(old_source),
                    )
                    continue
                p = None
                ps = source(
                    "population-" + code,
                    "IBGE · Estimativa populacional",
                    pop_year,
                    "https://sidra.ibge.gov.br/tabela/6579",
                    now,
                    {"value": None},
                )
                ps["agency"] = "IBGE"
            population[code] = (p, ps)
        data = build(
            now, monthly_rows, url, census, year, sources, rma_rows, rs, population
        )
        if previous:
            # Preserve collection timestamps per unchanged source, then propagate
            # to every cell. Check whole payload before generating any CSV/catalog.
            for s in data["sources"]:
                old = next((o for o in previous["sources"] if o["id"] == s["id"]), None)
                if (
                    old
                    and old["contentHash"] == s["contentHash"]
                    and old["url"] == s["url"]
                    and old["reference"] == s["reference"]
                    and old.get("archiveHash") == s.get("archiveHash")
                ):
                    s["collectedAt"] = old["collectedAt"]
            timestamps = {s["id"]: s["collectedAt"] for s in data["sources"]}

            def propagate(obj):
                if isinstance(obj, dict):
                    if "sourceId" in obj and "collectedAt" in obj:
                        obj["collectedAt"] = timestamps[obj["sourceId"]]
                    for v in obj.values():
                        propagate(v)
                elif isinstance(obj, list):
                    for v in obj:
                        propagate(v)

            propagate(data)
            comparable = copy.deepcopy(data)
            comparable["collection"] = previous["collection"]
            if comparable == previous:
                print(
                    "Assistência Social: sem mudança nas fontes; timestamps preservados."
                )
                return previous
        validate(data)
        from scripts.modules.health import publish

        with tempfile.TemporaryDirectory(prefix="turvo-social-stage-") as temporary:
            stage = Path(temporary)
            if (directory / "indicators.json").exists():
                shutil.copyfile(
                    directory / "indicators.json", stage / "indicators.json"
                )
            atomic_write(stage / "social.json", data)
            exports(data, stage / "exports")
            catalog(data, stage)
            from scripts.check_social_privacy import check_directory

            check_directory(stage)
            publish(stage, directory)
        print("Assistência Social: snapshot municipal validado e publicado.")
        return data
    except Exception as exc:
        print(
            f"Assistência Social: coleta falhou; snapshot anterior preservado ({type(exc).__name__})."
        )
        if previous:
            result = copy.deepcopy(previous)
            result["collection"]["failures"] = [
                f"Fonte social indisponível ou schema divergente: {type(exc).__name__}"
            ]
            return result
        raise
