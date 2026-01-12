import streamlit as st
import pandas as pd
import plotly.express as px


def render(engine):
    st.title("Overview")

    col1, col2, col3 = st.columns(3)

    # CEN stats
    cen_stats = pd.read_sql(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN estado_solicitud LIKE '%%Autorizado%%' OR estado_solicitud LIKE '%%construcción%%' THEN 1 ELSE 0 END) as activos,
            SUM(CAST(REPLACE(REPLACE(potencia_nominal, '"', ''), ',', '.') AS DECIMAL(10,2))) as mw_total
        FROM cen_acceso_abierto.solicitudes
        WHERE deleted_at IS NULL
        """,
        engine,
    )

    with col1:
        st.metric("Solicitudes CEN", f"{cen_stats['total'].iloc[0]:,}")
    with col2:
        st.metric("Proyectos Activos", f"{cen_stats['activos'].iloc[0]:,}")
    with col3:
        st.metric("MW Totales", f"{cen_stats['mw_total'].iloc[0]:,.0f}")

    st.divider()

    # Two charts side by side
    left, right = st.columns(2)

    with left:
        st.subheader("Solicitudes por Tecnologia")
        tech_data = pd.read_sql(
            """
            SELECT tipo_tecnologia_nombre as tecnologia, COUNT(*) as cantidad
            FROM cen_acceso_abierto.solicitudes
            WHERE deleted_at IS NULL AND tipo_tecnologia_nombre IS NOT NULL
            GROUP BY tipo_tecnologia_nombre
            ORDER BY cantidad DESC
            """,
            engine,
        )
        fig = px.pie(
            tech_data,
            values="cantidad",
            names="tecnologia",
            hole=0.4,
        )
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Top 10 Regiones")
        region_data = pd.read_sql(
            """
            SELECT region, COUNT(*) as cantidad
            FROM cen_acceso_abierto.solicitudes
            WHERE deleted_at IS NULL AND region IS NOT NULL
            GROUP BY region
            ORDER BY cantidad DESC
            LIMIT 10
            """,
            engine,
        )
        fig = px.bar(
            region_data,
            x="cantidad",
            y="region",
            orientation="h",
        )
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # SEA projects summary
    st.subheader("Proyectos SEA Recientes")
    sea_recent = pd.read_sql(
        """
        SELECT
            expediente_nombre as proyecto,
            region_nombre as region,
            estado_proyecto as estado,
            DATE_FORMAT(FROM_UNIXTIME(fecha_presentacion), '%%Y-%%m-%%d') as fecha,
            CONCAT('$', FORMAT(inversion_mm / 1000000, 1), 'MM') as inversion
        FROM sea.proyectos
        WHERE fecha_presentacion IS NOT NULL
        ORDER BY fecha_presentacion DESC
        LIMIT 10
        """,
        engine,
    )
    st.dataframe(sea_recent, use_container_width=True, hide_index=True)
