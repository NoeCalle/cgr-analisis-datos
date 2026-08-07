# Análisis estadístico en R — componente R del Anexo 2 del TDR.
# PoC sintético: análisis descriptivo/inferencial complementario, no validación
# independiente del modelo ni evidencia de desempeño productivo.

ruta <- "lakehouse/plata/dataset_favoritismo.csv"
if (!file.exists(ruta)) {
  stop("No existe lakehouse/plata/dataset_favoritismo.csv; ejecutar el DAG o publicar Plata primero.")
}
datos <- read.csv(ruta)

cat("=== Resumen del dataset Plata (R) ===\n")
cat(sprintf("Filas: %d | Columnas: %d\n", nrow(datos), ncol(datos)))

# read.csv puede interpretar booleanos como TRUE/FALSE lógicos o texto según
# la versión/archivo. Normalizamos explícitamente.
label <- as.character(datos$label_favoritismo_real) %in% c("True", "TRUE", "1")
grupo_favoritismo <- datos[label, ]
grupo_normal <- datos[!label, ]
cat(sprintf("Casos sembrados: %d de %d (%.2f%%)\n\n",
            nrow(grupo_favoritismo), nrow(datos), 100 * mean(label)))

cat("=== Estadística descriptiva por grupo ===\n")
columnas <- c(
  "n_contratos",
  "concentracion_objeto",
  "pct_contratacion_directa",
  "pct_comparacion_precios",
  "monto_total"
)
for (col in columnas) {
  cat(sprintf("\n%s:\n", col))
  cat(sprintf("  Casos sembrados -> media=%.4f, sd=%.4f\n",
              mean(grupo_favoritismo[[col]]), sd(grupo_favoritismo[[col]])))
  cat(sprintf("  Resto           -> media=%.4f, sd=%.4f\n",
              mean(grupo_normal[[col]]), sd(grupo_normal[[col]])))
}

cat("\n=== Prueba t de Welch: concentracion_objeto ===\n")
prueba <- t.test(
  grupo_favoritismo$concentracion_objeto,
  grupo_normal$concentracion_objeto
)
print(prueba)
cat(sprintf(
  "\nInterpretación PoC: p=%.6g. Esta prueba describe diferencia entre grupos sintéticos; no valida causalidad ni generalización del modelo.\n",
  prueba$p.value
))

png("outputs/charts/13_r_boxplot_concentracion.png", width=900, height=600, res=120)
boxplot(
  concentracion_objeto ~ label,
  data=datos,
  names=c("Resto", "Caso sembrado"),
  main="Concentración de objeto contractual por grupo sintético (R)",
  ylab="concentracion_objeto"
)
dev.off()
cat("R verificado como análisis complementario sobre la capa Plata del PoC.\n")
