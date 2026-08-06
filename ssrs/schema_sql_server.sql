-- Esquema T-SQL para SQL Server — checklist Anexo 3, ítem 7:
-- "Integración para Ecosistema SSRS: Resultados del modelo (predicciones
-- y puntajes de riesgo)".
--
-- Este script NO se ejecuta contra un SQL Server real (no hay acceso
-- desde este entorno de prueba de concepto); es el DDL que se ejecutaría
-- en el SQL Server de la CGR (ver Anexo 2: "Servicio SQL Server" recibe
-- los resultados desde el Lakehouse para consumo de SSRS/Power BI). Para
-- demostrar el pipeline de punta a punta, src/publicar_ssrs.py ejecuta
-- este mismo esquema (con tipos equivalentes) sobre SQLite como stand-in
-- local — documentado explícitamente como sustituto, no como el destino
-- real.

CREATE TABLE dbo.PrediccionesFavoritismo (
    id_proveedor        NVARCHAR(10)    NOT NULL,
    id_entidad          NVARCHAR(10)    NOT NULL,
    n_contratos         INT             NOT NULL,
    monto_total         DECIMAL(18,2)   NOT NULL,
    pct_no_competitiva  DECIMAL(5,4)    NOT NULL,
    score_riesgo        DECIMAL(5,4)    NOT NULL,
    fecha_calculo       DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_PrediccionesFavoritismo PRIMARY KEY (id_proveedor, id_entidad)
);

CREATE TABLE dbo.PrediccionesFraccionamiento (
    id_proveedor            NVARCHAR(10)    NOT NULL,
    id_entidad              NVARCHAR(10)    NOT NULL,
    objeto                  NVARCHAR(200)   NOT NULL,
    max_contratos_ventana   INT             NOT NULL,
    pct_bajo_umbral         DECIMAL(5,4)    NOT NULL,
    score_anomalia          DECIMAL(9,4)    NOT NULL,
    cumple_regla_legal      BIT             NOT NULL,
    fecha_calculo           DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_PrediccionesFraccionamiento PRIMARY KEY (id_proveedor, id_entidad, objeto)
);

CREATE TABLE dbo.VinculosProveedorFuncionario (
    id_proveedor        NVARCHAR(10)    NOT NULL,
    id_funcionario       NVARCHAR(10)    NOT NULL,
    n_contratos          INT             NOT NULL,
    comparte_telefono    BIT             NOT NULL,
    comparte_direccion   BIT             NOT NULL,
    fecha_calculo         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_VinculosProveedorFuncionario PRIMARY KEY (id_proveedor, id_funcionario)
);

-- Índices para las consultas típicas de un dataset de SSRS (filtrado por
-- score descendente, que es como un auditor navegaría el reporte)
CREATE INDEX IX_Favoritismo_Score ON dbo.PrediccionesFavoritismo (score_riesgo DESC);
CREATE INDEX IX_Fraccionamiento_Score ON dbo.PrediccionesFraccionamiento (score_anomalia DESC);

-- Consulta de ejemplo que usaría el Dataset compartido en SSRS (parámetro
-- @UmbralMinimo controlado desde el reporte)
-- SELECT id_proveedor, id_entidad, n_contratos, score_riesgo
-- FROM dbo.PrediccionesFavoritismo
-- WHERE score_riesgo >= @UmbralMinimo
-- ORDER BY score_riesgo DESC;
