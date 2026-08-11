-- Plantilla de mínimo privilegio para el Datamart/reporting del módulo 1.8.2.
-- Debe revisarse con Seguridad/DBA CGR antes de ejecutarse. No crea logins.
-- Los principals reales se asignan a estos roles fuera del repositorio.

IF DATABASE_PRINCIPAL_ID(N'CGR_Analisis_ReportReader') IS NULL
    CREATE ROLE CGR_Analisis_ReportReader;
GO

IF DATABASE_PRINCIPAL_ID(N'CGR_Analisis_Publisher') IS NULL
    CREATE ROLE CGR_Analisis_Publisher;
GO

-- SSRS/consumidores: solo vistas estables de reporting.
GRANT SELECT ON OBJECT::dbo.vw_SSRS_Favoritismo TO CGR_Analisis_ReportReader;
GRANT SELECT ON OBJECT::dbo.vw_SSRS_Fraccionamiento TO CGR_Analisis_ReportReader;
GRANT SELECT ON OBJECT::dbo.vw_SSRS_VinculosProveedorFuncionario TO CGR_Analisis_ReportReader;
GO

-- Publicador del pipeline: DML sobre tablas destino; no DDL ni acceso a fuentes SIAF/SEACE.
GRANT SELECT, INSERT, UPDATE, DELETE ON OBJECT::dbo.PrediccionesFavoritismo TO CGR_Analisis_Publisher;
GRANT SELECT, INSERT, UPDATE, DELETE ON OBJECT::dbo.PrediccionesFraccionamiento TO CGR_Analisis_Publisher;
GRANT SELECT, INSERT, UPDATE, DELETE ON OBJECT::dbo.VinculosProveedorFuncionario TO CGR_Analisis_Publisher;
GO

-- Principio operativo recomendado:
-- 1) lectura SIAF/SEACE: identidad distinta, SELECT-only sobre vistas autorizadas;
-- 2) publicación Oro/reporting: miembro de CGR_Analisis_Publisher;
-- 3) SSRS: miembro de CGR_Analisis_ReportReader;
-- 4) DDL/despliegue: identidad DBA/deployment separada y auditada.
