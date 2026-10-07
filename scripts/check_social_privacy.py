"""Fail builds on personal/unknown fields or unsafe small cells in social exports."""

import csv
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.modules.social import exports, validate


def check_directory(directory):
    directory = Path(directory)
    path = directory / "social.json"
    if not path.exists():
        raise ValueError("Snapshot Assistência Social obrigatório ausente")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data)
    # No extra nested raw files: only the normalized social snapshot and the
    # known aggregate CSV contracts can be published by this module.
    for p in directory.rglob("*"):
        if not p.is_file() or not any(
            part.startswith("social") for part in p.relative_to(directory).parts
        ):
            continue
        if p == path:
            continue
        if p.parent != directory / "exports" or p.name not in {
            "social-cadunico.csv",
            "social-bolsa-familia.csv",
            "social-bpc.csv",
            "social-suas.csv",
            "social-services.csv",
        }:
            raise ValueError("Arquivo social público fora do contrato: " + p.name)
        with p.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fields = set(reader.fieldnames or [])
            expected = (
                {
                    "municipalityCode",
                    "reference",
                    "type",
                    "id",
                    "institutionName",
                    "institutionalAddress",
                    "situation",
                    "sourceId",
                }
                if p.name == "social-suas.csv"
                else {
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
                }
            )
            if fields != expected:
                raise ValueError("Campos CSV sociais fora do contrato")
            for row in reader:
                if row["municipalityCode"] != "4127965":
                    raise ValueError("CSV social de território incorreto")
                if "value" in row:
                    if row["status"] in {"unavailable", "suppressed"} and row["value"]:
                        raise ValueError("Supressão/ausência exposta em CSV")
                    if (
                        row["value"]
                        and row["unit"]
                        in {"famílias", "pessoas", "benefícios", "atendimentos"}
                        and 0 < float(row["value"]) < 5
                    ):
                        raise ValueError("Célula pequena exposta em CSV")
    with tempfile.TemporaryDirectory(prefix="turvo-social-privacy-") as temporary:
        expected = Path(temporary)
        exports(data, expected)
        for generated in expected.iterdir():
            published = directory / "exports" / generated.name
            if (
                not published.exists()
                or published.read_bytes() != generated.read_bytes()
            ):
                raise ValueError(
                    "CSV social diverge do snapshot validado: " + generated.name
                )
    return data


if __name__ == "__main__":
    try:
        check_directory(
            Path(sys.argv[1])
            if len(sys.argv) > 1
            else Path(__file__).resolve().parents[1] / "public/data"
        )
    except Exception as exc:
        print("Publicação social bloqueada: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
    print("Assistência Social: schema, agregados e proteção de dados validados.")
