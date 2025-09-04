# ===== NUEVO: Gráfica de unidades restantes =====
st.subheader("📊 Unidades restantes (Stock) y punto de pedido (Min)")

# Toggle: global (todos los apartamentos) o por apartamento concreto
modo_graf = st.radio(
    "Vista de la gráfica:",
    ["Global por producto", "Por apartamento"],
    index=0,
    horizontal=True,
)

import matplotlib.pyplot as plt

if modo_graf == "Global por producto":
    g = (
        detalle.groupby("Producto", as_index=False)
        .agg(Stock=("Stock", "sum"), Min=("Min", "sum"))
    )
    g = g.sort_values("Stock", ascending=True)
    # Limitar a top N si hay muchos
    topN = st.slider("¿Cuántos productos mostrar?", min_value=10, max_value=min(50, len(g)), value=min(20, len(g)))
    g = g.head(topN)

    fig, ax = plt.subplots(figsize=(10, max(5, len(g)*0.35)))
    ax.barh(g["Producto"], g["Stock"])                # barras = unidades restantes
    ax.scatter(g["Min"], range(len(g)), marker="D")   # marcadores = punto de pedido (Min)
    ax.set_xlabel("Unidades")
    ax.set_ylabel("Producto")
    ax.set_title("Unidades restantes (Stock) vs Punto de pedido (Min)")
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    fig.tight_layout()
    st.pyplot(fig)

    # Lista rápida de productos por debajo del Min
    bajos = g[g["Stock"] < g["Min"]][["Producto", "Stock", "Min"]]
    if not bajos.empty:
        st.warning("⚠️ Productos por debajo del punto de pedido (Min):")
        st.dataframe(bajos.reset_index(drop=True), use_container_width=True)

else:
    # Selector de apartamento (almacén)
    alms = sorted(detalle["Almacen"].dropna().unique().tolist())
    if not alms:
        st.info("No hay apartamentos para filtrar.")
    else:
        alm_sel = st.selectbox("Elige apartamento (almacén):", alms, index=0)
        g = (
            detalle[detalle["Almacen"] == alm_sel]
            .groupby("Producto", as_index=False)
            .agg(Stock=("Stock", "sum"), Min=("Min", "sum"))
            .sort_values("Stock", ascending=True)
        )
        topN = st.slider("¿Cuántos productos mostrar? ", min_value=10, max_value=min(50, len(g)), value=min(20, len(g)), key="topN_alm")
        g = g.head(topN)

        fig, ax = plt.subplots(figsize=(10, max(5, len(g)*0.35)))
        ax.barh(g["Producto"], g["Stock"])
        ax.scatter(g["Min"], range(len(g)), marker="D")
        ax.set_xlabel("Unidades")
        ax.set_ylabel("Producto")
        ax.set_title(f"Unidades restantes (Stock) vs Min — {alm_sel}")
        ax.grid(axis="x", linestyle=":", alpha=0.5)
        fig.tight_layout()
        st.pyplot(fig)

        bajos = g[g["Stock"] < g["Min"]][["Producto", "Stock", "Min"]]
        if not bajos.empty:
            st.warning(f"⚠️ En {alm_sel}, por debajo del Min:")
            st.dataframe(bajos.reset_index(drop=True), use_container_width=True)
