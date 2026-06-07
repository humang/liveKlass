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
    click_sessions = sessions[sessions["event_type"].apply(lambda events: "item_click" in events)]
    purchase_sessions = sessions[sessions["event_type"].apply(lambda events: "purchase" in events)]

    funnel_df = pd.DataFrame(
        {
            "stage": ["전체 세션", "상품 클릭 세션", "구매 세션"],
            "count": [total_sessions, len(click_sessions), len(purchase_sessions)],
        }
    )
    fig = px.funnel(
        funnel_df,
        x="count",
        y="stage",
        title="유저 이탈 퍼널",
    )
    fig.update_traces(
        hovertemplate="단계: %{y}<br>세션 수: %{x:,}<extra></extra>"
    )
    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
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
    fig.update_traces(
        hovertemplate="체류 시간: %{x:.2f}분<br>이탈 유저 수: %{y}명<extra></extra>"
    )
    fig.update_layout(bargap=0.1, margin=dict(l=20, r=20, t=50, b=20))
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
    fig.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside",
        hovertemplate=(
            "탐색 깊이: %{x}<br>전환율: %{y:.2f}%<br>세션 수: %{customdata[0]}명<extra></extra>"
        ),
        customdata=conversion[["total_sessions"]].values,
    )
    fig.update_layout(yaxis=dict(range=[0, max(conversion["conversion_rate"].max() * 1.2, 10)]), margin=dict(l=20, r=20, t=50, b=20))
    return fig


def build_group_summary(df):
    session_events = (
        df.groupby("session_id").agg(
            event_count=("event_type", "count"),
            has_purchase=("event_type", lambda types: (types == "purchase").any()),
            session_start=("timestamp", "min"),
            session_end=("timestamp", "max"),
        )
        .reset_index()
    )
    session_events["dwell_seconds"] = (session_events["session_end"] - session_events["session_start"]).dt.total_seconds()
    session_events["group"] = session_events.apply(
        lambda row: "구매 완료"
        if row["has_purchase"]
        else ("즉시 이탈" if row["event_count"] <= 2 else "윈도우 쇼핑"),
        axis=1,
    )
    summary = (
        session_events.groupby("group").agg(
            sessions=("session_id", "count"),
            avg_dwell_seconds=("dwell_seconds", "mean"),
            avg_event_count=("event_count", "mean"),
        )
        .reset_index()
    )
    summary["avg_dwell_seconds"] = summary["avg_dwell_seconds"].round(0).astype(int)
    summary["avg_event_count"] = summary["avg_event_count"].round(1)
    summary.columns = ["그룹", "해당 세션 수", "평균 체류 시간(초)", "평균 탐색 횟수"]
    order = ["즉시 이탈", "윈도우 쇼핑", "구매 완료"]
    summary["sort_order"] = summary["그룹"].apply(lambda x: order.index(x) if x in order else 99)
    summary = summary.sort_values("sort_order").drop(columns=["sort_order"])
    return summary


def main():
    st.set_page_config(page_title="마케팅 인사이트 도출 대시보드", layout="wide")
    st.title("마케팅 인사이트 도출 대시보드")
    st.markdown(
        "### 세션 기반 사용자 행동을 한눈에 파악하고, UX/마케팅 개선 포인트를 도출합니다."
    )
    st.markdown(
        "총 세션 대비 상품 클릭, 구매 전환 패턴과 비구매 이탈 사용자의 체류 시간 분포를 직관적으로 분석합니다."
    )

    df = load_data()
    if df.empty:
        st.warning("`event_logs` 테이블에 데이터가 없습니다. 먼저 이벤트 생성기를 실행해 주세요.")
        return

    total_sessions = df["session_id"].nunique()
    purchase_sessions = df[df["event_type"] == "purchase"]["session_id"].nunique()
    total_purchases = df[df["event_type"] == "purchase"].shape[0]
    conversion_rate = round(purchase_sessions / total_sessions * 100, 2) if total_sessions else 0.0

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("총 세션 수", f"{total_sessions:,}")
    metric_col2.metric("총 구매 세션 수", f"{purchase_sessions:,}")
    metric_col3.metric("전체 구매 전환율", f"{conversion_rate:.2f}%")

    funnel_col, funnel_info_col = st.columns([3, 1])
    with funnel_col:
        st.plotly_chart(build_funnel_chart(df), use_container_width=True)
    with funnel_info_col:
        st.info(
            "**퍼널 인사이트**\n"
            "- 상품 클릭 이후 구매 전환율을 체크하세요.\n"
            "- 상품 클릭 대비 구매 비중이 낮다면 검색·상품 상세 UI를 개선하세요.\n"
            "- 상단 여백을 줄이고 CTA 버튼을 명확하게 배치하세요."
        )

    dwell_col, dwell_info_col = st.columns([3, 1])
    with dwell_col:
        st.plotly_chart(build_dwell_histogram(df), use_container_width=True)
    with dwell_info_col:
        st.warning(
            "**체류 시간 인사이트**\n"
            "- 0~1분대 이탈이 집중된다면 랜딩 페이지 첫인상을 개선해야 합니다.\n"
            "- 상품 탐색 전 전환을 유도할 수 있는 추천 배너를 검토하세요.\n"
        )

    depth_col, depth_info_col = st.columns([3, 1])
    with depth_col:
        st.plotly_chart(build_conversion_depth_chart(df), use_container_width=True)
    with depth_info_col:
        st.info(
            "**탐색 깊이 인사이트**\n"
            "- 4~6회 탐색 사용자의 전환율이 높다면 핵심 탐색 경로를 강화하세요.\n"
            "- 1~3회 세션은 빠른 이탈 가능성이 크므로 첫 페이지 UX를 최적화하세요."
        )

    st.subheader("유저 행동 패턴 요약 표")
    summary_df = build_group_summary(df)
    st.dataframe(summary_df, use_container_width=True)


if __name__ == "__main__":
    main()
