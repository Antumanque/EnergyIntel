import streamlit as st
import pandas as pd
import plotly.express as px


def render(engine):
    st.title("SEA - Proyectos Ambientales")

    # Filters
    with st.expander("Filtros", expanded=True):
        fcol1, fcol2, fcol3 = st.columns(3)

        regions = pd.read_sql(
            "SELECT DISTINCT region_nombre FROM sea.proyectos WHERE region_nombre IS NOT NULL ORDER BY 1",
            engine,
        )["region_nombre"].tolist()

        estados = pd.read_sql(
            "SELECT DISTINCT estado_proyecto FROM sea.proyectos WHERE estado_proyecto IS NOT NULL ORDER BY 1",
            engine,
        )["estado_proyecto"].tolist()

        tipos = pd.read_sql(
            "SELECT DISTINCT workflow_descripcion FROM sea.proyectos WHERE workflow_descripcion IS NOT NULL ORDER BY 1",
            engine,
        )["workflow_descripcion"].tolist()

        with fcol1:
            selected_region = st.multiselect("Region", regions, key="sea_region")
        with fcol2:
            selected_estado = st.multiselect("Estado", estados, key="sea_estado")
        with fcol3:
            selected_tipo = st.multiselect("Tipo (DIA/EIA)", tipos, key="sea_tipo")

    # Build query
    where = ["1=1"]
    if selected_region:
        regions_str = ", ".join([f"'{r}'" for r in selected_region])
        where.append(f"region_nombre IN ({regions_str})")
    if selected_estado:
        estados_str = ", ".join([f"'{e}'" for e in selected_estado])
        where.append(f"estado_proyecto IN ({estados_str})")
    if selected_tipo:
        tipos_str = ", ".join([f"'{t}'" for t in selected_tipo])
        where.append(f"workflow_descripcion IN ({tipos_str})")

    where_clause = " AND ".join(where)

    # KPIs
    kpis = pd.read_sql(
        f"""
        SELECT
            COUNT(*) as total,
            SUM(inversion_mm) / 1000000 as inversion_mm,
            COUNT(DISTINCT titular) as titulares
        FROM sea.proyectos
        WHERE {where_clause}
        """,
        engine,
    )

    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Proyectos", f"{kpis['total'].iloc[0]:,}")
    with k2:
        inv = kpis["inversion_mm"].iloc[0] or 0
        st.metric("Inversion Total", f"${inv:,.0f}MM")
    with k3:
        st.metric("Titulares", f"{kpis['titulares'].iloc[0]:,}")

    st.divider()

    # Charts
    left, right = st.columns(2)

    with left:
        st.subheader("Por Estado")
        estado_data = pd.read_sql(
            f"""
            SELECT estado_proyecto as estado, COUNT(*) as cantidad
            FROM sea.proyectos
            WHERE {where_clause}
            GROUP BY estado_proyecto
            ORDER BY cantidad DESC
            """,
            engine,
        )
        fig = px.pie(estado_data, values="cantidad", names="estado", hole=0.4)
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Inversion por Region (Top 10)")
        inv_region = pd.read_sql(
            f"""
            SELECT
                region_nombre as region,
                SUM(inversion_mm) / 1000000 as inversion_mm
            FROM sea.proyectos
            WHERE {where_clause} AND region_nombre IS NOT NULL
            GROUP BY region_nombre
            ORDER BY inversion_mm DESC
            LIMIT 10
            """,
            engine,
        )
        fig = px.bar(inv_region, x="inversion_mm", y="region", orientation="h")
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # DIA vs EIA
    st.subheader("DIA vs EIA por Region")
    tipo_region = pd.read_sql(
        f"""
        SELECT
            region_nombre as region,
            workflow_descripcion as tipo,
            COUNT(*) as cantidad
        FROM sea.proyectos
        WHERE {where_clause} AND region_nombre IS NOT NULL
        GROUP BY region_nombre, workflow_descripcion
        ORDER BY cantidad DESC
        """,
        engine,
    )
    if not tipo_region.empty:
        fig = px.bar(
            tipo_region,
            x="region",
            y="cantidad",
            color="tipo",
            barmode="group",
        )
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Data table
    st.subheader("Detalle")
    data = pd.read_sql(
        f"""
        SELECT
            expediente_nombre as proyecto,
            titular,
            region_nombre as region,
            workflow_descripcion as tipo,
            estado_proyecto as estado,
            CONCAT('$', FORMAT(inversion_mm / 1000000, 1), 'MM') as inversion,
            DATE_FORMAT(FROM_UNIXTIME(fecha_presentacion), '%%Y-%%m-%%d') as fecha
        FROM sea.proyectos
        WHERE {where_clause}
        ORDER BY fecha_presentacion DESC
        LIMIT 500
        """,
        engine,
    )
    st.dataframe(data, use_container_width=True, hide_index=True)
