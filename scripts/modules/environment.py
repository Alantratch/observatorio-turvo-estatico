"""Modular static environment ETL. Each failed source keeps its validated delivery."""

import copy
import csv
import hashlib
import io
import json
import math
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scripts.common import atomic_write, read, preserve_collection_times, request_json
from scripts.modules.health import publish
from scripts.sources import environment as src

CODE = "4127965"
ROOT = Path(__file__).resolve().parents[2]


def missing(reason, url, unit=None):
    return {
        "status": "unavailable",
        "value": None,
        "reference": None,
        "collectedAt": None,
        "unit": unit,
        "url": url,
        "reason": reason,
    }


def resource(
    directory, cache, identifier, url, parser, metadata, bootstrap=None, force=False
):
    """Conditional source checks keep small normalized extracts, never national files."""
    target = directory / "environment/resources" / f"{identifier}.json"
    old = read(target, None)
    with src.request(url, "HEAD") as response:
        signature = {
            k: response.headers.get(k)
            for k in ["ETag", "Last-Modified", "Content-Length"]
        }
    has_validator = signature["ETag"] or signature["Last-Modified"]
    if (
        not force
        and old
        and has_validator
        and old.get("http") == signature
        and all(
            old["source"].get(k) == metadata.get(k)
            for k in ["url", "collection", "version"]
        )
    ):
        return old
    path = cache / (
        identifier
        + (".zip" if url.endswith(".zip") or "drive.usercontent" in url else ".csv")
    )
    if bootstrap and Path(bootstrap).exists() and not path.exists():
        shutil.copyfile(bootstrap, path)
    manifest = read(path.with_suffix(path.suffix + ".manifest.json"), None)
    if (
        force
        or not path.exists()
        or manifest != signature
        or (old is not None and old.get("http") != signature)
    ):
        digest = src.download(url, path)
    else:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if signature["Content-Length"] and path.stat().st_size != int(
            signature["Content-Length"]
        ):
            raise ValueError("Arquivo local não corresponde ao tamanho oficial")
    atomic_write(path.with_suffix(path.suffix + ".manifest.json"), signature)
    payload = parser(path)
    if identifier == "land":
        years = sorted(payload["rows"][0]["years"])
        metadata = {**metadata, "reference": years[0] + "–" + years[-1]}
    candidate = {
        "data": payload,
        "source": {**metadata, "sha256": digest},
        "http": signature,
    }
    candidate = preserve_collection_times(candidate, old)
    atomic_write(target, candidate)
    # Cache may be explicitly retained outside public/data; runners use disposable directories.
    return candidate


def area(code):
    url = f"https://servicodados.ibge.gov.br/api/v1/pesquisas/indicadores/29167/resultados/{code}"
    data = request_json(url)
    if (
        len(data) != 1
        or data[0]["id"] != 29167
        or len(data[0]["res"]) != 1
        or data[0]["res"][0]["localidade"] != code[:-1]
    ):
        raise ValueError("Área IBGE: município/indicador divergente")
    rows = data[0]["res"][0]["res"]
    reference = max(rows)
    value = src.valid_number(rows[reference])
    if value <= 0:
        raise ValueError("Área municipal nula")
    return {
        "value": value,
        "unit": "km²",
        "reference": reference,
        "url": url,
        "municipalityCode": code,
    }


def land_block(rows, code, denominator):
    selected = [r for r in rows if r["municipalityCode"] == code]
    years = sorted(selected[0]["years"])
    classes = {}
    for row in selected:
        item = classes.setdefault(
            row["code"],
            {
                k: row[k]
                for k in [
                    "code",
                    "name",
                    "level",
                    "hierarchy",
                    "color",
                    "collection",
                    "unit",
                ]
            },
        )
        item.setdefault("series", {year: 0.0 for year in years})
        for year in years:
            item["series"][year] += row["years"][year]
    totals = {year: sum(c["series"][year] for c in classes.values()) for year in years}
    denominator_ha = denominator["value"] * 100
    if any(
        abs(total - denominator_ha) / denominator_ha > 0.02 for total in totals.values()
    ):
        raise ValueError("Área classificada diverge mais de 2% do IBGE")
    result = []
    for item in classes.values():
        item["series"] = [
            {
                "year": year,
                "areaHa": value,
                "sharePercent": value / denominator_ha * 100,
            }
            for year, value in item["series"].items()
        ]
        item["latest"] = item["series"][-1]
        result.append(item)
    history = []
    for year in years:
        values = {
            key: 0.0
            for key in [
                "native",
                "forest",
                "farming",
                "farmingWithoutPlantation",
                "plantation",
                "urban",
                "water",
                "pasture",
                "agriculture",
            ]
        }
        for c in result:
            value = next(r["areaHa"] for r in c["series"] if r["year"] == year)
            prefix = c["hierarchy"]
            identifier = c["code"]
            if identifier in src.NATIVE_CODES:
                values["native"] += value
            if prefix.startswith("1."):
                values["forest"] += value
            if prefix.startswith("3."):
                values["farming"] += value
            if prefix.startswith("3.") and identifier != 9:
                values["farmingWithoutPlantation"] += value
            if prefix.startswith("3.2."):
                values["agriculture"] += value
            for key, match in [
                ("plantation", 9),
                ("urban", 24),
                ("water", 33),
                ("pasture", 15),
            ]:
                if identifier == match:
                    values[key] += value
        history.append({"year": year, **values})
    return {
        "status": "real",
        "reference": years[-1],
        "classes": sorted(result, key=lambda c: c["code"]),
        "history": history,
        "mappedAreaHa": totals[years[-1]],
        "municipalArea": denominator,
        "areaDifferencePercent": (totals[years[-1]] / denominator_ha - 1) * 100,
        "shareMethodology": "Percentuais derivados: área em ha / (área territorial IBGE em km² × 100). Soma pode diferir de 100% até 2% por limites/raster; classes terminais sem somar pais novamente.",
    }


def fire_block(resources, code, denominator):
    records = {}
    references = set()
    through = None
    for r in resources:
        data = r["data"]
        references.add(data["reference"])
        through = max(through or data["availableThrough"], data["availableThrough"])
        for observation in data["observations"]:
            if observation["municipalityCode"] == code:
                key = observation["id"]
                if key in records and records[key] != observation:
                    raise ValueError("ID INPE conflitante entre arquivos")
                records[key] = observation
    years = sorted({ref[:4] for ref in references})
    annual = []
    monthly = []
    for year in years:
        covered = [
            f"{year}{m:02d}" in references or year in references for m in range(1, 13)
        ]
        year_through = max(
            r["data"]["availableThrough"]
            for r in resources
            if r["data"]["reference"].startswith(year)
        )
        complete = all(covered) and (
            year in references or year_through >= year + "-12-31"
        )
        year_records = [r for r in records.values() if r["date"].startswith(year)]
        annual.append(
            {
                "year": year,
                "count": len(year_records),
                "complete": complete,
                "coverageMonths": sum(covered),
                "through": f"{year}-12-31" if complete else year_through,
                "per1000Km2": len(year_records) / denominator["value"] * 1000,
            }
        )
        for month in range(1, 13):
            period = f"{year}-{month:02d}"
            count = (
                sum(r["date"].startswith(period) for r in year_records)
                if covered[month - 1]
                else None
            )
            monthly.append(
                {"period": period, "count": count, "available": covered[month - 1]}
            )
    # Snapshot current year is explicitly partial; don't compare it as a complete annual total.
    current = str(datetime.now(timezone.utc).year)
    if current in years:
        annual[-1]["complete"] = False
        annual[-1]["through"] = through
    return {
        "status": "real",
        "reference": through,
        "satellite": src.SATELLITE,
        "annual": annual,
        "monthly": monthly,
        "currentYear": next((r for r in annual if r["year"] == current), None),
        "previousYear": next(
            (r for r in annual if r["year"] == str(int(current) - 1)), None
        ),
        "points": sorted(
            [r for r in records.values() if r["date"][:4] >= str(int(max(years)) - 1)],
            key=lambda r: (r["date"], r["id"]),
        ),
        "normalization": {
            "status": "derived",
            "formula": "focos / área IBGE em km² × 1000",
            "denominator": denominator,
        },
        "methodology": "AQUA_M-T / MODIS, satélite de referência. Focos são detecções térmicas, não incêndios individuais ou hectares queimados. Ano atual parcial. Dados podem ser revisados; ausência de detecção não comprova ausência de fogo. Aviso INPE de falta de imageamento em 12/08/2026.",
        "methodologyUrl": "https://data.inpe.br/queimadas/pages/secao_informacoes/faq/index.html",
    }


def build(resources, boundary, previous=None):
    data = (
        copy.deepcopy(previous)
        if previous
        else {
            "schemaVersion": 1,
            "municipality": {"code": CODE, "name": "Turvo", "state": "PR"},
            "summary": {},
            "sources": [],
            "comparisons": [],
        }
    )
    land_resource = resources.get("land")
    fire_resources = [r for key, r in resources.items() if key.startswith("fire-")]
    if land_resource:
        rows = land_resource["data"]["rows"]
        areas = land_resource["data"]["areas"]
        own = land_block(rows, CODE, areas[CODE])
        data["landCover"] = own
        data["vegetation"] = {
            "status": "derived",
            "reference": own["reference"],
            "nativeCodes": sorted(src.NATIVE_CODES),
            "nativeAreaHa": own["history"][-1]["native"],
            "forestAreaHa": own["history"][-1]["forest"],
            "plantationAreaHa": own["history"][-1]["plantation"],
            "methodology": "Soma explícita de classes vegetadas nativas 3,4,5,6,7,49,11,12,77,84,50. Exclui silvicultura (9), agropecuária, apicum e afloramento rochoso. Indicador derivado do Observatório, sem inferir desmatamento ilegal.",
        }
        data["comparisons"] = [
            {
                "municipalityCode": code,
                "name": name,
                "landCover": land_block(rows, code, areas[code]),
            }
            for code, name in src.MUNICIPALITIES.items()
        ]
        if fire_resources:
            for peer in data["comparisons"]:
                peer["fire"] = fire_block(
                    fire_resources,
                    peer["municipalityCode"],
                    areas[peer["municipalityCode"]],
                )
            data["fire"] = fire_block(fire_resources, CODE, areas[CODE])
    if "water" in resources:
        data["water"] = {**resources["water"]["data"], "status": "real"}
    if "protection" in resources:
        data["protectedAreas"] = resources["protection"]["data"]
    for key in ["landCover", "vegetation", "fire", "water", "protectedAreas"]:
        data.setdefault(
            key,
            missing(
                "Fonte ainda não coletada e validada.",
                {
                    "landCover": src.MAP_PORTAL,
                    "vegetation": src.MAP_PORTAL,
                    "fire": src.FIRE_PORTAL,
                    "water": src.ANA,
                    "protectedAreas": src.UC,
                }[key],
            ),
        )
    data["climate"] = missing(
        "Histórico de temperatura e precipitação ainda sem exportação pública validada de estação. Previsão meteorológica não é histórico.",
        "https://portal.inmet.gov.br/dadoshistoricos",
    )
    data["burnedArea"] = missing(
        "Focos não medem área queimada. Integração municipal de MapBiomas Fogo/AQ1km ainda pendente.",
        "https://brasil.mapbiomas.org/iniciativas/fogo/",
        "ha",
    )
    data["deforestation"] = missing(
        "PRODES/DETER da Amazônia Legal não se aplica automaticamente a Turvo; produto para Mata Atlântica ainda não integrado.",
        "https://terrabrasilis.dpi.inpe.br/",
    )
    data["geometry"] = boundary
    sources = [r["source"] for r in resources.values()]
    data["sources"] = sorted(sources, key=lambda s: s["id"])
    if land_resource:
        latest = data["landCover"]["history"][-1]
        ha = data["landCover"]["municipalArea"]["value"] * 100
        ref = latest["year"]
        data["summary"] = {
            key: {
                "value": latest[key],
                "sharePercent": latest[key] / ha * 100,
                "unit": "ha",
                "reference": ref,
                "status": "derived",
                "sourceId": "land",
            }
            for key in [
                "native",
                "forest",
                "farming",
                "farmingWithoutPlantation",
                "plantation",
                "urban",
                "water",
            ]
        }
    return data


def validate(data):
    if data["schemaVersion"] != 1 or data["municipality"] != {
        "code": CODE,
        "name": "Turvo",
        "state": "PR",
    }:
        raise ValueError("Schema/município ambiental inválido")
    for key in [
        "landCover",
        "vegetation",
        "fire",
        "water",
        "protectedAreas",
        "climate",
        "burnedArea",
        "deforestation",
    ]:
        block = data[key]
        if block["status"] not in {"real", "derived", "unavailable"}:
            raise ValueError("Estado inválido")
        if block["status"] == "unavailable" and block.get("value") is not None:
            raise ValueError("Ausência não é zero")
    if data["landCover"]["status"] == "real":
        peers = data["comparisons"]
        if {p["municipalityCode"] for p in peers} != set(src.MUNICIPALITIES):
            raise ValueError("Comparação municipal incompleta")
        for block in [data["landCover"]] + [p["landCover"] for p in peers]:
            ids = [c["code"] for c in block["classes"]]
            if len(ids) != len(set(ids)):
                raise ValueError("Classes duplicadas")
            denom = src.valid_number(block["municipalArea"]["value"]) * 100
            if denom <= 0:
                raise ValueError("Área municipal inválida")
            years = [p["year"] for p in block["history"]]
            if (
                not years
                or years != [str(y) for y in range(1985, int(years[-1]) + 1)]
                or block["reference"] != years[-1]
            ):
                raise ValueError("Histórico ambiental incompleto")
            collections = {c["collection"] for c in block["classes"]}
            if len(collections) != 1:
                raise ValueError("Coleções misturadas")
            for c in block["classes"]:
                if (
                    c["unit"] != "ha"
                    or c["level"] != len(c["hierarchy"].split("."))
                    or not c["name"].startswith(c["hierarchy"])
                ):
                    raise ValueError("Classe/unidade/hierarquia inválida")
                if [r["year"] for r in c["series"]] != years or c["latest"] != c[
                    "series"
                ][-1]:
                    raise ValueError("Série de classe incompleta")
            derived_rows = [
                {
                    "municipalityCode": CODE,
                    "biome": "validated",
                    "years": {r["year"]: r["areaHa"] for r in c["series"]},
                    **{
                        k: c[k]
                        for k in [
                            "code",
                            "name",
                            "level",
                            "hierarchy",
                            "color",
                            "collection",
                            "unit",
                        ]
                    },
                }
                for c in block["classes"]
            ]
            rebuilt = land_block(derived_rows, CODE, block["municipalArea"])
            if (
                rebuilt["history"] != block["history"]
                or abs(rebuilt["mappedAreaHa"] - block["mappedAreaHa"]) > 1e-6
            ):
                raise ValueError("Agregação de classes divergente")
            for c in block["classes"]:
                for point in c["series"]:
                    if (
                        abs(point["sharePercent"] - point["areaHa"] / denom * 100)
                        > 1e-7
                    ):
                        raise ValueError("Percentual incorreto")
        native = data["landCover"]["history"][-1]["native"]
        plantation = data["landCover"]["history"][-1]["plantation"]
        if 9 in data["vegetation"]["nativeCodes"] or data["vegetation"][
            "nativeCodes"
        ] != sorted(src.NATIVE_CODES):
            raise ValueError("Silvicultura não é vegetação nativa")
        if (
            native != data["vegetation"]["nativeAreaHa"]
            or plantation != data["vegetation"]["plantationAreaHa"]
        ):
            raise ValueError("Resumo de vegetação divergente")
    if data["fire"]["status"] == "real":
        for annual in data["fire"]["annual"]:
            if annual["count"] != sum(
                r["count"] or 0
                for r in data["fire"]["monthly"]
                if r["period"].startswith(annual["year"])
            ):
                raise ValueError("Focos anuais/mensais divergentes")
    for block in [data["fire"]] + [
        p["fire"] for p in data.get("comparisons", []) if "fire" in p
    ]:
        if block["status"] != "real":
            continue
        seen = set()
        for row in block["monthly"]:
            if row["available"] != (row["count"] is not None):
                raise ValueError("Mês ausente convertido em zero")
            if row["count"] is not None and (
                type(row["count"]) is not int or row["count"] < 0
            ):
                raise ValueError("Contagem INPE inválida")
        for point in block["points"]:
            if (
                point["id"] in seen
                or point["satellite"] != src.SATELLITE
                or point["municipalityCode"] not in src.MUNICIPALITIES
            ):
                raise ValueError("Identidade INPE inválida")
            seen.add(point["id"])
            if datetime.fromisoformat(point["date"]) > datetime.now(timezone.utc):
                raise ValueError("Data INPE futura")
            if not (-27 < point["latitude"] < -22 and -55 < point["longitude"] < -48):
                raise ValueError("Coordenada INPE inválida")
    if data["water"]["status"] == "real":
        from shapely.geometry import shape, Point

        boundary = shape(data["geometry"]["features"][0]["geometry"])
        seen = set()
        for station in data["water"]["stations"]:
            if station["code"] in seen or station["type"] not in {
                "Pluviométrica",
                "Fluviométrica",
            }:
                raise ValueError("Estação inválida")
            seen.add(station["code"])
            inside = boundary.covers(Point(station["longitude"], station["latitude"]))
            if inside != (station["location"] == "inside") or station[
                "location"
            ] not in {"inside", "regional"}:
                raise ValueError("Localização ANA divergente")
    if data["protectedAreas"]["status"] == "derived":
        block = data["protectedAreas"]
        union = src.valid_number(block["unionAreaHa"])
        total = sum(src.valid_number(u["intersectionHa"]) for u in block["units"])
        if union > total + 1e-6 or (
            data["landCover"]["status"] == "real"
            and abs(
                block["sharePercent"]
                - union / (data["landCover"]["municipalArea"]["value"] * 100) * 100
            )
            > 1e-7
        ):
            raise ValueError("União/percentual UC inválido")
        if block["declaredMunicipalityCount"] != sum(
            u["registryMentionsTurvo"] for u in block["units"]
        ):
            raise ValueError("Cadastro UC divergente")
    for source in data["sources"]:
        if (
            not source["url"].startswith("https://")
            or not source["agency"]
            or not source["reference"]
            or not source["collectedAt"]
        ):
            raise ValueError("Metadados ambientais ausentes")
    json.dumps(data, allow_nan=False)


def exports(data, directory):
    directory = Path(directory) / "exports"
    directory.mkdir(parents=True, exist_ok=True)
    land_rows = [
        {
            "municipalityCode": p["municipalityCode"],
            "municipality": p["name"],
            "classCode": c["code"],
            "className": c["name"],
            "level": c["level"],
            "collection": c["collection"],
            **r,
        }
        for p in data.get("comparisons", [])
        for c in p["landCover"]["classes"]
        for r in c["series"]
    ]
    fire_rows = [
        {
            "municipalityCode": p["municipalityCode"],
            "municipality": p["name"],
            "satellite": src.SATELLITE,
            **r,
        }
        for p in data.get("comparisons", [])
        for r in p.get("fire", {}).get("monthly", [])
    ]
    water_rows = [
        {k: v for k, v in r.items() if k != "geometry"}
        for r in data["water"].get("stations", [])
    ]
    protection_rows = [
        {k: v for k, v in r.items() if k != "geometry"}
        for r in data["protectedAreas"].get("units", [])
    ]
    for name, rows in [
        ("land-cover", land_rows),
        ("fire", fire_rows),
        ("water", water_rows),
        ("protected-areas", protection_rows),
    ]:
        identifiers = {
            "land-cover": "land",
            "water": "water",
            "protected-areas": "protection",
        }
        for row in rows:
            identifier = identifiers.get(name) or (
                "fire-" + row["period"].replace("-", "")
                if any(
                    s["id"] == "fire-" + row["period"].replace("-", "")
                    for s in data["sources"]
                )
                else "fire-" + row["period"][:4]
            )
            source = next((s for s in data["sources"] if s["id"] == identifier), None)
            row.update(
                {
                    "sourceAgency": source["agency"] if source else "INPE",
                    "sourceUrl": source["url"] if source else src.FIRE_PORTAL,
                    "reference": source["reference"] if source else row.get("period"),
                    "collectedAt": source["collectedAt"] if source else None,
                    "unit": (
                        "ha"
                        if name in {"land-cover", "protected-areas"}
                        else "focos de calor" if name == "fire" else "estações"
                    ),
                }
            )
        out = io.StringIO()
        fields = list(rows[0]) if rows else ["status", "reason"]
        writer = csv.DictWriter(out, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(
            rows
            or [
                {"status": "unavailable", "reason": "Sem dados validados nesta entrega"}
            ]
        )
        (directory / f"environment-{name}.csv").write_text(
            "\ufeff" + out.getvalue(), encoding="utf-8"
        )


def catalog(data, directory):
    path = Path(directory) / "indicators.json"
    current = read(path, None)
    if not current:
        return
    current["indicators"] = [
        r
        for r in current["indicators"]
        if r["module"] not in {"environment", "procurement"}
    ]
    if data["landCover"]["status"] == "real":
        source = next(s for s in data["sources"] if s["id"] == "land")
        for code, title in [
            (3, "Área de Formação Florestal"),
            (9, "Área de Silvicultura"),
            (24, "Área Urbanizada"),
            (33, "Área de Rio, Lago e Oceano"),
        ]:
            item = next(
                (c for c in data["landCover"]["classes"] if c["code"] == code), None
            )
            if not item:
                continue
            current["indicators"].append(
                {
                    "id": f"environment-class-{code}",
                    "module": "environment",
                    "title": title,
                    "value": item["latest"]["areaHa"],
                    "unit": "ha",
                    "source": f'MapBiomas · Coleção {source["collection"]}',
                    "agency": "Rede MapBiomas",
                    "reference": item["latest"]["year"],
                    "url": source["url"],
                    "collectedAt": source["collectedAt"],
                    "municipalityCode": CODE,
                    "status": "real",
                    "series": [
                        {"period": r["year"], "value": r["areaHa"]}
                        for r in item["series"]
                    ],
                    "note": f'Classe {code}: {item["name"]}. Área classificada, não produção econômica ou desmatamento.',
                }
            )
    current["indicators"].sort(key=lambda r: (r["module"], r["id"]))
    atomic_write(path, current)


def update(directory, offline=False, source="all", cache=None, force=False):
    from shapely.geometry import shape

    directory = Path(directory)
    path = directory / "environment.json"
    previous = read(path, None)
    if offline:
        if previous is None:
            raise ValueError("Snapshot ambiental ausente")
        validate(previous)
        return previous
    cache_path = Path(cache) if cache else None
    if cache_path and (
        cache_path.resolve() == directory.resolve()
        or directory.resolve() in cache_path.resolve().parents
    ):
        raise ValueError("Cache nacional deve ficar fora de public/data")
    now = datetime.now(timezone.utc).isoformat()
    failures = []
    geometry = read(directory / "population/turvo.geojson", None)
    if not geometry:
        raise ValueError("Malha IBGE municipal ausente")
    boundary = shape(geometry["features"][0]["geometry"])
    if not boundary.is_valid:
        raise ValueError("Malha inválida")
    with tempfile.TemporaryDirectory(
        prefix="turvo-env-cache-"
    ) as temp, tempfile.TemporaryDirectory(prefix="turvo-env-stage-") as staging:
        cache_path = cache_path or Path(temp)
        cache_path.mkdir(parents=True, exist_ok=True)
        stage = Path(staging)
        if (directory / "environment/resources").exists():
            shutil.copytree(
                directory / "environment/resources", stage / "environment/resources"
            )
        if source in {"all", "land"}:
            try:
                collection, url, download_url = src.discover_land()

                def parse(p):
                    return {
                        "rows": src.land(p, collection),
                        "areas": {code: area(code) for code in src.MUNICIPALITIES},
                    }

                metadata = src.source(
                    "land",
                    "Rede MapBiomas",
                    "Cobertura e uso da terra · Landsat 30m",
                    url,
                    "1985–" + str(datetime.now(timezone.utc).year - 1),
                    now,
                    "ha",
                    collection=collection,
                    version=collection,
                    license="CC BY 4.0",
                    catalogUrl=src.MAP_PORTAL,
                    transformation="Filtro por código IBGE; classes da legenda oficial; soma por município/classe quando houver mais de um bioma. Percentuais e agregações são derivados.",
                )
                resource(
                    stage,
                    cache_path,
                    "land",
                    download_url,
                    parse,
                    metadata,
                    force=force,
                )
            except Exception as exc:
                failures.append("MapBiomas: " + str(exc))
        if source in {"all", "fire"}:
            fire_stage = stage / "environment/resources"
            backup = read_resources(stage)
            try:
                for ref, url, annual in src.fire_items(datetime.now(timezone.utc)):
                    meta = src.source(
                        "fire-" + ref,
                        "INPE",
                        "Programa Queimadas — satélite de referência",
                        url,
                        ref,
                        now,
                        "focos de calor",
                        satellite=src.SATELLITE,
                        catalogUrl=src.FIRE_PORTAL,
                        transformation="Filtro código IBGE (mensal) ou nome+UF (anual de referência); somente AQUA_M-T; deduplicação pelo ID oficial; UTC.",
                    )
                    resource(
                        stage,
                        cache_path,
                        "fire-" + ref,
                        url,
                        lambda p, ref=ref, annual=annual: src.fire(p, ref, annual),
                        meta,
                        force=force,
                    )
            except Exception as exc:
                # A missing month must never produce a current-year zero or incomplete total.
                for p in fire_stage.glob("fire-*.json"):
                    p.unlink()
                for key, value in backup.items():
                    if key.startswith("fire-"):
                        atomic_write(fire_stage / (key + ".json"), value)
                failures.append("INPE: " + str(exc))
        if source in {"all", "water"}:
            try:
                bounds = list(boundary.bounds)
                bounds = [
                    bounds[0] - 0.15,
                    bounds[1] - 0.15,
                    bounds[2] + 0.15,
                    bounds[3] + 0.15,
                ]
                fields = "Codigo,Nome,TipoEstacao,Operando,Latitude,Longitude,Municipio,MunicipioCodigo,UF,Bacia,SubBacia,Rio,ResponsavelSigla,EstacaoTelemetrica,DataAlteracao"
                features, url = src.geo_query(src.ANA, bounds, fields, "UF='PARANÁ'")
                payload = {
                    "stations": src.stations(features["features"], boundary),
                    "measurements": missing(
                        "Endpoint Hidroweb consultado exige autenticação (401). Cadastro telemétrico não garante acesso público a medições. Nível, vazão e chuva não foram estimados.",
                        "https://www.snirh.gov.br/hidroweb/rest/api/estacao/telemetrica",
                    ),
                    "methodology": "Dentro do município = ponto na malha IBGE 2022; referência regional = fora da malha, até 50 km do centroide, dez mais próximas. MunicipioCodigo é identificador interno ANA, não código IBGE. Cadastro não é medição e Operando é declaração do inventário.",
                }
                old = read(stage / "environment/resources/water.json", None)
                candidate = {
                    "data": payload,
                    "source": src.source(
                        "water",
                        "ANA",
                        "Inventário de estações hidrometeorológicas SNIRH",
                        url,
                        "Cadastro consultado; datas próprias por estação",
                        now,
                        "estações",
                        municipalityCodes=[CODE],
                        transformation=payload["methodology"],
                    ),
                }
                atomic_write(
                    stage / "environment/resources/water.json",
                    preserve_collection_times(candidate, old),
                )
            except Exception as exc:
                failures.append("ANA: " + str(exc))
        if source in {"all", "protection"}:
            try:
                features, url = src.geo_query(
                    src.UC,
                    boundary.bounds,
                    "uc_id,cd_cnuc,nome_uc,esfera,categoria,grupo,municipio,org_gestor,dt_sync",
                )
                payload = src.protected(
                    features["features"], boundary, area(CODE)["value"]
                )
                biomes, biome_url = src.geo_query(
                    src.BIOME, boundary.bounds, "bioma,cd_bioma"
                )
                hits = [
                    f["properties"]["bioma"]
                    for f in biomes["features"]
                    if shape(f["geometry"]).intersection(boundary).area > 0
                ]
                payload["biomes"] = sorted(set(hits))
                payload["biomeSourceUrl"] = biome_url
                payload["biomeReference"] = (
                    "Base IBGE 1:250.000 disponibilizada pelo IBAMA; edição não informada no serviço."
                )
                old = read(stage / "environment/resources/protection.json", None)
                candidate = {
                    "data": payload,
                    "source": src.source(
                        "protection",
                        "MMA / CNUC · IBAMA (serviço de distribuição)",
                        "Poligonais CNUC e biomas IBGE",
                        url,
                        "Sincronização "
                        + datetime.fromtimestamp(
                            max(
                                (
                                    f["properties"]["dt_sync"]
                                    for f in features["features"]
                                ),
                                default=int(
                                    datetime.now(timezone.utc).timestamp() * 1000
                                ),
                            )
                            / 1000,
                            timezone.utc,
                        )
                        .date()
                        .isoformat(),
                        now,
                        "ha; unidades",
                        municipalityCodes=[CODE],
                        transformation=payload["methodology"],
                        biomeUrl=biome_url,
                    ),
                }
                atomic_write(
                    stage / "environment/resources/protection.json",
                    preserve_collection_times(candidate, old),
                )
            except Exception as exc:
                failures.append("CNUC/IBGE: " + str(exc))
        resources = read_resources(stage)
        candidate = build(resources, geometry, previous)
        candidate["collection"] = {
            "attemptedAt": now,
            "lastSuccessAt": (
                now
                if not failures
                else (
                    previous.get("collection", {}).get("lastSuccessAt")
                    if previous
                    else None
                )
            ),
            "failures": [],
            "policy": "Fontes independentes, transação por publicação. Arquivo INPE faltante preserva todo o bloco Fogo. Falhas ficam no log; snapshot anterior não é substituído por zero.",
        }
        if failures:
            print("\n".join("FALHA " + failure for failure in failures))
            # Publish successful independent sources only if a first viable land dataset exists.
        validate(candidate)
        candidate = preserve_collection_times(candidate, previous)
        if candidate is not previous:
            if (directory / "indicators.json").exists():
                shutil.copyfile(
                    directory / "indicators.json", stage / "indicators.json"
                )
            atomic_write(stage / "environment.json", candidate)
            exports(candidate, stage)
            catalog(candidate, stage)
            publish(stage, directory)
            print("Meio Ambiente: snapshot validado publicado.")
        else:
            print("Meio Ambiente: sem alterações; nenhum timestamp atualizado.")
        result = copy.deepcopy(candidate)
        result["collection"]["failures"] = failures
        return result


def read_resources(directory):
    return {
        p.stem: read(p, None)
        for p in sorted((Path(directory) / "environment/resources").glob("*.json"))
    }
