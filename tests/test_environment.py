"""Confirmed municipal extracts plus deliberately corrupt data; never live network."""

import copy, json, tempfile, unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from shapely.geometry import box, mapping
from scripts.sources import environment as s
from scripts.modules import environment as e
from scripts.common import atomic_write

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    return json.loads((ROOT / "public/data/environment.json").read_text())


def record(**extra):
    return {
        "id": "official-a",
        "lat": "-25",
        "lon": "-51.5",
        "estado": "PARANÁ",
        "municipio": "TURVO",
        "municipio_id": "4127965",
        "data_hora_gmt": "2026-01-02 13:20:00",
        "satelite": "AQUA_M-T",
        "bioma": "Mata Atlântica",
        **extra,
    }


class FireTests(unittest.TestCase):
    def test_only_reference_satellite(self):
        self.assertEqual(
            s.parse_fire([record(satelite="NOAA-20")], "202601")["observations"], []
        )

    def test_homonym_in_sc_excluded(self):
        self.assertEqual(
            s.parse_fire(
                [record(estado="SANTA CATARINA", municipio_id="4218806")], "202601"
            )["observations"],
            [],
        )

    def test_inconsistent_name_code_rejected(self):
        with self.assertRaises(ValueError):
            s.parse_fire([record(municipio="PITANGA")], "202601")

    def test_official_id_dedup_preserves_distinct_same_coordinate(self):
        self.assertEqual(
            len(
                s.parse_fire([record(), record(), record(id="official-b")], "202601")[
                    "observations"
                ]
            ),
            2,
        )

    def test_conflicting_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            s.parse_fire([record(), record(lat="-25.1")], "202601")

    def test_invalid_reference_rejected(self):
        with self.assertRaises(ValueError):
            s.parse_fire([record()], "202602")

    def test_invalid_coordinate_rejected(self):
        with self.assertRaises(ValueError):
            s.parse_fire([record(lat="nan")], "202601")

    def test_empty_export_not_zero(self):
        with self.assertRaises(ValueError):
            s.parse_fire([], "202601")

    def test_future_observation_rejected(self):
        with self.assertRaises(ValueError):
            s.parse_fire([record(data_hora_gmt="2099-01-02 13:20:00")], "209901")

    def test_annual_homonym_filter_and_implicit_reference(self):
        row = {
            "foco_id": "x",
            "lat": "-25",
            "lon": "-51.5",
            "estado": "SANTA CATARINA",
            "municipio": "TURVO",
            "data_pas": "2025-01-02 12:00:00",
        }
        self.assertEqual(s.parse_fire([row], "2025", True)["observations"], [])

    def test_partial_year_has_null_missing_months(self):
        r = {"data": s.parse_fire([record()], "202601")}
        d = e.fire_block([r], "4127965", {"value": 100})
        self.assertFalse(d["currentYear"]["complete"])
        self.assertEqual(d["monthly"][0]["count"], 1)
        self.assertIsNone(d["monthly"][1]["count"])
        self.assertEqual(d["currentYear"]["per1000Km2"], 10)

    def test_future_year_discovers_new_annual_and_monthly_fallback(self):
        class Response:
            def __init__(self, text):
                self.content = text.encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, *args):
                return self.content

        with patch.object(
            s,
            "request",
            side_effect=[
                Response("focos_br_pr_ref_2020.zip"),
                Response(" ".join(f"focos_br_ref_{y}.zip" for y in range(2021, 2026))),
            ],
        ):
            rows = s.fire_items(datetime(2027, 2, 1, tzinfo=timezone.utc))
        self.assertTrue(any(r[0] == "202612" and not r[2] for r in rows))
        self.assertTrue(any(r[0] == "202702" for r in rows))
        self.assertTrue(any(r[0] == "2025" and r[2] for r in rows))

    def test_annual_archive_supersedes_revised_monthly_ids(self):
        annual = {
            "data": {
                "reference": "2025",
                "availableThrough": "2025-12-31",
                "observations": [
                    {
                        "id": "official-a",
                        "municipalityCode": "4127965",
                        "date": "2025-01-02T13:20:00+00:00",
                    }
                ],
            }
        }
        monthly = {
            "data": {
                "reference": "202501",
                "availableThrough": "2025-01-31",
                "observations": [
                    {
                        "id": "reissued-id",
                        "municipalityCode": "4127965",
                        "date": "2025-01-02T13:20:00+00:00",
                    }
                ],
            }
        }
        block = e.fire_block([annual, monthly], "4127965", {"value": 100})
        self.assertEqual(block["annual"][0]["count"], 1)
        self.assertTrue(block["annual"][0]["complete"])


class LandTests(unittest.TestCase):
    def rows(self):
        return [
            {
                "geocode": code,
                "municipality": name,
                "state": "Paraná",
                "biome": "Mata Atlântica",
                "class": 3,
                "y1985": 100,
            }
            for code, name in s.MUNICIPALITIES.items()
        ]

    def parse(self, rows):
        return s.parse_land(
            rows, {"3": {"name": "1.1 Formação Florestal", "color": "#129912"}}, "11"
        )

    def test_official_legend_and_units(self):
        r = self.parse(self.rows())[0]
        self.assertEqual(r["name"], "1.1 Formação Florestal")
        self.assertEqual(r["level"], 2)
        self.assertEqual(r["unit"], "ha")

    def test_homonym_state_rejected(self):
        r = self.rows()
        r[0]["state"] = "Santa Catarina"
        with self.assertRaises(ValueError):
            self.parse(r)

    def test_duplicate_terminal_cell_rejected(self):
        r = self.rows()
        r.append(r[0])
        with self.assertRaises(ValueError):
            self.parse(r)

    def test_missing_year_rejected(self):
        r = self.rows()
        r[0]["y1987"] = 100
        with self.assertRaises(ValueError):
            self.parse(r)

    def test_negative_area_rejected(self):
        r = self.rows()
        r[0]["y1985"] = -1
        with self.assertRaises(ValueError):
            self.parse(r)

    def test_area_tolerance_rejects_units_wrong(self):
        with self.assertRaises(ValueError):
            e.land_block(self.parse(self.rows()), "4127965", {"value": 100})


class GeographyTests(unittest.TestCase):
    def unit(self, code, geometry):
        return {
            "properties": {
                "cd_cnuc": code,
                "nome_uc": code,
                "esfera": "Estadual",
                "categoria": "APA",
                "grupo": "Uso sustentável",
                "org_gestor": "IAT",
                "municipio": "TURVO (PR)",
                "dt_sync": 1,
            },
            "geometry": mapping(geometry),
        }

    def test_uc_clip_union_not_full_area_or_overlap_sum(self):
        b = box(-51.6, -25.1, -51.5, -25)
        u = self.unit("a", box(-51.7, -25.2, -51.4, -24.9))
        v = self.unit("b", b)
        d = s.protected([u, v], b, 500)
        self.assertAlmostEqual(d["unionAreaHa"], d["units"][0]["intersectionHa"])
        self.assertLess(d["unionAreaHa"], sum(r["intersectionHa"] for r in d["units"]))
        self.assertEqual(d["declaredMunicipalityCount"], 2)

    def test_tangent_unit_excluded(self):
        self.assertEqual(
            s.protected(
                [self.unit("a", box(-51.7, -25.2, -51.6, -25.1))],
                box(-51.6, -25.1, -51.5, -25),
                500,
            )["units"],
            [],
        )

    def station(self, code, lon, lat):
        return {
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "Codigo": code,
                "Nome": "Estação",
                "UF": "PARANÁ",
                "Latitude": lat,
                "Longitude": lon,
                "TipoEstacao": "Pluviométrica",
                "Municipio": "TURVO",
                "MunicipioCodigo": 22280700,
                "Operando": "Sim",
                "EstacaoTelemetrica": "Não",
                "ResponsavelSigla": "ANA",
                "Bacia": "PARANÁ",
                "SubBacia": "IVAÍ",
                "Rio": None,
                "DataAlteracao": 1,
            },
        }

    def test_inside_nearby_and_internal_code_not_ibge(self):
        d = s.stations(
            [self.station(1, -51.55, -25.05), self.station(2, -51.49, -25.05)],
            box(-51.6, -25.1, -51.5, -25),
        )
        self.assertEqual([r["location"] for r in d], ["inside", "regional"])
        self.assertEqual(d[0]["sourceMunicipalityCode"], 22280700)

    def test_station_coordinate_discrepancy_rejected(self):
        f = self.station(1, -51.55, -25.05)
        f["properties"]["Latitude"] = -24
        with self.assertRaises(ValueError):
            s.stations([f], box(-51.6, -25.1, -51.5, -25))

    def test_truncated_geographic_response_rejected(self):
        with patch.object(
            s,
            "request_json",
            return_value={"features": [], "exceededTransferLimit": True},
        ):
            with self.assertRaises(ValueError):
                s.geo_query(s.ANA, [-52, -26, -51, -25])


class SnapshotTests(unittest.TestCase):
    def test_real_delivery_valid_and_no_synthetic_missing(self):
        e.validate(snapshot())
        self.assertIsNone(snapshot()["water"]["measurements"]["value"])

    def test_native_excludes_silviculture(self):
        d = snapshot()
        self.assertNotIn(9, d["vegetation"]["nativeCodes"])
        self.assertAlmostEqual(
            d["vegetation"]["nativeAreaHa"],
            sum(
                c["latest"]["areaHa"]
                for c in d["landCover"]["classes"]
                if c["code"] in s.NATIVE_CODES
            ),
        )

    def test_derived_historical_tamper_rejected(self):
        d = snapshot()
        d["landCover"]["history"][0]["native"] += 100
        with self.assertRaises(ValueError):
            e.validate(d)

    def test_percent_tamper_rejected(self):
        d = snapshot()
        d["landCover"]["classes"][0]["series"][0]["sharePercent"] = 100
        with self.assertRaises(ValueError):
            e.validate(d)

    def test_fake_zero_absence_rejected(self):
        d = snapshot()
        d["climate"]["value"] = 0
        with self.assertRaises(ValueError):
            e.validate(d)

    def test_all_sources_failure_preserves_every_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            atomic_write(folder / "environment.json", snapshot())
            atomic_write(folder / "population/turvo.geojson", snapshot()["geometry"])
            for srcfile in (ROOT / "public/data/environment/resources").glob("*.json"):
                atomic_write(
                    folder / "environment/resources" / srcfile.name,
                    json.loads(srcfile.read_text()),
                )
            before = {
                p.relative_to(folder): p.read_bytes() for p in folder.rglob("*.json")
            }
            with patch.object(
                s, "discover_land", side_effect=RuntimeError("indisponível")
            ), patch.object(
                s, "fire_items", side_effect=RuntimeError("indisponível")
            ), patch.object(
                s, "geo_query", side_effect=RuntimeError("indisponível")
            ):
                result = e.update(folder)
            self.assertEqual(len(result["collection"]["failures"]), 4)
            self.assertEqual(
                before,
                {p.relative_to(folder): p.read_bytes() for p in folder.rglob("*.json")},
            )

    def test_exports_have_source_metadata_and_not_national_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            e.exports(snapshot(), tmp)
            for p in Path(tmp, "exports").glob("*.csv"):
                self.assertIn("sourceUrl", p.read_text())
                self.assertIn("collectedAt", p.read_text())

    def test_empty_initial_delivery_is_explicitly_unavailable(self):
        d = e.build({}, snapshot()["geometry"])
        e.validate(d)
        self.assertEqual(d["landCover"]["status"], "unavailable")
        self.assertEqual(d["comparisons"], [])

    def test_no_national_cache_in_public(self):
        with self.assertRaises(ValueError):
            e.update(ROOT / "public/data", cache=ROOT / "public/data/environment/cache")


class ResourceTests(unittest.TestCase):
    def test_http_unchanged_skips_download_and_parser(self):
        class Response:
            headers = {"ETag": "v1", "Content-Length": "2"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            metadata = {"id": "example", "url": "https://official.test/file"}
            old = {
                "data": [1],
                "source": metadata,
                "http": {"ETag": "v1", "Last-Modified": None, "Content-Length": "2"},
            }
            atomic_write(folder / "environment/resources/example.json", old)
            with patch.object(s, "request", return_value=Response()), patch.object(
                s, "download"
            ) as download:
                self.assertEqual(
                    e.resource(
                        folder,
                        folder / "cache",
                        "example",
                        "https://official.test/file",
                        lambda _: self.fail("parser executed"),
                        metadata,
                    ),
                    old,
                )
                download.assert_not_called()

    def test_force_downloads_despite_validator_and_cold_cache_does_not_trust_file(self):
        class Response:
            headers = {"ETag": "v1", "Content-Length": "2"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            cache = folder / "cache"
            cache.mkdir()
            (cache / "example.csv").write_text("xx")

            def download(url, path):
                path.write_text("[]")
                return "digest"

            with patch.object(s, "request", return_value=Response()), patch.object(
                s, "download", side_effect=download
            ) as get:
                e.resource(
                    folder,
                    cache,
                    "example",
                    "https://official.test/file",
                    lambda _: [],
                    {"id": "example", "url": "https://official.test/file"},
                )
                self.assertEqual(get.call_count, 1)
                e.resource(
                    folder,
                    cache,
                    "example",
                    "https://official.test/file",
                    lambda _: [],
                    {"id": "example", "url": "https://official.test/file"},
                    force=True,
                )
                self.assertEqual(get.call_count, 2)

    def test_formal_schema_matches_published_delivery(self):
        import jsonschema

        schema = json.loads((ROOT / "docs/schemas/environment.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(snapshot(), schema)
        invalid = snapshot()
        invalid["water"]["stations"][0]["location"] = "unknown"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)


if __name__ == "__main__":
    unittest.main()
