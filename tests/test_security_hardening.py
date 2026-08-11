"""Regresiones de seguridad y privacidad introducidas en la Etapa 4B."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import generar_datos
import ingestar_canonico
import modelo_grafos
from core.config import validar_config
from core.security_paths import (
    preparar_directorio_candidato,
    validar_artefactos_dentro_del_candidate,
)


def _contracts_mapping():
    return {
        "id_contrato": "ID_CONTRATO",
        "id_proveedor": "ID_PROVEEDOR",
        "id_entidad": "ID_ENTIDAD",
        "monto": "MONTO",
        "fecha_contrato": "FECHA",
        "modalidad": "MODALIDAD",
        "objeto": "OBJETO",
        "categoria_principal": "CATEGORIA",
    }


def test_connection_env_no_acepta_connection_string_disfrazado():
    config = {
        "contract_schema_version": 1,
        "mode": "inference",
        "source": {
            "type": "sqlserver",
            "connection_env": "Driver={ODBC Driver 18 for SQL Server};Server=x;PWD=secret",
            "tables": {"contracts": "dbo.Contratos"},
        },
        "mapping": {"contracts": _contracts_mapping()},
    }
    with pytest.raises(ValueError, match="connection_env.*variable de entorno"):
        validar_config(config)


def test_connection_env_acepta_nombre_de_variable():
    config = {
        "contract_schema_version": 1,
        "mode": "inference",
        "source": {
            "type": "sqlserver",
            "connection_env": "CGR_SOURCE_DATABASE_URL",
            "tables": {"contracts": "dbo.Contratos"},
        },
        "mapping": {"contracts": _contracts_mapping()},
    }
    validar_config(config)


def test_train_solo_limpia_directorios_bajo_root_autorizado(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("CGR_ALLOWED_CANDIDATE_ROOTS", str(runtime))

    manifest = runtime / "model_candidates" / "candidate_manifest.json"
    manifest.parent.mkdir(parents=True)
    marker = manifest.parent / "marker.txt"
    marker.write_text("old", encoding="utf-8")

    normalized_manifest, candidate_dir = preparar_directorio_candidato(manifest)
    assert normalized_manifest == manifest
    assert candidate_dir == manifest.parent
    assert candidate_dir.exists()
    assert not marker.exists()

    with pytest.raises(ValueError, match="fuera de roots autorizados"):
        preparar_directorio_candidato(tmp_path / "outside" / "candidate_manifest.json")

    with pytest.raises(ValueError, match="fuera de roots autorizados"):
        preparar_directorio_candidato(runtime / "candidate_manifest.json")

    with pytest.raises(ValueError, match="se requiere nombre"):
        preparar_directorio_candidato(runtime / "otro" / "manifest.json")


def test_manifest_candidate_rechaza_artefactos_fuera_de_su_directorio(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    manifest = candidate / "candidate_manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    internal = candidate / "model.bin"
    internal.write_bytes(b"ok")
    external = tmp_path / "external.bin"
    external.write_bytes(b"outside")

    validar_artefactos_dentro_del_candidate(
        manifest, {"model": {"path": str(internal)}}
    )
    with pytest.raises(ValueError, match="fuera de su directorio"):
        validar_artefactos_dentro_del_candidate(
            manifest, {"model": {"path": str(external)}}
        )


def test_manifest_candidate_rechaza_symlink_que_escape(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    manifest = candidate / "candidate_manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    external = tmp_path / "external.bin"
    external.write_bytes(b"outside")
    link = candidate / "model.bin"
    try:
        link.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("El filesystem de pruebas no permite symlinks")

    with pytest.raises(ValueError, match="fuera de su directorio"):
        validar_artefactos_dentro_del_candidate(
            manifest, {"model": {"path": str(link)}}
        )


def test_identificadores_y_contactos_sinteticos_son_inequivocos(monkeypatch):
    monkeypatch.setattr(generar_datos, "RNG", np.random.default_rng(123))
    proveedores = generar_datos.generar_proveedores(n=4)
    entidades = generar_datos.generar_entidades(n=2)
    funcionarios = generar_datos.generar_funcionarios(n=4, entidades=entidades)
    assert proveedores["ruc"].str.startswith("SYN-RUC-").all()
    assert funcionarios["dni_funcionario"].str.startswith("SYN-DNI-").all()

    monkeypatch.setattr(modelo_grafos, "RNG", np.random.default_rng(123))
    prov_contacto, func_contacto = modelo_grafos.enriquecer_contacto(
        proveedores[["id_proveedor"]], funcionarios[["id_funcionario"]]
    )
    assert prov_contacto["telefono"].str.startswith("SYN-TEL-").all()
    assert func_contacto["telefono"].str.startswith("SYN-TEL-").all()
    assert prov_contacto["direccion"].str.startswith("SYN-DIR-").all()
    assert func_contacto["direccion"].str.startswith("SYN-DIR-").all()


def test_cli_integracion_no_escribe_preview_por_defecto(monkeypatch, capsys):
    captured = {}
    config = {
        "source": {"type": "local_csv"},
        "mapping": {"contracts": {}},
        "mode": "inference",
    }
    monkeypatch.setattr(ingestar_canonico, "cargar_config", lambda _: config)
    monkeypatch.setattr(ingestar_canonico, "obtener_version_contrato", lambda _: 1)

    def fake_integrar(_config, output_dir=None):
        captured["output_dir"] = output_dir
        return {}, {"source_type": "local_csv", "domains": {}}

    monkeypatch.setattr(ingestar_canonico, "integrar", fake_integrar)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingestar_canonico.py", "--config", "dummy.yaml"],
    )
    ingestar_canonico.main()
    capsys.readouterr()
    assert captured["output_dir"] is None


def test_ci_pr_es_read_only_y_persistencia_esta_segregada():
    tests_yml = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    audit_yml = (ROOT / ".github/workflows/audit-anexo3.yml").read_text(encoding="utf-8")

    assert re.search(r"permissions:\s*\n\s+contents: read", tests_yml)
    assert "git push" not in tests_yml
    assert "persistable-verified-tree" in tests_yml

    assert "github.event.workflow_run.event == 'push'" in audit_yml
    assert "github.event.workflow_run.head_branch == 'main'" in audit_yml
    assert "github.event.workflow_run.head_sha" in audit_yml
    assert "run-id: ${{ github.event.workflow_run.id }}" in audit_yml
    assert "reject-untrusted-source" in audit_yml
    assert re.search(
        r"ssrs-and-checklist:.*?permissions:\s*\n\s+contents: write",
        audit_yml,
        flags=re.S,
    )


def test_todas_las_actions_externas_estan_fijadas_a_sha_inmutable():
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml"))
    assert workflows
    uses_lines = []
    for workflow in workflows:
        for line in workflow.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("uses:"):
                uses_lines.append((workflow.name, stripped))

    assert uses_lines
    bad = [
        f"{name}: {line}"
        for name, line in uses_lines
        if not re.search(r"@[0-9a-f]{40}(?:\s+#.*)?$", line)
    ]
    assert not bad, "Actions no fijadas a SHA:\n" + "\n".join(bad)


def test_sqlserver_reporting_declara_minimo_privilegio_sin_logins():
    ddl = (ROOT / "ssrs/schema_sql_server.sql").read_text(encoding="utf-8")
    roles = (ROOT / "ssrs/security_roles_template.sql").read_text(encoding="utf-8")
    assert "CREATE OR ALTER VIEW dbo.vw_SSRS_VinculosProveedorFuncionario" in ddl
    assert "IX_Vinculos_Compartidos" in ddl
    assert "CGR_Analisis_ReportReader" in roles
    assert "CGR_Analisis_Publisher" in roles
    assert "CREATE LOGIN" not in roles.upper()
    assert "GRANT SELECT ON OBJECT::dbo.vw_SSRS_Favoritismo TO CGR_Analisis_ReportReader" in roles
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON OBJECT::dbo.PrediccionesFavoritismo TO CGR_Analisis_Publisher" in roles
