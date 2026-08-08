#!/usr/bin/env python3
"""Materializa el índice paginado de los DOCX generados con LibreOffice UNO.

El generador Node deja el marcador [[TOC]]. Este script lo reemplaza por un
índice real de capítulos y actualiza sus números de página. También aplica
estilos Arial 11 a los estilos del índice y añade `mirrorMargins` al OOXML para
que el documento quede preparado para impresión a doble cara.

Requiere LibreOffice Writer y python3-uno. En CI se invoca con /usr/bin/python3.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue

ROOT = Path(__file__).resolve().parent
DEFAULT_DOCS = [ROOT / "Reporte_Tecnico_Prototipo_CGR_1.8.2.docx"] + sorted(
    (ROOT / "productos_formales").glob("Producto_*.docx")
)


def prop(nombre, valor):
    p = PropertyValue()
    p.Name = nombre
    p.Value = valor
    return p


def iniciar_libreoffice(profile: Path):
    cmd = [
        shutil.which("soffice") or shutil.which("libreoffice") or "soffice",
        f"-env:UserInstallation={uno.systemPathToFileUrl(str(profile))}",
        "--headless",
        "--norestore",
        "--nodefault",
        "--nolockcheck",
        "--accept=socket,host=localhost,port=2002;urp;StarOffice.ServiceManager",
    ]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def conectar(timeout_s: float = 15.0):
    ctx = uno.getComponentContext()
    resolver = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", ctx
    )
    limite = time.time() + timeout_s
    ultimo = None
    while time.time() < limite:
        try:
            return resolver.resolve(
                "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"
            )
        except Exception as exc:  # pragma: no cover - depende del proceso LO
            ultimo = exc
            time.sleep(0.25)
    raise RuntimeError(f"No se pudo conectar a LibreOffice UNO: {ultimo}")


def normalizar_estilos_indice(doc):
    """Fuerza Arial 11 y espaciado simple en estilos Contents/Index de Writer."""
    try:
        familias = doc.StyleFamilies
        estilos = familias.getByName("ParagraphStyles")
    except Exception:
        return

    for nombre in estilos.getElementNames():
        low = nombre.lower()
        if not ("contents" in low or low.startswith("index")):
            continue
        try:
            estilo = estilos.getByName(nombre)
            if hasattr(estilo, "CharFontName"):
                estilo.CharFontName = "Arial"
            if hasattr(estilo, "CharFontNameAsian"):
                estilo.CharFontNameAsian = "Arial"
            if hasattr(estilo, "CharFontNameComplex"):
                estilo.CharFontNameComplex = "Arial"
            if hasattr(estilo, "CharHeight"):
                estilo.CharHeight = 11.0
            if hasattr(estilo, "CharHeightAsian"):
                estilo.CharHeightAsian = 11.0
            if hasattr(estilo, "CharHeightComplex"):
                estilo.CharHeightComplex = 11.0
            if hasattr(estilo, "ParaTopMargin"):
                estilo.ParaTopMargin = 0
            if hasattr(estilo, "ParaBottomMargin"):
                estilo.ParaBottomMargin = 0
            if hasattr(estilo, "ParaLineSpacing"):
                ls = uno.createUnoStruct("com.sun.star.style.LineSpacing")
                ls.Mode = 0  # FIX
                ls.Height = 100
                estilo.ParaLineSpacing = ls
        except Exception:
            # Un estilo no editable no debe impedir actualizar el documento.
            continue


def insertar_o_actualizar_toc(doc):
    indices = doc.getDocumentIndexes()
    if indices.getCount() > 0:
        for i in range(indices.getCount()):
            indices.getByIndex(i).update()
        return indices.getCount()

    descriptor = doc.createSearchDescriptor()
    descriptor.SearchString = "[[TOC]]"
    encontrado = doc.findFirst(descriptor)
    if not encontrado:
        raise RuntimeError("No se encontró [[TOC]] ni un índice existente")

    encontrado.String = ""
    toc = doc.createInstance("com.sun.star.text.ContentIndex")
    toc.Title = "Índice"
    toc.CreateFromOutline = True
    toc.Level = 3
    doc.Text.insertTextContent(encontrado, toc, False)
    toc.update()
    return 1


def procesar_docx(ctx, ruta: Path):
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL(
        uno.systemPathToFileUrl(str(ruta.resolve())),
        "_blank",
        0,
        (prop("Hidden", True), prop("ReadOnly", False)),
    )
    if doc is None:
        raise RuntimeError(f"LibreOffice no pudo abrir {ruta}")
    try:
        normalizar_estilos_indice(doc)
        n = insertar_o_actualizar_toc(doc)
        doc.store()
        print(f"Índice actualizado ({n}) -> {ruta.name}")
    finally:
        doc.close(True)


def patch_duplex_settings(ruta: Path):
    """Añade mirrorMargins y updateFields al settings.xml sin alterar el contenido."""
    with zipfile.ZipFile(ruta, "r") as zin:
        archivos = {info.filename: zin.read(info.filename) for info in zin.infolist()}

    settings = archivos.get("word/settings.xml")
    if not settings:
        return
    texto = settings.decode("utf-8")
    inserciones = []
    if "<w:mirrorMargins" not in texto:
        inserciones.append("<w:mirrorMargins/>")
    if "<w:updateFields" not in texto:
        inserciones.append('<w:updateFields w:val="true"/>')
    if not inserciones:
        return
    texto = texto.replace("</w:settings>", "".join(inserciones) + "</w:settings>")
    archivos["word/settings.xml"] = texto.encode("utf-8")

    temporal = ruta.with_suffix(".tmp.docx")
    with zipfile.ZipFile(temporal, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for nombre, datos in archivos.items():
            zout.writestr(nombre, datos)
    os.replace(temporal, ruta)


def main(argv: list[str]) -> int:
    rutas = [Path(x) for x in argv] if argv else DEFAULT_DOCS
    rutas = [p if p.is_absolute() else (Path.cwd() / p) for p in rutas]
    faltan = [str(p) for p in rutas if not p.exists()]
    if faltan:
        raise FileNotFoundError("Faltan DOCX para postprocesar: " + ", ".join(faltan))

    with tempfile.TemporaryDirectory(prefix="cgr-lo-profile-") as tmp:
        proceso = iniciar_libreoffice(Path(tmp))
        try:
            ctx = conectar()
            for ruta in rutas:
                procesar_docx(ctx, ruta)
                patch_duplex_settings(ruta)
        finally:
            proceso.terminate()
            try:
                proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proceso.kill()

    print(f"DOCX postprocesados: {len(rutas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
