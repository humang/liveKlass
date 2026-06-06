import os

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st


@st.cache_data
def load_data():
    conn = psycopg2.connect(
        host=os.environ.get("DATABASE_HOST", "localhost"),
        port=int(os.environ.get("DATABASE_PORT", 5432)),
        dbname=os.environ.get("DATABASE_NAME", "ecommerce_events"),
        user=os.environ.get("DATABASE_USER", "postgres"),
        password=os.environ.get("DATABASE_PASSWORD", "postgres"),
    )
    query = "SELECT session_id, event_type, timestamp FROM event_logs"
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def build_funnel_chart(df):
    sessions = df.groupby("session_id")["event_type"].agg(list).reset_index()
    total_sessions = len(sessions)
    click_sessions = sessions[ sessions["event_type"].apply(lambda events: "item_click" in events) ]
    purchase_sessions = sessions[ sessions["event_type"].apply(lambda events: "purchase" in events) ]

    funnel_df = pd.DataFrame(
        {
            "stage": ["전체 세션", "상품 클릭 세션", "구매 세션"],
            "count": [total_sessions, len(click_sessions), len(purchase_sessions)],
        }
    )
    fig = px.funnel(funnel_df, x="count", y="stage", title="유저 이탈 퍼널")
    return fig


def build_dwell_histogram(df):
    purchase_sessions = df[df["event_type"] == "purchase"]["session_id"].unique()
    bounce_df = df[~df["session_id"].isin(purchase_sessions)].copy()
    dwell = (
        bounce_df.groupby("session_id").agg(
            session_start=("timestamp", "min"),
            session_end=("timestamp", "max"),
        )
        .reset_index()
    )
    dwell["dwell_minutes"] = (dwell["session_end"] - dwell["session_start"]).dt.total_seconds() / 60
    fig = px.histogram(
        dwell,
        x="dwell_minutes",
        nbins=30,
        title="체류 시간 분포 (구매 미발생 세션)",
        labels={"dwell_minutes": "체류 시간 (분)"},
    )
    fig.update_layout(bargap=0.1)
    return fig


def build_conversion_depth_chart(df):
    session_events = (
        df.groupby("session_id").agg(
            event_count=("event_type", "count"),
            purchased=("event_type", lambda types: (types == "purchase").any()),
        )
        .reset_index()
    )
    bins = [0, 3, 6, 9, 100]
    labels = ["1~3회", "4~6회", "7~9회", "10회 이상"]
    session_events["depth_bucket"] = pd.cut(session_events["event_count"], bins=bins, labels=labels, right=True)
    conversion = (
        session_events.groupby("depth_bucket").agg(
            total_sessions=("purchased", "count"),
            purchases=("purchased", "sum"),
        )
        .reset_index()
    )
    conversion["conversion_rate"] = conversion["purchases"] / conversion["total_sessions"] * 100
    fig = px.bar(
        conversion,
        x="depth_bucket",
        y="conversion_rate",
        text="conversion_rate",
        title="탐색 깊이별 전환율",
        labels={"depth_bucket": "이벤트 발생 횟수 구간", "conversion_rate": "전환율 (%)"},
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(yaxis=dict(range=[0, conversion["conversion_rate"].max() * 1.2]))
    return fig


def main():
    st.set_page_config(page_title="마케팅 인사이트 도출 대시보드", layout="wide")
    st.title("마케팅 인사이트 도출 대시보드")
    st.markdown(
        "현실적인 세션 기반 이벤트 데이터를 분석하여 유저 이탈과 구매 전환 패턴을 시각화합니다.\n"
        "세션 수준의 탐색 깊이, 체류 시간, 이탈 퍼널을 확인하여 UX 및 마케팅 전략 개선 포인트를 도출하세요."
    )

    df = load_data()
    if df.empty:
        st.warning("`event_logs` 테이블에 데이터가 없습니다. 먼저 이벤트 생성기를 실행해 주세요.")
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        st.plotly_chart(build_funnel_chart(df), use_container_width=True)
    with col2:
        st.plotly_chart(build_dwell_histogram(df), use_container_width=True)

    st.plotly_chart(build_conversion_depth_chart(df), use_container_width=True)

    st.markdown("---")
    st.markdown(
        "### 데이터 요약"
        f"\n- 전체 세션 수: {df['session_id'].nunique():,}"
        f"\n- 구매 세션 수: {df[df['event_type'] == 'purchase']['session_id'].nunique():,}"
        f"\n- 구매 전환율: {round(df.groupby('session_id')['event_type'].apply(lambda events: (events == 'purchase').any()).mean() * 100, 2)}%"
    )


if __name__ == "__main__":
    main()
