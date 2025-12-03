# LangChain Multi-Agent 지출 분석 서비스

LangChain의 Multi-Agent 시스템을 활용한 지출 관리 및 분석 서비스입니다. SQLite 데이터베이스를 사용하여 지출 데이터를 저장하고, OpenAI GPT를 활용하여 카테고리 자동 분류 및 리포트 생성을 수행합니다.

## 주요 기능

### 1. 지출 입력 및 관리
- **개별 지출 추가**: 날짜, 카테고리, 지출 내역, 금액, 지출처를 입력하여 지출 데이터 추가
- **CSV 일괄 업로드**: CSV 파일을 통한 대량 지출 데이터 일괄 추가
- **표 기반 수정/삭제**: 표에서 직접 데이터 수정 및 삭제 가능 (삭제 컬럼에 체크 표시)
- **카테고리 자동 분류**: 카테고리를 입력하지 않을 경우 LLM 기반 자동 분류

### 2. 지출 분석 대시보드
- **카테고리별 지출 분석**: 각 카테고리별 총액, 평균, 건수, 최소/최대값 등 통계 제공
- **Month-on-Month 증감 분석**: 전월 대비 증감률 계산 및 시각화
- **이상치 분석**: 평균+2SD 이상의 지출을 이상치로 탐지
- **월 지출 예상**: 회귀 분석을 통한 월 지출액 예측
- **시각화**: 바 차트 및 파이 차트를 통한 지출 패턴 시각화

### 3. 리포트 생성
- **AI 기반 리포트**: 지출 분석 결과를 바탕으로 마크다운 형식의 리포트 자동 생성
- **소비 패턴 인사이트**: AI가 분석한 소비 패턴, 개선 포인트, 실천 가능한 조언 제공
- **기간별 리포트**: 특정 기간을 선택하여 해당 기간의 리포트 생성 가능
- **로딩 표시**: 리포트 생성 중 로딩 스피너 표시

## 프로젝트 구조

```
proj/
├── agents/
│   ├── __init__.py
│   ├── db_agent.py          # DB 관리 Agent (카테고리 분류)
│   ├── analysis_agent.py    # 지출 분석 Agent (통계 분석)
│   └── report_agent.py      # 리포트 생성 Agent (AI 리포트 생성)
├── database/
│   ├── __init__.py
│   ├── db_manager.py        # SQLite DB 관리
│   └── models.py            # DB 스키마 정의
├── utils/
│   ├── __init__.py
│   ├── llm_utils.py         # LLM 유틸리티 (카테고리 분류)
│   └── analysis_utils.py    # 통계 분석 유틸리티
├── main.py                  # 메인 비즈니스 로직 및 서비스 레이어
├── ui_gradio.py             # Gradio UI 모듈
├── expenses.db              # SQLite 데이터베이스 파일 (자동 생성)
├── requirements.txt         # Python 패키지 의존성
└── README.md
```

## 설치 방법

### 1. 저장소 클론 또는 다운로드

```bash
cd proj
```

### 2. 가상 환경 생성 및 활성화 (권장)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
pip install gradio-calendar  # 날짜 선택 컴포넌트
```

### 4. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 OpenAI API 키를 설정하세요:

```bash
OPENAI_API_KEY=your_actual_openai_api_key_here
```

## 사용 방법

### 서비스 실행

```bash
python main.py
```

서비스가 실행되면 브라우저에서 `http://localhost:7860`으로 접속할 수 있습니다.

### 기능 사용

#### 1. 지출 입력
- **날짜**: 캘린더에서 선택 또는 YYYY-MM-DD 형식으로 입력
- **카테고리**: 선택사항. 비어있으면 자동으로 분류됩니다.
- **지출 내역**: 지출 내용을 입력 (예: "점심 식사", "지하철 요금")
- **금액**: 숫자로 입력
- **지출처**: 선택사항 (예: "스타벅스", "이마트")

#### 2. CSV 파일 업로드
- CSV 파일 형식:
  - 필수 컬럼: `date`, `description`, `amount`
  - 선택 컬럼: `category`, `merchant`
- 예시:
  ```csv
  date,description,amount,category,merchant
  2024-01-15,점심 식사,15000,식비,맛있는 식당
  2024-01-16,지하철 요금,1400,교통비,
  2024-01-17,커피,5000,,스타벅스
  ```

#### 3. 지출 내역 관리
- **표에서 직접 수정**: 표의 셀을 클릭하여 직접 수정 가능
- **삭제**: "삭제" 컬럼에 체크(True) 표시 후 "변경사항 저장" 버튼 클릭
- **목록 새로고침**: 최신 데이터로 표 업데이트

#### 4. 분석 대시보드
- "분석 새로고침" 버튼을 클릭하여 최신 분석 결과를 확인할 수 있습니다.
- 시작 날짜와 종료 날짜를 선택하여 특정 기간의 분석을 확인할 수 있습니다.
- 날짜를 지정하지 않으면 전체 기간을 분석합니다.
- 카테고리별 통계, MoM 증감 분석, 이상치 분석, 예상 월 지출을 확인할 수 있습니다.
- 바 차트와 파이 차트를 통해 시각적으로 지출 패턴을 확인할 수 있습니다.

#### 5. 리포트 생성
- 사용자 이름을 입력할 수 있습니다 (선택사항).
- 시작 날짜와 종료 날짜를 선택하여 특정 기간의 리포트를 생성할 수 있습니다.
- 날짜를 비워두면 전체 기간의 리포트가 생성됩니다.
- "리포트 생성" 버튼을 클릭하면 로딩 스피너가 표시되고, AI가 분석 결과를 바탕으로 리포트를 생성합니다.
- 리포트는 마크다운 형식으로 생성되며, 소비 패턴 인사이트 및 제안이 포함됩니다.

## Multi-Agent 구조

### 📂DB Agent (`agents/db_agent.py`)
- **역할**: 데이터 입력, 조회, 카테고리 자동 분류
- **도구**:
  - `add_expense`: 지출 데이터 추가
  - `get_expenses`: 기간별 지출 조회
  - `classify_category`: LLM 기반 카테고리 분류

### 📊Analysis Agent (`agents/analysis_agent.py`)
- **역할**: 통계 분석, 이상치 탐지, 예측
- **도구**:
  - `get_category_statistics`: 카테고리별 통계
  - `calculate_mom_growth`: Month-on-Month 증감률
  - `detect_outliers`: 평균+2SD 이상치 탐지
  - `predict_monthly_expense`: 회귀 기반 월 지출 예상
- **최적화**: 리포트 생성 시 LLM 없이 모든 분석 도구를 직접 호출하여 비용 절감 및 성능 향상 (`get_all_analysis()` 메서드)

### 📝Report Agent (`agents/report_agent.py`)
- **역할**: 마크다운 리포트 생성
- **기능**:
  - `generate_report`: 분석 결과를 바탕으로 리포트 생성
  - GPT-4o를 사용하여 소비 패턴 인사이트 및 제안 생성
  - 리포트 헤더(사용자 이름, 분석 기간, 지출 건수) 자동 포함

## 데이터베이스 스키마

### expenses 테이블
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `date`: DATE NOT NULL - 지출 날짜
- `category`: TEXT NOT NULL - 카테고리
- `description`: TEXT NOT NULL - 지출 내역
- `amount`: REAL NOT NULL - 금액
- `merchant`: TEXT - 지출처 (선택사항)
- `created_at`: TIMESTAMP DEFAULT CURRENT_TIMESTAMP - 생성 시간

## 기술 스택

- **LangChain**: Multi-Agent 시스템 구축
- **OpenAI GPT**: 카테고리 분류 및 리포트 생성
  - GPT-3.5-turbo: 카테고리 분류, Analysis Agent
  - GPT-4o: 리포트 생성
- **SQLite**: 데이터베이스
- **Gradio**: 웹 UI
- **gradio-calendar**: 날짜 선택 컴포넌트
- **Pandas/NumPy**: 데이터 분석
- **scikit-learn**: 회귀 분석
- **Plotly**: 차트 생성


## 주의사항

- OpenAI API 키가 필요합니다. API 사용량에 따라 비용이 발생할 수 있습니다.
  - 카테고리 분류: GPT-3.5-turbo 사용
  - 리포트 생성: GPT-4o 사용
- SQLite 데이터베이스 파일(`expenses.db`)은 프로젝트 루트에 자동으로 생성됩니다.
- 초기 실행 시 데이터베이스 테이블이 자동으로 생성됩니다.
- Windows 환경에서 실행 시 asyncio 이벤트 루프 정책이 자동으로 설정됩니다.
