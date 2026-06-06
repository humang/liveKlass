import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import psycopg2
import seaborn as sns

OUTPUT_DIR = Path("output_charts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def open_db_connection():
    return psycopg2.connect(
        host=os.environ.get("DATABASE_HOST", "localhost"),
        port=int(os.environ.get("DATABASE_PORT", 5432)),
        dbname=os.environ.get("DATABASE_NAME", "ecommerce_events"),
        user=os.environ.get("DATABASE_USER", "postgres"),
        password=os.environ.get("DATABASE_PASSWORD", "postgres"),
    )


def load_event_data(conn):
    query = "SELECT log_id, timestamp, user_id, session_id, event_type, search_keyword, item_id, page_url FROM event_logs"
    return pd.read_sql_query(query, conn)


def analyze_conversion_by_depth(df):
    session_events = df.groupby("session_id").agg(
        event_count=("event_type", "count"),
        purchased=("event_type", lambda types: (types == "purchase").any()),
    )
    session_events["event_count"] = session_events["event_count"].astype(int)
    result = session_events.groupby("event_count").agg(
        total_sessions=("purchased", "count"),
        purchases=("purchased", "sum"),
    )
    result["conversion_rate"] = (result["purchases"] / result["total_sessions"]) * 100
    result = result.reset_index()
    return result


def analyze_bounce_dwell_time(df):
    purchase_sessions = df[df["event_type"] == "purchase"]["session_id"].unique()
    bounce_df = df[~df["session_id"].isin(purchase_sessions)].copy()
    dwell = (
        bounce_df.groupby("session_id").agg(
            session_start=("timestamp", "min"),
            session_end=("timestamp", "max"),
        )
        .reset_index()
    )
    dwell["dwell_seconds"] = (dwell["session_end"] - dwell["session_start"]).dt.total_seconds()
    dwell["dwell_minutes"] = dwell["dwell_seconds"] / 60.0
    return dwell


def plot_conversion_rate(df):
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x="event_count", y="conversion_rate", palette="Blues_d")
    plt.title("Purchase Conversion Rate by Session Event Depth")
    plt.xlabel("Session Event Count")
    plt.ylabel("Conversion Rate (%)")
    plt.tight_layout()
    output_path = OUTPUT_DIR / "conversion_rate_by_event_depth.png"
    plt.savefig(output_path)
    plt.close()
    print(f"Saved conversion rate chart: {output_path}")


def plot_dwell_time_distribution(df):
    plt.figure(figsize=(10, 6))
    sns.histplot(df["dwell_minutes"], bins=15, kde=True, color="#5B8FF9")
    plt.title("Dwell Time Distribution for Non-Purchasing Sessions")
    plt.xlabel("Dwell Time (minutes)")
    plt.ylabel("Number of Sessions")
    plt.tight_layout()
    output_path = OUTPUT_DIR / "bounce_dwell_time_distribution.png"
    plt.savefig(output_path)
    plt.close()
    print(f"Saved dwell time distribution chart: {output_path}")


def main():
    try:
        conn = open_db_connection()
    except Exception as exc:
        print("Unable to connect to PostgreSQL:", exc)
        sys.exit(1)

    df = load_event_data(conn)
    if df.empty:
        print("No event data found in event_logs.")
        sys.exit(0)

    conversion_df = analyze_conversion_by_depth(df)
    dwell_df = analyze_bounce_dwell_time(df)

    print("Conversion analysis by event depth:")
    print(conversion_df)
    print("Non-purchasing session dwell time summary:")
    print(dwell_df["dwell_minutes"].describe())

    plot_conversion_rate(conversion_df)
    plot_dwell_time_distribution(dwell_df)

    conn.close()


if __name__ == "__main__":
    main()
