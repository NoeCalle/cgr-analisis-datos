-- Contrato T-SQL para SQL Server — Anexo 3, ítem 7.
-- PoC independiente: el despliegue institucional requiere infraestructura CGR.
-- Las salidas son señales/scores de priorización, no hallazgos ni determinaciones.

CREATE TABLE dbo.PrediccionesFavoritismo (
    id_proveedor              NVARCHAR(100)   NOT NULL,
    id_entidad                NVARCHAR(100)   NOT NULL,
    n_contratos               INT             NOT NULL,
    monto_total               DECIMAL(20,2)   NOT NULL,
    pct_contratacion_directa  DECIMAL(9,8)    NOT NULL,
    pct_comparacion_precios   DECIMAL(9,8)    NOT NULL,
    score_riesgo              DECIMAL(10,9)   NOT NULL,
    fecha_calculo             DATETIME2(7)    NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_PrediccionesFavoritismo PRIMARY KEY (id_proveedor, id_entidad),
    CONSTRAINT CK_Fav_n_contratos CHECK (n_contratos >= 0),
    CONSTRAINT CK_Fav_monto CHECK (monto_total >= 0),
    CONSTRAINT CK_Fav_pct_cd CHECK (pct_contratacion_directa BETWEEN 0 AND 1),
    CONSTRAINT CK_Fav_pct_cp CHECK (pct_comparacion_precios BETWEEN 0 AND 1),
    CONSTRAINT CK_Fav_score CHECK (score_riesgo BETWEEN 0 AND 1)
);
GO

CREATE TABLE dbo.PrediccionesFraccionamiento (
    id_proveedor            NVARCHAR(100)   NOT NULL,
    id_entidad              NVARCHAR(100)   NOT NULL,
    objeto                  NVARCHAR(300)   NOT NULL,
    max_contratos_ventana   INT             NOT NULL,
    pct_bajo_umbral         DECIMAL(9,8)    NOT NULL,
    score_anomalia          DECIMAL(18,10)  NOT NULL,
    senal_priorizacion      BIT             NOT NULL,
    fecha_calculo           DATETIME2(7)    NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_PrediccionesFraccionamiento PRIMARY KEY (id_proveedor, id_entidad, objeto),
    CONSTRAINT CK_Frac_max_ventana CHECK (max_contratos_ventana >= 0),
    CONSTRAINT CK_Frac_pct_umbral CHECK (pct_bajo_umbral BETWEEN 0 AND 1)
);
GO

CREATE TABLE dbo.VinculosProveedorFuncionario (
    id_proveedor         NVARCHAR(100)   NOT NULL,
    id_funcionario       NVARCHAR(100)   NOT NULL,
    n_contratos          INT             NOT NULL,
    comparte_telefono    BIT             NOT NULL,
    comparte_direccion   BIT             NOT NULL,
    fecha_calculo        DATETIME2(7)    NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_VinculosProveedorFuncionario PRIMARY KEY (id_proveedor, id_funcionario),
    CONSTRAINT CK_Vinc_n_contratos CHECK (n_contratos >= 0)
);
GO

CREATE INDEX IX_Favoritismo_Score
    ON dbo.PrediccionesFavoritismo (score_riesgo DESC)
    INCLUDE (id_proveedor, id_entidad, n_contratos, monto_total);
GO

CREATE INDEX IX_Fraccionamiento_Score
    ON dbo.PrediccionesFraccionamiento (score_anomalia DESC)
    INCLUDE (id_proveedor, id_entidad, objeto, senal_priorizacion);
GO

-- Las vistas constituyen el contrato estable consumido por los RDL.
CREATE OR ALTER VIEW dbo.vw_SSRS_Favoritismo
AS
SELECT
    id_proveedor,
    id_entidad,
    n_contratos,
    monto_total,
    pct_contratacion_directa,
    pct_comparacion_precios,
    score_riesgo,
    fecha_calculo
FROM dbo.PrediccionesFavoritismo;
GO

CREATE OR ALTER VIEW dbo.vw_SSRS_Fraccionamiento
AS
SELECT
    id_proveedor,
    id_entidad,
    objeto,
    max_contratos_ventana,
    pct_bajo_umbral,
    score_anomalia,
    senal_priorizacion,
    fecha_calculo
FROM dbo.PrediccionesFraccionamiento;
GO

-- Dataset de referencia SSRS — Favoritismo:
-- SELECT id_proveedor, id_entidad, n_contratos, monto_total,
--        pct_contratacion_directa, pct_comparacion_precios, score_riesgo
-- FROM dbo.vw_SSRS_Favoritismo
-- WHERE score_riesgo >= @UmbralMinimo
-- ORDER BY score_riesgo DESC;

-- Dataset de referencia SSRS — Fraccionamiento:
-- SELECT id_proveedor, id_entidad, objeto, max_contratos_ventana,
--        pct_bajo_umbral, score_anomalia, senal_priorizacion
-- FROM dbo.vw_SSRS_Fraccionamiento
-- WHERE score_anomalia >= @ScoreMinimo
-- ORDER BY score_anomalia DESC;
