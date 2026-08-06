# Análisis estadístico en R — componente "R" del Anexo 2 del TDR
# ("Lenguajes de programación soportados": Python, SQL, Scala, R, Java).
#
# R es fuerte en estadística inferencial; aquí se usa para un análisis que
# complementa lo ya hecho en Python: pruebas de hipótesis formales sobre
# si los pares proveedor-entidad de alto riesgo tienen medias
# significativamente distintas al resto, algo que en el pipeline Python
# se reportó de forma descriptiva (rankings) pero no como prueba
# estadística formal.

datos <- read.csv("data/dataset_favoritismo.csv")

cat("=== Resumen del dataset (R) ===\n")
cat(sprintf("Filas: %d | Columnas: %d\n", nrow(datos), ncol(datos)))
cat(sprintf("Casos con favoritismo sembrado: %d de %d (%.2f%%)\n\n",
            sum(datos$label_favoritismo_real == "True"),
            nrow(datos),
            100 * mean(datos$label_favoritismo_real == "True")))

# Separar grupos: favoritismo real vs. resto
grupo_favoritismo <- datos[datos$label_favoritismo_real == "True", ]
grupo_normal <- datos[datos$label_favoritismo_real == "False", ]

cat("=== Estadística descriptiva por grupo ===\n")
for (col in c("n_contratos", "concentracion_objeto", "pct_no_competitiva", "monto_total")) {
  cat(sprintf("\n%s:\n", col))
  cat(sprintf("  Favoritismo real  -> media=%.4f, sd=%.4f\n",
              mean(grupo_favoritismo[[col]]), sd(grupo_favoritismo[[col]])))
  cat(sprintf("  Resto             -> media=%.4f, sd=%.4f\n",
              mean(grupo_normal[[col]]), sd(grupo_normal[[col]])))
}

# Prueba t de Welch (no asume varianzas iguales) para concentracion_objeto,
# la variable de mayor importancia según el modelo Random Forest (Sección 3
# del reporte técnico)
cat("\n=== Prueba t de Welch: concentracion_objeto (favoritismo vs. resto) ===\n")
prueba <- t.test(grupo_favoritismo$concentracion_objeto, grupo_normal$concentracion_objeto)
print(prueba)

cat(sprintf("\nConclusión: %s\n",
    ifelse(prueba$p.value < 0.05,
           "diferencia estadísticamente significativa (p < 0.05) — confirma con una prueba formal lo que el modelo Random Forest ya señalaba por importancia de variable.",
           "sin diferencia estadísticamente significativa.")))

# Guardar un gráfico de cajas comparando ambos grupos
png("outputs/charts/13_r_boxplot_concentracion.png", width = 900, height = 600, res = 120)
boxplot(concentracion_objeto ~ label_favoritismo_real, data = datos,
        col = c("#a0aec0", "#c53030"),
        names = c("Resto", "Favoritismo real"),
        main = "Concentracion de objeto contractual por grupo (R)",
        ylab = "concentracion_objeto")
dev.off()

cat("\nGráfico guardado en outputs/charts/13_r_boxplot_concentracion.png\n")
cat("R VERIFICADO: análisis estadístico formal ejecutado sobre los datos del prototipo.\n")
