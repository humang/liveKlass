# E-commerce Event Analytics Pipeline

Python 기반 이벤트 생성기와 PostgreSQL 저장소, Streamlit 대시보드로 구성된 E-commerce 로그 파이프라인입니다.

## 구성

- `main.py` : 세션 기반 이벤트 생성기
- `visualize.py` : 로컬 PNG 분석 차트 생성 스크립트
- `app.py` : Streamlit 대시보드 앱
- `init.sql` : PostgreSQL 테이블 초기화 SQL
- `Dockerfile` : Python 앱 및 대시보드 이미지 빌드
- `docker-compose.yml` : DB, 이벤트 제너레이터, Streamlit 대시보드 서비스 구성

## 실행

```bash
docker compose up -d --build
```

대시보드 열기: `http://localhost:8501`
