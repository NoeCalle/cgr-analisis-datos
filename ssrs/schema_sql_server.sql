-- Esquema T-SQL para SQL Server — checklist Anexo 3, ítem 7.
-- PoC: el destino institucional real requiere infraestructura CGR.
-- Las salidas se denominan señales/scores de priorización, no hallazgos.

CREATE TABLE dbo.PrediccionesFavoritismo (
    id_proveedor              NVARCHAR(100)   NOT NULL,
    id_entidad                NVARCHAR(100)   NOT NULL,
    n_contratos               INT             NOT NULL,
    monto_total               DECIMAL(20,2)   NOT NULL,
    pct_contratacion_directa  DECIMAL(6,5)    NOT NULL,
    pct_comparacion_precios   DECIMAL(6,5)    NOT NULL,
    score_riesgo              DECIMAL(10,7)   NOT NULL,
    fecha_calculo             DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_PrediccionesFavoritismo PRIMARY KEY (id_proveedor, id_entidad)
);

CREATE TABLE dbo.PrediccionesFraccionamiento (
    id_proveedor            NVARCHAR(100)   NOT NULL,
    id_entidad              NVARCHAR(100)   NOT NULL,
    objeto                  NVARCHAR(300)   NOT NULL,
    max_contratos_ventana   INT             NOT NULL,
    pct_bajo_umbral         DECIMAL(6,5)    NOT NULL,
    score_anomalia          DECIMAL(18,8)   NOT NULL,
    senal_priorizacion      BIT             NOT NULL,
    fecha_calculo           DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_PrediccionesFraccionamiento PRIMARY KEY (id_proveedor, id_entidad, objeto)
);

CREATE TABLE dbo.VinculosProveedorFuncionario (
    id_proveedor         NVARCHAR(100)   NOT NULL,
    id_funcionario       NVARCHAR(100)   NOT NULL,
    n_contratos          INT             NOT NULL,
    comparte_telefono    BIT             NOT NULL,
    comparte_direccion   BIT             NOT NULL,
    fecha_calculo        DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_VinculosProveedorFuncionario PRIMARY KEY (id_proveedor, id_funcionario)
);

CREATE INDEX IX_Favoritismo_Score
    ON dbo.PrediccionesFavoritismo (score_riesgo DESC);
CREATE INDEX IX_Fraccionamiento_Score
    ON dbo.PrediccionesFraccionamiento (score_anomalia DESC);

-- Ejemplo de Dataset SSRS:
-- SELECT id_proveedor, id_entidad, n_contratos,
--        pct_contratacion_directa, pct_comparacion_precios, score_riesgo
-- FROM dbo.PrediccionesFavoritismo
-- WHERE score_riesgo >= @UmbralMinimo
-- ORDER BY score_riesgo DESC;
