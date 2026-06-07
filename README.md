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

## Kubernetes 아키텍처 설계

이 설계는 로컬 Docker Compose 기반 파이프라인을 Kubernetes 프로덕션 환경으로 확장하기 위한 아키텍처 개요와 주요 리소스를 제시합니다.

### 주요 Kubernetes 매니페스트

- `k8s/db/db-pvc.yaml`: PostgreSQL 데이터를 영구 저장하기 위한 PVC를 선언합니다.
- `k8s/db/db-statefulset.yaml`: PostgreSQL을 StatefulSet으로 배포하여 안정적인 네트워크 ID와 볼륨 영속성을 보장합니다.
- `k8s/db/db-service.yaml`: Postgres에 내부 클러스터IP로 안전하게 접근할 수 있는 서비스입니다.
- `k8s/base/db-configmap.yaml`: 데이터베이스 이름과 사용자 같은 비민감 구성 값을 분리합니다.
- `k8s/base/db-secret.yaml`: 데이터베이스 비밀번호와 Streamlit 시크릿 키 등 민감 데이터를 Secret으로 저장합니다.
- `k8s/app/app-deployment.yaml`: 이벤트 생성기 앱 Deployment로 CPU/메모리 리소스, 프로브, Prometheus 스크랩 어노테이션을 정의합니다.
- `k8s/app/app-service.yaml`: 이벤트 생성기 앱에 대한 클러스터 내부 접근을 제공하는 ClusterIP 서비스입니다.
- `k8s/app/app-hpa.yaml`: CPU 사용률 기반으로 1~5개까지 자동 확장하는 HPA입니다.
- `k8s/dashboard/dash-deployment.yaml`: Streamlit 대시보드 Deployment로 DB 연결 정보, 리소스 제약, 프로브를 설정합니다.
- `k8s/dashboard/dash-service.yaml`: 대시보드에 대한 클러스터 내부 Service입니다.
- `k8s/routing/gateway.yaml`: Gateway API Gateway 리소스를 선언합니다.
- `k8s/routing/httproute.yaml`: `/api/events`는 이벤트 생성기 앱으로, `/dashboard`는 Streamlit 대시보드로 라우팅합니다.

### 아키텍처 설계 요약

- `StatefulSet`과 `PersistentVolumeClaim`은 PostgreSQL 데이터의 내구성과 스토리지 영속성을 보장합니다.
- ConfigMap과 Secret 분리는 비민감 구성과 민감 데이터를 분리하여 보안과 운영 유연성을 높입니다.
- Deployments는 애플리케이션의 선언적 관리, 자동 롤링 업데이트, 장애 복구를 제공합니다.
- Service는 내부 서비스 디스커버리와 연결 추상화를 제공해 Pod IP 변경을 투명하게 처리합니다.
- HPA는 CPU 기반 자동 확장을 통해 트래픽 변화에 탄력적으로 대응합니다.
- Gateway API는 외부 트래픽을 `/api/events`와 `/dashboard`로 분리하여 서비스별 라우팅을 처리합니다.

### 모니터링 및 보안

- 이벤트 생성기와 대시보드 Pod에 Prometheus 스크랩 어노테이션을 추가하여 메트릭 수집을 준비합니다.
- Grafana와 Prometheus를 함께 사용하면 애플리케이션 성능, DB 연결 상태, 자원 사용량을 시각화할 수 있습니다.
- 민감 정보는 `k8s/base/db-secret.yaml`에 저장하고, 애플리케이션은 환경 변수로 주입받아 코드에 직접 포함되지 않습니다.

### 스키마 설명

JSON 통째 저장을 지양하고, 다양한 유저 행동(검색, 클릭, 구매)을 단일 테이블(event_logs)에 통합하되 이벤트별 특화 필드(`keyword`, `item_id`)는 Nullable로 설계하여 유연성과 분석 속도의 균형을 맞추었습니다. 특히 `session_id`와 `timestamp` 컬럼을 명확히 분리하여, 분석 시 복잡한 JOIN 연산 없이 SQL의 윈도우 함수(Window Function)만으로도 유저의 '체류 시간'과 '탐색 깊이'를 고속으로 집계할 수 있도록 설계했습니다.

### 구현하면서 고민한 점

① "단순한 랜덤 데이터가 아닌, 마케팅 액션을 이끌어낼 수 있는 데이터란 무엇일까?"
초기에는 Faker를 이용해 이벤트 타입만 무작위로 생성했습니다. 하지만 이 데이터로는 '그래서 사이트를 어떻게 개선할 것인가?'라는 질문에 답할 수 없었습니다.

- 결정: 유저 행동을 세션(`session_id`)으로 묶고, 3가지 가상의 페르소나(즉시 이탈자, 윈도우 쇼퍼, 목적형 구매자)를 정의하여 행동 패턴에 가중치를 부여하는 로직을 구현했습니다.
- 결과: 이를 통해 대시보드에서 '체류 시간 대비 전환율', '특정 탐색 깊이에서의 이탈률' 등을 분석할 수 있게 되었고, 마케팅 팀이 "10초 내 이탈 유저가 많으니 랜딩 페이지를 개선하자"는 식의 실질적인 액션 플랜을 도출할 수 있는 파이프라인이 되었습니다. (단, 더미 데이터 생성 로직의 한계로 특정 탐색 횟수에 전환율이 편중되는 현상이 발생했는데, 향후 마르코프 체인(Markov Chain) 모델 등을 도입해 더 정교하게 개선해 보고 싶습니다.)

② "분석 결과를 가장 효과적으로 전달하는 시각화 방법은 무엇일까?"
처음에는 Matplotlib을 사용해 정적인 PNG 이미지로 결과를 저장했습니다. 하지만 실제 업무 환경에서 데이터 분석 결과를 마케터와 공유할 때, 정적 이미지는 설득력이 떨어진다고 판단했습니다.

- 결정: 별도의 무거운 BI 툴(Metabase 등)을 구축하는 대신, Python 기반의 Streamlit과 Plotly를 도입했습니다.
- 결과: 인프라 복잡도는 Docker 컨테이너 하나 추가하는 정도로 최소화하면서도, 마우스 툴팁(Hover)과 인터랙티브한 차트 조작이 가능한 실무 수준의 대시보드를 구축할 수 있었습니다.

③ "프로덕션 레벨로 확장할 때 데이터의 영속성과 보안은 어떻게 보장할 것인가?" (K8s 아키텍처 설계 중)
초기 Docker Compose 환경에서는 편의성을 위해 DB 비밀번호를 `docker-compose.yml`에 하드코딩했고, 단순히 컨테이너를 띄우는 데 집중했습니다. 하지만 선택 과제인 Kubernetes 설계를 진행하면서 이 방식이 실무(Production)에서는 매우 위험하다는 것을 깨달았습니다.

- 결정 및 해결: DB의 비밀번호 등 민감 정보는 환경변수에서 분리하여 K8s Secret으로 관리하도록 설계했습니다. 또한, DB를 일반적인 Deployment로 띄우면 Pod 재시작 시 로그 데이터가 모두 날아간다는 것을 알게 되어, 영구 볼륨(PVC)을 마운트하고 네트워크 식별자를 유지할 수 있는 StatefulSet으로 DB 배포 방식을 변경하여 데이터 안정성을 확보했습니다.


