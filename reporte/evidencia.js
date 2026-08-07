const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const RUTA = path.join(ROOT, 'outputs', 'evidencia_documental.json');

if (!fs.existsSync(RUTA)) {
  throw new Error(
    'Falta outputs/evidencia_documental.json. Ejecuta primero: python src/generar_evidencia_documental.py'
  );
}

const e = JSON.parse(fs.readFileSync(RUTA, 'utf8'));

const pct = (v, d = 1) => `${(Number(v) * 100).toFixed(d)}%`;
const num = (v, d = 0) => Number(v).toLocaleString('es-PE', {
  minimumFractionDigits: d,
  maximumFractionDigits: d,
});
const pen = (v, d = 0) => `S/ ${num(v, d)}`;

function modelo(nombre) {
  return e.seleccion_favoritismo.resultados.find((x) => x.modelo === nombre);
}

module.exports = {
  e, pct, num, pen, modelo,
  syn: e.sintetico,
  fav: e.sintetico.favoritismo,
  frac: e.sintetico.fraccionamiento,
  selFav: e.seleccion_favoritismo,
  tuneFav: e.tuning_favoritismo,
  tuneFrac: e.tuning_fraccionamiento,
  p0: e.validacion_datos_publicos,
};
