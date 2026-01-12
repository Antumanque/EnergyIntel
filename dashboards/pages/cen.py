import streamlit as st
import pandas as pd
import plotly.express as px


def render(engine):
    st.title("CEN - Solicitudes de Conexion")

    # Filters
    with st.expander("Filtros", expanded=True):
        fcol1, fcol2, fcol3 = st.columns(3)

        techs = pd.read_sql(
            "SELECT DISTINCT tipo_tecnologia_nombre FROM cen_acceso_abierto.solicitudes WHERE tipo_tecnologia_nombre IS NOT NULL ORDER BY 1",
            engine,
        )["tipo_tecnologia_nombre"].tolist()

        regions = pd.read_sql(
            "SELECT DISTINCT region FROM cen_acceso_abierto.solicitudes WHERE region IS NOT NULL ORDER BY 1",
            engine,
        )["region"].tolist()

        estados = pd.read_sql(
            "SELECT DISTINCT estado_solicitud FROM cen_acceso_abierto.solicitudes WHERE estado_solicitud IS NOT NULL ORDER BY 1",
            engine,
        )["estado_solicitud"].tolist()

        with fcol1:
            selected_tech = st.multiselect("Tecnologia", techs)
        with fcol2:
            selected_region = st.multiselect("Region", regions)
        with fcol3:
            selected_estado = st.multiselect("Estado", estados)

    # Build query
    where = ["deleted_at IS NULL"]
    if selected_tech:
        techs_str = ", ".join([f"'{t}'" for t in selected_tech])
        where.append(f"tipo_tecnologia_nombre IN ({techs_str})")
    if selected_region:
        regions_str = ", ".join([f"'{r}'" for r in selected_region])
        where.append(f"region IN ({regions_str})")
    if selected_estado:
        estados_str = ", ".join([f"'{e}'" for e in selected_estado])
        where.append(f"estado_solicitud IN ({estados_str})")

    where_clause = " AND ".join(where)

    # KPIs
    kpis = pd.read_sql(
        f"""
        SELECT
            COUNT(*) as total,
            COUNT(DISTINCT razon_social) as empresas,
            SUM(CAST(REPLACE(REPLACE(potencia_nominal, '"', ''), ',', '.') AS DECIMAL(10,2))) as mw
        FROM cen_acceso_abierto.solicitudes
        WHERE {where_clause}
        """,
        engine,
    )

    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Solicitudes", f"{kpis['total'].iloc[0]:,}")
    with k2:
        st.metric("Empresas", f"{kpis['empresas'].iloc[0]:,}")
    with k3:
        mw = kpis["mw"].iloc[0] or 0
        st.metric("MW", f"{mw:,.0f}")

    st.divider()

    # Charts
    left, right = st.columns(2)

    with left:
        st.subheader("Por Estado")
        estado_data = pd.read_sql(
            f"""
            SELECT estado_solicitud as estado, COUNT(*) as cantidad
            FROM cen_acceso_abierto.solicitudes
            WHERE {where_clause}
            GROUP BY estado_solicitud
            ORDER BY cantidad DESC
            LIMIT 10
            """,
            engine,
        )
        fig = px.bar(estado_data, x="cantidad", y="estado", orientation="h")
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("MW por Tecnologia")
        mw_tech = pd.read_sql(
            f"""
            SELECT
                tipo_tecnologia_nombre as tecnologia,
                SUM(CAST(REPLACE(REPLACE(potencia_nominal, '"', ''), ',', '.') AS DECIMAL(10,2))) as mw
            FROM cen_acceso_abierto.solicitudes
            WHERE {where_clause} AND tipo_tecnologia_nombre IS NOT NULL
            GROUP BY tipo_tecnologia_nombre
            ORDER BY mw DESC
            """,
            engine,
        )
        fig = px.bar(mw_tech, x="tecnologia", y="mw")
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Time series
    st.subheader("Solicitudes por Mes")
    timeline = pd.read_sql(
        f"""
        SELECT
            DATE_FORMAT(create_date, '%%Y-%%m') as mes,
            COUNT(*) as cantidad
        FROM cen_acceso_abierto.solicitudes
        WHERE {where_clause} AND create_date IS NOT NULL
        GROUP BY DATE_FORMAT(create_date, '%%Y-%%m')
        ORDER BY mes
        """,
        engine,
    )
    if not timeline.empty:
        fig = px.line(timeline, x="mes", y="cantidad", markers=True)
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Data table
    st.subheader("Detalle")
    data = pd.read_sql(
        f"""
        SELECT
            proyecto,
            razon_social as empresa,
            tipo_tecnologia_nombre as tecnologia,
            CAST(REPLACE(REPLACE(potencia_nominal, '"', ''), ',', '.') AS DECIMAL(10,2)) as mw,
            region,
            estado_solicitud as estado,
            DATE_FORMAT(create_date, '%%Y-%%m-%%d') as fecha
        FROM cen_acceso_abierto.solicitudes
        WHERE {where_clause}
        ORDER BY create_date DESC
        LIMIT 500
        """,
        engine,
    )
    st.dataframe(data, use_container_width=True, hide_index=True)
