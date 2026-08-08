"""Contratos canónicos de datos para desacoplar fuentes externas del ML.

Los modelos y feature engineering deben depender de estos nombres canónicos,
no de nombres físicos de tablas/columnas de CGR, SIAF, SEACE u otra fuente.

Sprint 1 distingue explícitamente dos usos:
- inference: contratos actuales, sin etiquetas obligatorias;
- training: histórico con ground truth requerido para los modelos entrenables.

`required_*` significa que la columna debe existir. `nullable=False` se reserva
para claves/campos que la capa de integración no puede recuperar de forma
segura. Nulos imputables de negocio (monto, modalidad, objeto) se permiten aquí
y se resuelven o rechazan posteriormente en el quality gate/preprocesamiento.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str
    required_inference: bool = False
    required_training: bool = False
    nullable: bool = True


SCHEMAS: dict[str, tuple[FieldSpec, ...]] = {
    "contracts": (
        FieldSpec("id_contrato", "string", True, True, False),
        FieldSpec("id_proveedor", "string", True, True, False),
        FieldSpec("id_entidad", "string", True, True, False),
        FieldSpec("id_funcionario", "string"),
        # La columna monto debe existir, pero el PoC ya contempla imputación de
        # nulos en preprocesamiento; no se debe rechazar antes de ese quality gate.
        FieldSpec("monto", "number", True, True, True),
        FieldSpec("fecha_contrato", "datetime", True, True, False),
        FieldSpec("modalidad", "string", True, True, True),
        FieldSpec("objeto", "string", True, True, True),
        FieldSpec("categoria_principal", "string"),
        FieldSpec("fecha_actualizacion", "datetime"),
        # Ground truth canónico. Los nombres físicos/sintéticos se adaptan vía mapping.
        FieldSpec("label_favoritismo", "boolean", False, True, False),
        FieldSpec("label_fraccionamiento", "boolean", False, True, False),
    ),
    "suppliers": (
        FieldSpec("id_proveedor", "string", True, True, False),
        FieldSpec("nombre_proveedor", "string"),
        FieldSpec("ruc", "string"),
    ),
    "entities": (
        FieldSpec("id_entidad", "string", True, True, False),
        FieldSpec("nombre_entidad", "string"),
    ),
    "officials": (
        FieldSpec("id_funcionario", "string", True, True, False),
        FieldSpec("id_entidad", "string"),
        FieldSpec("nombre_funcionario", "string"),
        FieldSpec("email", "string"),
        FieldSpec("telefono", "string"),
    ),
    "payments": (
        FieldSpec("id_pago", "string", True, True, False),
        FieldSpec("id_contrato", "string", True, True, False),
        FieldSpec("fecha_devengado", "datetime"),
        FieldSpec("fecha_girado", "datetime"),
        FieldSpec("fecha_pagado", "datetime"),
        FieldSpec("monto_devengado", "number"),
        FieldSpec("monto_pagado", "number"),
        FieldSpec("estado", "string"),
    ),
}


def campos_canonicos(domain: str) -> tuple[str, ...]:
    _validar_dominio(domain)
    return tuple(field.name for field in SCHEMAS[domain])


def campos_requeridos(domain: str, mode: str = "inference") -> tuple[str, ...]:
    _validar_dominio(domain)
    _validar_modo(mode)
    attr = "required_training" if mode == "training" else "required_inference"
    return tuple(field.name for field in SCHEMAS[domain] if getattr(field, attr))


def aplicar_mapping(df: pd.DataFrame, domain: str, mapping: dict[str, str]) -> pd.DataFrame:
    """Renombra columnas físicas al contrato canónico.

    `mapping` usa dirección `campo_canonico: columna_fisica`. Las columnas no
    mapeadas se descartan deliberadamente para evitar acoplamiento accidental.
    """
    _validar_dominio(domain)
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError(f"Mapping vacío o inválido para dominio {domain!r}.")

    canonicos = set(campos_canonicos(domain))
    desconocidos = set(mapping) - canonicos
    if desconocidos:
        raise ValueError(
            f"Campos canónicos desconocidos en mapping {domain!r}: {sorted(desconocidos)}"
        )

    fisicos = list(mapping.values())
    duplicados = sorted({c for c in fisicos if fisicos.count(c) > 1})
    if duplicados:
        raise ValueError(
            f"Una columna física no puede alimentar múltiples campos canónicos: {duplicados}"
        )

    faltantes_fisicos = sorted(set(fisicos) - set(df.columns))
    if faltantes_fisicos:
        raise ValueError(
            f"La fuente {domain!r} no contiene columnas configuradas: {faltantes_fisicos}"
        )

    inverse = {physical: canonical for canonical, physical in mapping.items()}
    return df.loc[:, fisicos].rename(columns=inverse).copy()


def validar_dataframe(
    df: pd.DataFrame,
    domain: str,
    mode: str = "inference",
    *,
    coerce: bool = True,
) -> pd.DataFrame:
    """Valida presencia, tipos básicos y nulabilidad estructural.

    Devuelve una copia tipada. No imputa ni corrige calidad de negocio: esa
    responsabilidad pertenece al preprocesamiento/quality gate posterior.
    """
    _validar_dominio(domain)
    _validar_modo(mode)
    out = df.copy()

    required = set(campos_requeridos(domain, mode))
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError(
            f"Esquema canónico incompleto para {domain!r} ({mode}): faltan {missing}"
        )

    specs = {field.name: field for field in SCHEMAS[domain]}
    for col in out.columns:
        if col not in specs:
            raise ValueError(f"Columna no canónica en {domain!r}: {col!r}")
        if not coerce:
            continue
        spec = specs[col]
        try:
            if spec.kind == "datetime":
                out[col] = pd.to_datetime(out[col], errors="raise")
            elif spec.kind == "number":
                out[col] = pd.to_numeric(out[col], errors="raise")
            elif spec.kind == "boolean":
                out[col] = _coerce_bool(out[col])
            elif spec.kind == "string":
                # Mantiene NA en vez de convertirlo a la cadena "nan".
                out[col] = out[col].astype("string")
        except Exception as exc:  # pandas expone varias excepciones por dtype
            raise ValueError(
                f"No se pudo convertir {domain}.{col} al tipo {spec.kind}: {exc}"
            ) from exc

    for field in SCHEMAS[domain]:
        required_here = field.required_training if mode == "training" else field.required_inference
        if required_here and not field.nullable and field.name in out.columns:
            n_null = int(out[field.name].isna().sum())
            if n_null:
                raise ValueError(
                    f"{domain}.{field.name} contiene {n_null} nulos y es obligatorio en {mode}."
                )

    return out


def columnas_fisicas_necesarias(domain: str, mapping: dict[str, str], mode: str) -> list[str]:
    """Columnas físicas mínimas necesarias para leer un dominio en un modo dado."""
    required = set(campos_requeridos(domain, mode))
    missing_mapping = sorted(required - set(mapping))
    if missing_mapping:
        raise ValueError(
            f"El mapping de {domain!r} no define campos obligatorios para {mode}: {missing_mapping}"
        )
    return list(dict.fromkeys(mapping.values()))


def _coerce_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype("boolean")
    true_values = {True, 1, "1", "true", "t", "si", "sí", "yes", "y"}
    false_values = {False, 0, "0", "false", "f", "no", "n"}

    def conv(value):
        if pd.isna(value):
            return pd.NA
        normalized = value.strip().lower() if isinstance(value, str) else value
        if normalized in true_values:
            return True
        if normalized in false_values:
            return False
        raise ValueError(f"valor booleano no reconocido: {value!r}")

    return series.map(conv).astype("boolean")


def _validar_dominio(domain: str) -> None:
    if domain not in SCHEMAS:
        raise ValueError(f"Dominio desconocido {domain!r}. Válidos: {sorted(SCHEMAS)}")


def _validar_modo(mode: str) -> None:
    if mode not in {"inference", "training"}:
        raise ValueError("mode debe ser 'inference' o 'training'.")
