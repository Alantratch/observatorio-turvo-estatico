"""MDS source contracts and privacy failures, entirely offline.

Official Sep/Aug 2026 municipal fixture contains only permitted aggregates.
Mutations/small counts below are deliberately synthetic validation cases.
"""

import copy, csv, io, json, subprocess, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
from scripts.sources import mds
from scripts.modules import social as s
from scripts.check_social_privacy import check_directory

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-07T12:00:00+00:00"


def data():
    return json.loads((ROOT / "public/data/social.json").read_text())


def fixture():
    return json.loads((ROOT / "tests/fixtures/social/monthly.json").read_text())


def source():
    return s.source(
        "test", "MDS municipal", "202609", "https://example.gov.br", NOW, {}
    )


def monthly_response():
    docs = []
    for code, name in mds.MUNICIPALITIES.items():
        r = copy.deepcopy(fixture()["docs"][-1])
        r.update(
            codigo_ibge=code[:6], municipio=name.upper(), sigla_uf="PR", tipo_s="mes_mu"
        )
        docs.append(r)
    return {"response": {"numFound": len(docs), "start": 0, "docs": docs}}


def unit_row():
    return {
        "IBGE": "412796",
        "IBGE7": "4127965",
        "UF": "PR",
        "NU_IDENTIFICADOR": "41279600945",
        "q0_1": "CRAS - FILADELFIA",
        "q0_2": "Rua",
        "q0_3": "AGENOR ALMEIDA CAMARGO",
        "q0_4": "299",
        "q0_6": "JARDIM FILADELFIA",
        "q12_13": "Sim",
    }


class MdsTests(unittest.TestCase):
    def test_families_people_distinct(self):
        b, _ = s.cadunico(fixture()["docs"], NOW, "https://example.gov.br")
        self.assertEqual(b["families"]["value"], 2995)
        self.assertEqual(b["people"]["value"], 7696)
        self.assertEqual(b["families"]["unit"], "famílias")
        self.assertEqual(b["people"]["unit"], "pessoas")

    def test_income_official_universes(self):
        b, _ = s.cadunico(fixture()["docs"], NOW, "https://example.gov.br")
        self.assertEqual(
            [r["families"]["value"] for r in b["income"]], [889, 853, 1253]
        )
        self.assertEqual(sum(r["people"]["value"] for r in b["income"]), 7696)

    def test_wrong_income_sum_rejected(self):
        rows = fixture()["docs"]
        rows[-1][mds.CAD["lowIncomeFamilies"]] = 999
        with self.assertRaisesRegex(ValueError, "Faixas"):
            s.cadunico(rows, NOW, "https://example.gov.br")

    def test_quality_official_percent(self):
        b, _ = s.cadunico(fixture()["docs"], NOW, "https://example.gov.br")
        q = b["registrationQuality"]
        self.assertEqual(q["updatedPercent"]["value"], 94.02)
        self.assertEqual(q["notUpdated"]["value"], 179)
        self.assertEqual(q["notUpdated"]["status"], "derived")

    def test_confirmed_zero_universe_does_not_impute_missing(self):
        row = copy.deepcopy(fixture()["docs"][-1])
        for field in mds.CAD.values():
            row[field] = 0
        block, _ = s.cadunico([row], NOW, "https://example.gov.br")
        self.assertEqual(block["families"]["value"], 0)
        self.assertEqual(block["registrationQuality"]["updatedPercent"]["value"], 0)

    def test_quality_small_difference_protects_percent_and_complement(self):
        row = copy.deepcopy(fixture()["docs"][-1])
        row[mds.CAD["updated"]] = 2992
        row[mds.CAD["updatedPercent"]] = 99.9
        block, _ = s.cadunico([row], NOW, "https://example.gov.br")
        for cell in block["registrationQuality"].values():
            self.assertEqual(cell["status"], "suppressed")
            self.assertIsNone(cell["value"])

    def test_invalid_quality_rejected(self):
        rows = fixture()["docs"]
        rows[-1][mds.CAD["updatedPercent"]] = 120
        with self.assertRaisesRegex(ValueError, "Percentual"):
            s.cadunico(rows, NOW, "https://example.gov.br")

    def test_quality_numerator_checked(self):
        rows = fixture()["docs"]
        rows[-1][mds.CAD["updatedPercent"]] = 90
        with self.assertRaisesRegex(ValueError, "Taxa"):
            s.cadunico(rows, NOW, "https://example.gov.br")

    def test_families_updated_over_total_rejected(self):
        rows = fixture()["docs"]
        rows[-1][mds.CAD["updated"]] = 3000
        with self.assertRaisesRegex(ValueError, "superiores"):
            s.cadunico(rows, NOW, "https://example.gov.br")

    def test_bolsa_real_values_and_official_average(self):
        b, _ = s.monthly_block(
            fixture()["docs"], mds.BF, "Bolsa Família", NOW, "https://example.gov.br"
        )
        self.assertEqual(b["reference"], "202609")
        self.assertEqual(b["transferredValue"]["value"], 665693)
        self.assertEqual(b["averageBenefit"]["value"], 649.46)
        self.assertNotEqual(round(665693 / 1030, 2), b["averageBenefit"]["value"])

    def test_future_placeholder_not_selected(self):
        rows = fixture()["docs"] + [{"anomes_s": "202612"}]
        self.assertEqual(mds.latest(rows, mds.BF)["anomes_s"], "202609")

    def test_no_auxilio_brasil_bridge(self):
        rows = fixture()["docs"]
        old = copy.deepcopy(rows[-1])
        old["anomes_s"] = "202212"
        rows.append(old)
        b, _ = s.monthly_block(
            rows, mds.BF, "Bolsa Família", NOW, "https://example.gov.br"
        )
        self.assertTrue(all(r["reference"] >= "202303" for r in b["series"]))

    def test_bpc_separate_period_and_publics(self):
        b, _ = s.bpc_block(fixture()["docs"], NOW, "https://example.gov.br")
        self.assertEqual(b["reference"], "202608")
        self.assertEqual(
            (b["elderly"]["value"], b["disabled"]["value"], b["total"]["value"]),
            (128, 196, 324),
        )
        self.assertEqual(b["transferredValue"]["value"], 526828.46)

    def test_bpc_unpublished_zeros_do_not_become_zero(self):
        rows = fixture()["docs"]
        rows[-1]["bpc_ben_i"] = 0
        self.assertEqual(mds.latest(rows, mds.BPC)["anomes_s"], "202608")

    def test_bpc_history_gap_is_null(self):
        b, _ = s.bpc_block(fixture()["docs"], NOW, "https://example.gov.br")
        self.assertTrue(all(r["total"]["value"] is None for r in b["series"][:-1]))

    def test_bpc_sum_failure(self):
        rows = fixture()["docs"]
        rows[0][mds.BPC["total"]] = 999
        with self.assertRaisesRegex(ValueError, "BPC: total"):
            s.bpc_block(rows, NOW, "https://example.gov.br")

    def test_decimal_money_preserves_cents(self):
        self.assertEqual(mds.numeric("319340.15", money=True), 319340.15)

    def test_absence_never_zero(self):
        self.assertIsNone(mds.numeric(None))
        self.assertIsNone(mds.numeric("X"))
        self.assertEqual(mds.numeric("0"), 0)

    def test_invalid_number(self):
        for v in ("NaN", "inf", "-1", "12,45", "text", "2.5"):
            with self.subTest(v=v), self.assertRaises(ValueError):
                mds.numeric(v)

    def test_wrong_turvo_sc_rejected(self):
        r = monthly_response()
        r["response"]["docs"][0]["codigo_ibge"] = "421880"
        with patch.object(mds, "request_json", return_value=r), self.assertRaisesRegex(
            ValueError, "Território"
        ):
            mds.monthly("202608", "202609")

    def test_wrong_uf_rejected(self):
        r = monthly_response()
        r["response"]["docs"][0]["sigla_uf"] = "SC"
        with patch.object(mds, "request_json", return_value=r), self.assertRaisesRegex(
            ValueError, "Território"
        ):
            mds.monthly("202608", "202609")

    def test_missing_peer_rejected(self):
        r = monthly_response()
        r["response"]["docs"].pop()
        r["response"]["numFound"] = 3
        with patch.object(mds, "request_json", return_value=r), self.assertRaisesRegex(
            ValueError, "Município"
        ):
            mds.monthly("202608", "202609")

    def test_truncation_rejected(self):
        r = monthly_response()
        r["response"]["numFound"] = 500
        with patch.object(mds, "request_json", return_value=r), self.assertRaisesRegex(
            ValueError, "truncada"
        ):
            mds.monthly("202608", "202609")

    def test_duplicates_rejected(self):
        r = monthly_response()
        r["response"]["docs"].append(r["response"]["docs"][0])
        r["response"]["numFound"] = 5
        with patch.object(mds, "request_json", return_value=r), self.assertRaisesRegex(
            ValueError, "duplicada"
        ):
            mds.monthly("202608", "202609")

    def test_unknown_personal_api_fields_not_carried(self):
        r = monthly_response()
        r["response"]["docs"][0]["cpf"] = "malicious"
        with patch.object(mds, "request_json", return_value=r):
            rows, _ = mds.monthly("202608", "202609")
        self.assertNotIn("cpf", rows["4127965"][0])

    def test_query_is_explicitly_municipal_and_whitelisted(self):
        from urllib.parse import urlparse, parse_qs

        q = parse_qs(urlparse(mds.monthly_url("202608", "202609")).query)
        self.assertEqual(q["q"], ["*:*"])
        self.assertIn("412796", str(q["fq"]))
        self.assertEqual(set(q["fl"][0].split(",")), mds.FIELDS)

    def test_period_validation(self):
        for p in ("202613", "202600", "2026", "2026-09"):
            self.assertFalse(mds.valid_month(p))

    def test_resource_discovery_does_not_guess_urls(self):
        text = '<a href="https://aplicacoes.mds.gov.br/snas/defeso/censosuas/2025/1_CRAS.zip">CRAS</a><a href="https://evil.example/censosuas/2026/1_CRAS.zip">fake</a>'
        year, urls, _ = mds.resources(text)
        self.assertEqual(year, "2025")
        self.assertEqual(set(urls), {"cras"})

    def test_service_dictionary_future_edition_not_assumed(self):
        with self.assertRaisesRegex(ValueError, "Dicionário"):
            mds.institutional([unit_row()], "cras", "2026", "censo-cras")

    def test_suas_deduplicates_real_unit(self):
        r = unit_row()
        units = mds.institutional([r, r], "cras", "2025", "censo-cras")["4127965"]
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["services"], ["PAIF"])
        self.assertNotIn("nome", units[0])

    def test_suas_conflicting_duplicates_fail(self):
        a = unit_row()
        b = unit_row()
        b["q0_1"] = "Conflicting"
        with self.assertRaisesRegex(ValueError, "divergentes"):
            mds.institutional([a, b], "cras", "2025", "censo-cras")

    def test_suas_uf_rejected(self):
        a = unit_row()
        a["UF"] = "SC"
        with self.assertRaisesRegex(ValueError, "UF"):
            mds.institutional([a], "cras", "2025", "censo-cras")

    def test_suas_rh_file_never_opened(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "units.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr(
                    "Censo_Dados_Gerais.csv",
                    "IBGE;IBGE7;UF;NU_IDENTIFICADOR;q0_1\n412796;4127965;PR;41279600945;CRAS\n",
                )
                z.writestr("RH.csv", b"invalid-byte-\xff")
            rows = list(mds.census_rows(p))
            self.assertEqual(len(rows), 1)

    def test_rma_only_treated_base_and_no_annual_unique_sum(self):
        import openpyxl

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "rma.xlsx"
            w = openpyxl.Workbook()
            ws = w.active
            ws.title = "Base tratada"
            ws.append(
                [
                    "IBGE",
                    "IBGE7",
                    "UF_A",
                    "ano",
                    "mes",
                    "NU_IDENTIFICADOR",
                    "a1",
                    "a2",
                    "c1",
                ]
            )
            ws.append([412796, 4127965, "PR", 2025, 1, "41279600945", 139, 0, 70])
            ws.append([412796, 4127965, "PR", 2025, 2, "41279600945", None, 0, 80])
            w.create_sheet("Base Original").append(["cpf"])
            w.save(p)
            rows = mds.paif(p, "2025")
            self.assertEqual(len(rows), 12)
            self.assertEqual(rows[0]["a1"], 139)
            self.assertIsNone(rows[1]["a1"])
            self.assertIsNone(rows[2]["c1"])


class SocialPrivacyTests(unittest.TestCase):
    def test_official_snapshot_and_exports_valid(self):
        check_directory(ROOT / "public/data")

    def test_schema_turvo_sc_rejected(self):
        d = data()
        d["municipality"]["code"] = "4218806"
        with self.assertRaisesRegex(ValueError, "município"):
            s.validate(d)

    def test_schema_unknown_key_rejected(self):
        d = data()
        d["unknown"] = "arbitrary"
        with self.assertRaisesRegex(ValueError, "permitido"):
            s.validate(d)

    def test_all_personal_fields_fail(self):
        for key in [
            "CPF",
            "cpf",
            "nis",
            "nome",
            "name",
            "telefone",
            "phone",
            "email",
            "endereco_residencial",
            "residentialAddress",
            "data_nascimento",
            "birthDate",
            "prontuario",
            "beneficiarios",
            "familyMembers",
        ]:
            d = data()
            d["cadunico"][key] = "private"
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.validate(d)

    def test_institution_name_only_in_suas(self):
        d = data()
        d["cadunico"]["institutionName"] = "someone"
        with self.assertRaisesRegex(ValueError, "equipamento"):
            s.validate(d)

    def test_unprotected_small_cell_fail(self):
        d = data()
        d["cadunico"]["people"]["value"] = 3
        with self.assertRaisesRegex(ValueError, "pequena"):
            s.validate(d)

    def test_suppressed_original_value_blocked(self):
        d = data()
        c = d["cadunico"]["people"]
        c["status"] = "suppressed"
        c["value"] = 100
        with self.assertRaisesRegex(ValueError, "Supressão|supressão"):
            s.validate(d)

    def test_metric_suppression_has_no_raw_value(self):
        m = s.metric(3, "famílias", "Synthetic test", "202609", source())
        self.assertIsNone(m["value"])
        self.assertEqual(m["status"], "suppressed")
        self.assertNotIn("rawValue", m)

    def test_institution_count_one_is_not_personal_cell(self):
        self.assertEqual(s.metric(1, "unidades", "CRAS", "2025", source())["value"], 1)

    def test_zero_is_not_suppressed(self):
        self.assertEqual(
            s.metric(0, "famílias", "Test", "202609", source())["status"], "real"
        )

    def test_bpc_complementary_suppression(self):
        row = copy.deepcopy(fixture()["docs"][0])
        row.update(
            {mds.BPC["elderly"]: 2, mds.BPC["disabled"]: 196, mds.BPC["total"]: 198}
        )
        b, _ = s.bpc_block([row], NOW, "https://example.gov.br")
        for k in mds.BPC:
            self.assertIsNone(b[k]["value"])
            self.assertEqual(b[k]["status"], "suppressed")

    def test_comparison_denominator_year_fail(self):
        d = data()
        d["comparisons"][0]["peoplePer100"]["denominatorReference"] = "2025"
        with self.assertRaisesRegex(ValueError, "temporal"):
            s.validate(d)

    def test_snapshot_preserved_on_api_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "social.json"
            content = (ROOT / "public/data/social.json").read_bytes()
            p.write_bytes(content)
            with patch.object(mds, "monthly", side_effect=TimeoutError):
                result = s.update(tmp)
            self.assertTrue(result["collection"]["failures"])
            self.assertEqual(p.read_bytes(), content)

    def test_unchanged_publication_retains_timestamps(self):
        from contextlib import ExitStack

        previous = data()
        fresh = copy.deepcopy(previous)
        for src in fresh["sources"]:
            src["collectedAt"] = "2030-01-01T00:00:00Z"
        fresh["collection"]["attemptedAt"] = "2030-01-01T00:00:00Z"
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            p = Path(tmp) / "social.json"
            content = (ROOT / "public/data/social.json").read_bytes()
            p.write_bytes(content)
            stack.enter_context(
                patch.object(
                    mds,
                    "monthly",
                    return_value=(
                        {"4127965": fixture()["docs"]},
                        "https://example.gov.br",
                    ),
                )
            )
            stack.enter_context(
                patch.object(
                    mds,
                    "download",
                    side_effect=lambda u, p, *a: Path(p).write_text("catalog"),
                )
            )
            stack.enter_context(
                patch.object(
                    mds,
                    "resources",
                    return_value=(
                        "2025",
                        {
                            k: "https://example.gov.br"
                            for k in [
                                "cras",
                                "creas",
                                "centroPop",
                                "acolhimento",
                                "convivencia",
                                "centroDia",
                                "cadunicoPost",
                            ]
                        },
                        None,
                    ),
                )
            )
            stack.enter_context(
                patch.object(
                    mds,
                    "acquire",
                    return_value=(Path("not-opened"), {"sha256": "hash"}),
                )
            )
            stack.enter_context(patch.object(mds, "census_rows", return_value=[]))
            stack.enter_context(
                patch.object(
                    mds,
                    "institutional",
                    return_value={c: [] for c in mds.MUNICIPALITIES},
                )
            )
            stack.enter_context(
                patch.object(s.IBGE, "aggregate", side_effect=RuntimeError)
            )
            stack.enter_context(patch.object(s, "build", return_value=fresh))
            result = s.update(tmp)
            self.assertEqual(p.read_bytes(), content)
            self.assertEqual(result, previous)

    def test_offline_never_calls_network(self):
        with patch.object(mds, "monthly", side_effect=AssertionError):
            s.update(ROOT / "public/data", offline=True)

    def test_build_cli_returns_failure_for_personal_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = data()
            d["cadunico"]["cpf"] = "private"
            (Path(tmp) / "social.json").write_text(json.dumps(d))
            result = subprocess.run(
                ["python3", str(ROOT / "scripts/check_social_privacy.py"), tmp],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bloqueada", result.stderr)

    def test_csv_personal_header_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "social.json").write_text(json.dumps(data()))
            s.exports(data(), p / "exports")
            f = p / "exports/social-cadunico.csv"
            f.write_text("cpf\nprivate\n")
            with self.assertRaisesRegex(ValueError, "Campos CSV"):
                check_directory(p)

    def test_csv_cannot_diverge_from_validated_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "social.json").write_text(json.dumps(data()))
            s.exports(data(), p / "exports")
            f = p / "exports/social-cadunico.csv"
            f.write_text(f.read_text().replace("2995", "9999"))
            with self.assertRaisesRegex(ValueError, "diverge"):
                check_directory(p)

    def test_extra_social_raw_file_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "social.json").write_text(json.dumps(data()))
            s.exports(data(), p / "exports")
            (p / "social").mkdir()
            (p / "social/raw.json").write_text('{"cpf":"private"}')
            with self.assertRaisesRegex(ValueError, "fora do contrato"):
                check_directory(p)

    def test_build_runs_privacy_gate_before_vite(self):
        scripts = json.loads((ROOT / "package.json").read_text())["scripts"]
        self.assertTrue(
            scripts["build"].startswith("python3 scripts/check_social_privacy.py &&")
        )
