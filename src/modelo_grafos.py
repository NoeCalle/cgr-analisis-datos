"""
Evaluación de Vínculos por Análisis de Grafos — numeral 4.2.4 del TDR:
"Análisis de grafos o redes para mapear y evaluar relaciones entre
proveedores y funcionarios (ej. por DNI, RUC, direcciones, teléfonos, etc.)"

Este módulo NO estaba en las 6 entregas originales (paso 1-6); se agrega
como mejora porque era la brecha más señalada frente al alcance completo
del TDR.

Enfoque:
  1. Se enriquecen proveedores y funcionarios con datos de contacto
     sintéticos (teléfono, dirección) — en producción vendrían de RENIEC/
     SUNAT/RNP, no existen en SIAF/SEACE por sí solos.
  2. Se siembran deliberadamente 5 "vínculos impropios": pares
     proveedor-funcionario que comparten teléfono y/o dirección (señal
     típica de una empresa fachada controlada por el propio funcionario
     o un familiar).
  3. Se construye un grafo bipartito (proveedores ↔ funcionarios) a
     partir de los contratos reales, y se marca cada arista según si
     comparte datos de contacto.
  4. Se valida qué proporción de los vínculos sembrados el método
     recupera, igual que en los pasos 4 y 5.
"""

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

RNG = np.random.default_rng(7)

DISTRITOS = ["San Isidro", "Miraflores", "Surco", "San Borja", "La Molina",
             "Jesús María", "Lince", "Magdalena", "Pueblo Libre", "Barranco"]
VIAS = ["Av. Los Álamos", "Jr. Las Begonias", "Av. La Marina", "Calle Los Pinos",
        "Av. Javier Prado", "Jr. Cusco", "Av. Arequipa", "Calle Las Camelias"]


def enriquecer_contacto(proveedores, funcionarios):
    """Agrega teléfono y dirección sintéticos. Estos SÍ existirían en
    producción vía cruces con RENIEC/SUNAT/RNP; aquí se simulan porque
    SIAF/SEACE no los traen por defecto."""
    proveedores = proveedores.copy()
    funcionarios = funcionarios.copy()

    proveedores["telefono"] = [f"9{RNG.integers(10000000, 99999999)}" for _ in range(len(proveedores))]
    proveedores["direccion"] = [f"{RNG.choice(VIAS)} {RNG.integers(100,999)}, {RNG.choice(DISTRITOS)}"
                                 for _ in range(len(proveedores))]

    funcionarios["telefono"] = [f"9{RNG.integers(10000000, 99999999)}" for _ in range(len(funcionarios))]
    funcionarios["direccion"] = [f"{RNG.choice(VIAS)} {RNG.integers(100,999)}, {RNG.choice(DISTRITOS)}"
                                  for _ in range(len(funcionarios))]
    return proveedores, funcionarios


def sembrar_vinculos_impropios(contratos, proveedores, funcionarios, n_casos=5):
    """Fuerza que n_casos pares proveedor-funcionario (que ya tienen
    contratos entre sí) compartan teléfono y/o dirección — el patrón que
    debería encender una alerta."""
    pares = contratos.groupby(["id_proveedor", "id_funcionario"]).size().reset_index(name="n")
    pares = pares[pares["n"] >= 2]  # solo pares con relación repetida, más creíble
    elegidos = pares.sample(n=min(n_casos, len(pares)), random_state=7)

    proveedores = proveedores.set_index("id_proveedor")
    funcionarios = funcionarios.set_index("id_funcionario")
    casos = []
    for _, row in elegidos.iterrows():
        p, f = row["id_proveedor"], row["id_funcionario"]
        comparte_tel = bool(RNG.random() < 0.7)
        if comparte_tel:
            proveedores.loc[p, "telefono"] = funcionarios.loc[f, "telefono"]
        else:
            proveedores.loc[p, "direccion"] = funcionarios.loc[f, "direccion"]
        casos.append({"id_proveedor": p, "id_funcionario": f, "label_vinculo_real": True})

    return proveedores.reset_index(), funcionarios.reset_index(), pd.DataFrame(casos)


def construir_grafo(contratos, proveedores, funcionarios):
    """Grafo bipartito proveedor-funcionario a partir de los contratos
    realmente ejecutados; cada arista se etiqueta si comparte teléfono o
    dirección (la señal operativa del numeral 4.2.4)."""
    edges = contratos.groupby(["id_proveedor", "id_funcionario"]).agg(
        n_contratos=("id_contrato", "count"), monto_total=("monto", "sum"),
    ).reset_index()

    tel_prov = proveedores.set_index("id_proveedor")["telefono"]
    dir_prov = proveedores.set_index("id_proveedor")["direccion"]
    tel_func = funcionarios.set_index("id_funcionario")["telefono"]
    dir_func = funcionarios.set_index("id_funcionario")["direccion"]

    edges["comparte_telefono"] = edges.apply(
        lambda r: tel_prov.get(r["id_proveedor"]) == tel_func.get(r["id_funcionario"]), axis=1)
    edges["comparte_direccion"] = edges.apply(
        lambda r: dir_prov.get(r["id_proveedor"]) == dir_func.get(r["id_funcionario"]), axis=1)
    edges["vinculo_sospechoso"] = edges["comparte_telefono"] | edges["comparte_direccion"]

    G = nx.Graph()
    for p in proveedores["id_proveedor"]:
        G.add_node(p, tipo="proveedor")
    for f in funcionarios["id_funcionario"]:
        G.add_node(f, tipo="funcionario")
    for _, r in edges.iterrows():
        G.add_edge(r["id_proveedor"], r["id_funcionario"],
                    n_contratos=r["n_contratos"], monto_total=r["monto_total"],
                    sospechoso=r["vinculo_sospechoso"])
    return G, edges


def validar(edges, casos_reales):
    marcados = edges[edges["vinculo_sospechoso"]]
    print(f"Vínculos impropios sembrados: {len(casos_reales)}")
    print(f"Aristas marcadas por comparte_telefono/direccion: {len(marcados)}")

    reales_set = set(zip(casos_reales["id_proveedor"], casos_reales["id_funcionario"]))
    marcados_set = set(zip(marcados["id_proveedor"], marcados["id_funcionario"]))
    aciertos = reales_set & marcados_set
    print(f"Aciertos: {len(aciertos)}/{len(reales_set)} "
          f"(precisión de la señal: {len(aciertos)/len(marcados_set)*100 if marcados_set else 0:.1f}%)")
    return aciertos


def graficar(G, edges, casos_reales, top_n_contexto=25):
    """Dibuja el subgrafo de: todas las aristas sospechosas + una muestra
    de aristas normales como contexto (mostrar las ~3,600 aristas reales
    sería ilegible)."""
    sospechosas = edges[edges["vinculo_sospechoso"]]
    contexto = edges[~edges["vinculo_sospechoso"]].sample(
        n=min(top_n_contexto, len(edges)), random_state=7)
    sub_edges = pd.concat([sospechosas, contexto])

    Gs = nx.Graph()
    for _, r in sub_edges.iterrows():
        Gs.add_node(r["id_proveedor"], tipo="proveedor")
        Gs.add_node(r["id_funcionario"], tipo="funcionario")
        Gs.add_edge(r["id_proveedor"], r["id_funcionario"], sospechoso=r["vinculo_sospechoso"])

    pos = nx.spring_layout(Gs, seed=7, k=0.6)
    colores_nodo = ["#c53030" if Gs.nodes[n]["tipo"] == "funcionario" else "#2b6cb0" for n in Gs.nodes]
    colores_arista = ["#e53e3e" if Gs.edges[e]["sospechoso"] else "#cbd5e0" for e in Gs.edges]
    anchos = [3.0 if Gs.edges[e]["sospechoso"] else 0.6 for e in Gs.edges]

    fig, ax = plt.subplots(figsize=(9, 7))
    nx.draw_networkx_nodes(Gs, pos, node_color=colores_nodo, node_size=140, ax=ax, alpha=0.9)
    nx.draw_networkx_edges(Gs, pos, edge_color=colores_arista, width=anchos, ax=ax)

    # Solo etiquetar los nodos involucrados en vínculos sospechosos (evita saturar)
    nodos_sospechosos = set(sospechosas["id_proveedor"]) | set(sospechosas["id_funcionario"])
    labels = {n: n for n in nodos_sospechosos}
    nx.draw_networkx_labels(Gs, pos, labels=labels, font_size=8, ax=ax)

    leyenda = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2b6cb0", markersize=9, label="Proveedor"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#c53030", markersize=9, label="Funcionario"),
        Line2D([0], [0], color="#e53e3e", lw=3, label="Vínculo sospechoso (comparte tel./dirección)"),
        Line2D([0], [0], color="#cbd5e0", lw=1, label="Relación contractual normal (muestra)"),
    ]
    ax.legend(handles=leyenda, loc="upper left", fontsize=8, frameon=True)
    ax.set_title("Red Proveedor–Funcionario\nVínculos sospechosos resaltados (numeral 4.2.4 del TDR)")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig("outputs/charts/10_grafo_vinculos.png", dpi=130)
    plt.close()


def main():
    contratos = pd.read_csv("data/contratos_siaf_seace.csv", parse_dates=["fecha_contrato"])
    proveedores = pd.read_csv("data/proveedores.csv")
    funcionarios = pd.read_csv("data/funcionarios.csv")

    proveedores, funcionarios = enriquecer_contacto(proveedores, funcionarios)
    proveedores, funcionarios, casos_reales = sembrar_vinculos_impropios(contratos, proveedores, funcionarios)

    proveedores.to_csv("data/proveedores_contacto.csv", index=False)
    funcionarios.to_csv("data/funcionarios_contacto.csv", index=False)

    G, edges = construir_grafo(contratos, proveedores, funcionarios)
    edges.to_csv("outputs/ranking_vinculos_proveedor_funcionario.csv", index=False)

    print(f"Grafo construido: {G.number_of_nodes()} nodos "
          f"({len(proveedores)} proveedores + {len(funcionarios)} funcionarios), "
          f"{G.number_of_edges()} aristas (relaciones contractuales).")

    validar(edges, casos_reales)
    graficar(G, edges, casos_reales)

    print("\n--- Vínculos sospechosos detectados ---")
    print(edges[edges["vinculo_sospechoso"]][
        ["id_proveedor", "id_funcionario", "n_contratos", "comparte_telefono", "comparte_direccion"]
    ].to_string(index=False))
    print("\nGráfico guardado en outputs/charts/10_grafo_vinculos.png")


if __name__ == "__main__":
    main()
