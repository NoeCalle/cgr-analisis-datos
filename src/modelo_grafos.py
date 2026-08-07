"""
Análisis de vínculos proveedor–funcionario — numeral 4.2.4 del TDR.

PoC sintético: crea un grafo bipartito a partir de contratos y siembra pares
que comparten teléfono o dirección para comprobar la lógica. En un entorno
institucional esos atributos provendrían de fuentes autorizadas; no se deben
inferir de datos abiertos inexistentes.

P1: consume contratos/dimensiones desde Plata y publica allí los datasets de
contacto enriquecidos para que GraphFrames use exactamente la misma entrada.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from rutas_datos import PLATA, entrada_plata

RNG = np.random.default_rng(7)
DISTRITOS = [
    "San Isidro", "Miraflores", "Surco", "San Borja", "La Molina",
    "Jesús María", "Lince", "Magdalena", "Pueblo Libre", "Barranco",
]
VIAS = [
    "Av. Los Álamos", "Jr. Las Begonias", "Av. La Marina", "Calle Los Pinos",
    "Av. Javier Prado", "Jr. Cusco", "Av. Arequipa", "Calle Las Camelias",
]


def enriquecer_contacto(proveedores, funcionarios):
    proveedores = proveedores.copy()
    funcionarios = funcionarios.copy()
    proveedores["telefono"] = [f"9{RNG.integers(10000000, 99999999)}" for _ in range(len(proveedores))]
    proveedores["direccion"] = [
        f"{RNG.choice(VIAS)} {RNG.integers(100,999)}, {RNG.choice(DISTRITOS)}"
        for _ in range(len(proveedores))
    ]
    funcionarios["telefono"] = [f"9{RNG.integers(10000000, 99999999)}" for _ in range(len(funcionarios))]
    funcionarios["direccion"] = [
        f"{RNG.choice(VIAS)} {RNG.integers(100,999)}, {RNG.choice(DISTRITOS)}"
        for _ in range(len(funcionarios))
    ]
    return proveedores, funcionarios


def sembrar_vinculos(contratos, proveedores, funcionarios, n_casos=5):
    pares = contratos.groupby(["id_proveedor", "id_funcionario"]).size().reset_index(name="n")
    pares = pares[pares["n"] >= 2]
    elegidos = pares.sample(n=min(n_casos, len(pares)), random_state=7)

    proveedores = proveedores.set_index("id_proveedor")
    funcionarios = funcionarios.set_index("id_funcionario")
    casos = []
    for _, row in elegidos.iterrows():
        p, f = row["id_proveedor"], row["id_funcionario"]
        if RNG.random() < 0.7:
            proveedores.loc[p, "telefono"] = funcionarios.loc[f, "telefono"]
        else:
            proveedores.loc[p, "direccion"] = funcionarios.loc[f, "direccion"]
        casos.append((p, f))
    return proveedores.reset_index(), funcionarios.reset_index(), set(casos)


def construir_edges(contratos, proveedores, funcionarios):
    edges = contratos.groupby(["id_proveedor", "id_funcionario"]).agg(
        n_contratos=("id_contrato", "count"), monto_total=("monto", "sum")
    ).reset_index()
    p = proveedores.set_index("id_proveedor")
    f = funcionarios.set_index("id_funcionario")

    edges["comparte_telefono"] = [
        p.at[prov, "telefono"] == f.at[func, "telefono"] for prov, func in zip(edges.id_proveedor, edges.id_funcionario)
    ]
    edges["comparte_direccion"] = [
        p.at[prov, "direccion"] == f.at[func, "direccion"] for prov, func in zip(edges.id_proveedor, edges.id_funcionario)
    ]
    edges["vinculo_sospechoso"] = edges["comparte_telefono"] | edges["comparte_direccion"]
    return edges


def construir_grafo(proveedores, funcionarios, edges):
    g = nx.Graph()
    g.add_nodes_from(((x, {"tipo": "proveedor"}) for x in proveedores["id_proveedor"]))
    g.add_nodes_from(((x, {"tipo": "funcionario"}) for x in funcionarios["id_funcionario"]))
    for _, r in edges.iterrows():
        g.add_edge(
            r["id_proveedor"], r["id_funcionario"],
            n_contratos=int(r["n_contratos"]),
            monto_total=float(r["monto_total"]),
            sospechoso=bool(r["vinculo_sospechoso"]),
        )
    return g


def validar(edges, casos):
    marcados = set(zip(
        edges.loc[edges["vinculo_sospechoso"], "id_proveedor"],
        edges.loc[edges["vinculo_sospechoso"], "id_funcionario"],
    ))
    aciertos = casos & marcados
    print(f"Vínculos sembrados: {len(casos)} | marcados: {len(marcados)} | recuperados: {len(aciertos)}")
    return len(aciertos), len(casos)


def graficar(edges):
    sospechosas = edges[edges["vinculo_sospechoso"]]
    contexto = edges[~edges["vinculo_sospechoso"]].sample(
        n=min(25, int((~edges["vinculo_sospechoso"]).sum())), random_state=7
    )
    muestra = pd.concat([sospechosas, contexto], ignore_index=True)
    g = nx.Graph()
    for _, r in muestra.iterrows():
        g.add_node(r["id_proveedor"], tipo="proveedor")
        g.add_node(r["id_funcionario"], tipo="funcionario")
        g.add_edge(r["id_proveedor"], r["id_funcionario"], sospechoso=bool(r["vinculo_sospechoso"]))
    pos = nx.spring_layout(g, seed=7)
    node_colors = ["tab:blue" if g.nodes[n]["tipo"] == "proveedor" else "tab:orange" for n in g.nodes]
    edge_widths = [2.5 if g.edges[e]["sospechoso"] else 0.7 for e in g.edges]
    fig, ax = plt.subplots(figsize=(9, 7))
    nx.draw_networkx_nodes(g, pos, node_color=node_colors, node_size=120, ax=ax)
    nx.draw_networkx_edges(g, pos, width=edge_widths, ax=ax)
    ax.set_title("Red proveedor–funcionario — muestra sintética")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig("outputs/charts/10_grafo_vinculos.png", dpi=130)
    plt.close()


def main():
    contratos = pd.read_csv(entrada_plata("contratos_procesados.csv"), parse_dates=["fecha_contrato"])
    proveedores = pd.read_csv(entrada_plata("proveedores.csv"))
    funcionarios = pd.read_csv(entrada_plata("funcionarios.csv"))

    proveedores, funcionarios = enriquecer_contacto(proveedores, funcionarios)
    proveedores, funcionarios, casos = sembrar_vinculos(contratos, proveedores, funcionarios)

    PLATA.mkdir(parents=True, exist_ok=True)
    proveedores.to_csv(PLATA / "proveedores_contacto.csv", index=False)
    funcionarios.to_csv(PLATA / "funcionarios_contacto.csv", index=False)

    edges = construir_edges(contratos, proveedores, funcionarios)
    edges.to_csv("outputs/ranking_vinculos_proveedor_funcionario.csv", index=False)
    g = construir_grafo(proveedores, funcionarios, edges)
    validar(edges, casos)
    graficar(edges)
    print(f"Grafo: {g.number_of_nodes()} nodos / {g.number_of_edges()} aristas.")


if __name__ == "__main__":
    main()
