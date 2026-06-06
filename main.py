import argparse
import os
import random
import string
import sys
import time
import uuid
from datetime import datetime, timedelta

import psycopg2
from faker import Faker

fake = Faker()
EVENT_TYPES = ["page_view", "search", "item_click", "purchase"]
USER_COUNT = 200


def random_user_id():
    return f"user_{random.randint(1000, 9999)}"


def random_page_url():
    return f"https://www.example.com/{fake.word()}/{fake.pystr(min_chars=3, max_chars=8)}"


def random_search_keyword():
    return fake.word()


def random_item_id():
    return f"item_{random.randint(10000, 99999)}"


def build_quick_bouncer(session_id, user_id):
    event_count = random.randint(1, 2)
    events = []
    start_time = datetime.now()
    for i in range(event_count):
        events.append({
            "event_type": "page_view",
            "timestamp": start_time + timedelta(seconds=random.randint(1, 10)),
            "search_keyword": None,
            "item_id": None,
            "page_url": random_page_url(),
        })
    return events


def build_window_shopper(session_id, user_id):
    event_count = random.randint(5, 10)
    events = []
    start_time = datetime.now()
    current_time = start_time
    for i in range(event_count):
        current_time += timedelta(seconds=random.randint(15, 45))
        if i % 3 == 1:
            event_type = "search"
            search_keyword = random_search_keyword()
            item_id = None
        elif i % 3 == 2:
            event_type = "item_click"
            search_keyword = None
            item_id = random_item_id()
        else:
            event_type = "page_view"
            search_keyword = None
            item_id = None
        events.append({
            "event_type": event_type,
            "timestamp": current_time,
            "search_keyword": search_keyword,
            "item_id": item_id,
            "page_url": random_page_url(),
        })
    return events


def build_purchaser(session_id, user_id):
    events = []
    start_time = datetime.now()
    current_time = start_time
    # page_view entry
    events.append({
        "event_type": "page_view",
        "timestamp": current_time,
        "search_keyword": None,
        "item_id": None,
        "page_url": random_page_url(),
    })
    # search
    current_time += timedelta(seconds=random.randint(5, 30))
    keyword = random_search_keyword()
    events.append({
        "event_type": "search",
        "timestamp": current_time,
        "search_keyword": keyword,
        "item_id": None,
        "page_url": random_page_url(),
    })
    # item click
    current_time += timedelta(seconds=random.randint(10, 40))
    item_id = random_item_id()
    events.append({
        "event_type": "item_click",
        "timestamp": current_time,
        "search_keyword": None,
        "item_id": item_id,
        "page_url": random_page_url(),
    })
    # purchase
    current_time += timedelta(seconds=random.randint(10, 60))
    events.append({
        "event_type": "purchase",
        "timestamp": current_time,
        "search_keyword": None,
        "item_id": item_id,
        "page_url": random_page_url(),
    })
    return events


def create_session_events():
    session_id = uuid.uuid4()
    user_id = random_user_id()
    weights = [0.35, 0.45, 0.20]
    session_type = random.choices(["bouncer", "window_shopper", "purchaser"], weights=weights, k=1)[0]
    if session_type == "bouncer":
        events = build_quick_bouncer(session_id, user_id)
    elif session_type == "window_shopper":
        events = build_window_shopper(session_id, user_id)
    else:
        events = build_purchaser(session_id, user_id)
    return session_id, user_id, events


def prepare_insert_query():
    return (
        "INSERT INTO event_logs (log_id, timestamp, user_id, session_id, event_type, search_keyword, item_id, page_url) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )


def open_db_connection(host, port, dbname, user, password):
    for attempt in range(10):
        try:
            return psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
            )
        except psycopg2.OperationalError:
            print(f"Database unavailable, retrying... ({attempt + 1}/10)")
            time.sleep(3)
    raise RuntimeError("Unable to connect to PostgreSQL")


def main(total_sessions: int | None):
    db_host = os.environ.get("DATABASE_HOST", "localhost")
    db_port = int(os.environ.get("DATABASE_PORT", 5432))
    db_name = os.environ.get("DATABASE_NAME", "ecommerce_events")
    db_user = os.environ.get("DATABASE_USER", "postgres")
    db_password = os.environ.get("DATABASE_PASSWORD", "postgres")

    db = open_db_connection(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
    )
    cursor = db.cursor()
    insert_sql = prepare_insert_query()

    session_counter = 0
    try:
        while total_sessions is None or session_counter < total_sessions:
            session_id, user_id, events = create_session_events()
            for event in events:
                cursor.execute(
                    insert_sql,
                    (
                        str(uuid.uuid4()),
                        event["timestamp"],
                        user_id,
                        str(session_id),
                        event["event_type"],
                        event["search_keyword"],
                        event["item_id"],
                        event["page_url"],
                    ),
                )
            db.commit()
            session_counter += 1
            print(
                f"Inserted session {session_counter}: {session_id} ({len(events)} events)"
            )
            if total_sessions is None:
                time.sleep(random.uniform(0.5, 1.2))
    except KeyboardInterrupt:
        print("Interrupted by user, exiting...")
    finally:
        cursor.close()
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic e-commerce session events into PostgreSQL.")
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of sessions to generate (omit for continuous generation)",
    )
    args = parser.parse_args()
    main(args.count)
