import streamlit as st


# ✅ set_page_config 가 반드시 첫 번째 st 명령어!
st.set_page_config(page_title="대진엔지니어링 스마트 통합시스템", layout="wide")

import pandas as pd
import sqlite3
import gspread
import io
import time
import random
import numpy as np
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
# 상단 import에 추가
from 사출성형_pdf_module import render_phase2_tabs

# tabs 선언에 탭 2개 추가
tabs = st.tabs([
    "🔴 연도별 전기 사용량",
    "📈 전기 사용량 추이분석",
    "🤖 설비별 전기사용량",
    "📋 기준초과 조치 보고서",
    "📄 전기 사용 일지 PDF",
    "🧹 설비 점검표 PDF",
    "📦 설비 검사",
    "📊 데이터 통합 관리",
])

# 탭 렌더링 (한 줄 추가)
# 기존 with tabs[0]: ~ with tabs[5]: 코드 그대로 유지
# 그 아래에 추가:
render_phase2_tabs(tabs[4], tabs[5])

# 기존 tabs[6], tabs[7] 코드도 그대로 유지
with tabs[6]:  # 📦 설비 검사
    ...
with tabs[7]:  # 📊 데이터 통합 관리
    ...


# =============================================
# 1. 페이지 설정 및 자동 새로고침
# =============================================

st_autorefresh(interval=30000, key="datarefresh")

# =============================================
# 2. DB 초기화 (확장: 금속유형, 조치보고서 강화)
# =============================================
def get_connection():
    return sqlite3.connect('사출성형_factory.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS Users (user_id TEXT PRIMARY KEY, name TEXT, role TEXT)")

    # ✅ 확장: 설비 트러블로 인한 대기 (PP/PE/PS)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Monitoring_Log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            사출_type TEXT,
            val REAL,
            status TEXT,
            metal_type TEXT DEFAULT '없음',
            timestamp DATETIME
        )""")

    # ✅ 확장: 조치보고서 테이블 강화
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Action_Report (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id INTEGER,
            사출_type TEXT,
            deviation_val REAL,
            worker_name TEXT,
            action_taken TEXT,
            disposition TEXT,
            root_cause TEXT,
            report_time DATETIME
        )""")

    # ✅ 신규: AI 예측 로그 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AI_Prediction_Log (
            pred_id INTEGER PRIMARY KEY AUTOINCREMENT,
            사출_type TEXT,
            predicted_val REAL,
            risk_level TEXT,
            confidence REAL,
            timestamp DATETIME
        )""")

    cur.execute("INSERT OR IGNORE INTO Users VALUES ('admin', '관리자', 'Manager')")
    cur.execute("INSERT OR IGNORE INTO Users VALUES ('user1', '홍길동', 'Staff')")
    cur.execute("INSERT OR IGNORE INTO Users VALUES ('user2', '김PP수', 'Staff')")
    conn.commit()
    conn.close()

# =============================================
# 3. 데이터 저장 함수
# =============================================
def log_data(사출_type, val, status="정상", metal_type="없음"):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute(
        "INSERT INTO Monitoring_Log (사출_type, val, status, metal_type, timestamp) VALUES (?, ?, ?, ?, ?)",
        (사출_type, val, status, metal_type, now)
    )
    log_id = cur.lastrowid
    conn.commit()
    conn.close()
    return log_id

def save_action_report(log_id, 사출_type, deviation_val, worker_name, action_taken, disposition, root_cause):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("""
        INSERT INTO Action_Report 
        (log_id, 사출_type, deviation_val, worker_name, action_taken, disposition, root_cause, report_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (log_id, 사출_type, deviation_val, worker_name, action_taken, disposition, root_cause, now))
    conn.commit()
    conn.close()

def save_ai_prediction(사출_type, predicted_val, risk_level, confidence):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute(
        "INSERT INTO AI_Prediction_Log (사출_type, predicted_val, risk_level, confidence, timestamp) VALUES (?, ?, ?, ?, ?)",
        (사출_type, predicted_val, risk_level, confidence, now)
    )
    conn.commit()
    conn.close()

# =============================================
# 4. 주기적 알람 체크
# =============================================
def check_periodic_tasks():
    conn = get_connection()
    df_last = pd.read_sql_query(
        "SELECT 사출_type, MAX(timestamp) as last_time FROM Monitoring_Log GROUP BY 사출_type", conn
    )
    conn.close()

    alerts = []
    now = datetime.now()

    oven_last = df_last[df_last['사출_type'] == '설비 가동']
    if oven_last.empty or (
        now - datetime.strptime(oven_last.iloc[0]['last_time'], '%Y-%m-%d %H:%M:%S')
    ).total_seconds() > 600:
        alerts.append("🔥 [사출성형] 10분 경과: 현재 온도를 확인하고 기록하세요!")
        log_data("사출성형", 180.0, "정상(주기적)")

    metal_last = df_last[df_last['사출_type'] == '금형제작']
    if metal_last.empty or (
        now - datetime.strptime(metal_last.iloc[0]['last_time'], '%Y-%m-%d %H:%M:%S')
    ).total_seconds() > 7200:
        alerts.append("🧲 [금형제작] 2시간 경과: 테스트 및 기기 점검이 필요합니다!")

    return alerts

# =============================================
# 5. ✅ 신규: AI 이상 예측 함수 (intactAI 연동 시뮬레이션)
# =============================================
def run_ai_prediction(사출_type, recent_values):
    """
    intactAI Edge 연동 시뮬레이션
    실제 연동 시: intactAI REST API / SDK 호출로 교체
    """
    if len(recent_values) < 3:
        return None

    vals = np.array(recent_values[-10:])  # 최근 10개 데이터
    mean_val = np.mean(vals)
    std_val = np.std(vals)
    trend = vals[-1] - vals[0] if len(vals) > 1 else 0

    if 사출_type == "사출성형":
        # 온도 기준: 175°C 이상 유지 필요
        predicted_next = mean_val + (trend * 0.3) + random.uniform(-1.5, 1.5)
        predicted_next = round(predicted_next, 1)

        if predicted_next < 172:
            risk_level = "🔴 고위험"
            confidence = round(random.uniform(0.82, 0.95), 2)
        elif predicted_next < 175:
            risk_level = "🟡 주의"
            confidence = round(random.uniform(0.70, 0.85), 2)
        else:
            risk_level = "🟢 정상"
            confidence = round(random.uniform(0.88, 0.97), 2)

    elif 사출_type == "금형제작":
        # 금속 탐지 이력 기반 위험도 계산
        detection_rate = sum(1 for v in recent_values if v > 0) / len(recent_values)
        predicted_next = round(detection_rate * 100, 1)

        if detection_rate > 0.1:
            risk_level = "🔴 고위험"
            confidence = round(random.uniform(0.80, 0.93), 2)
        elif detection_rate > 0.03:
            risk_level = "🟡 주의"
            confidence = round(random.uniform(0.70, 0.85), 2)
        else:
            risk_level = "🟢 정상"
            confidence = round(random.uniform(0.85, 0.96), 2)
    else:
        predicted_next = mean_val
        risk_level = "🟢 정상"
        confidence = 0.90

    save_ai_prediction(사출_type, predicted_next, risk_level, confidence)
    return {"predicted_val": predicted_next, "risk_level": risk_level, "confidence": confidence}

# =============================================
# 6. Google Sheets 전송
# =============================================
# 수정 후 (이 코드로 교체하세요)
def send_to_google_sheets(df):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        
        # 1. 파일명을 이미지에 보이는 '원재료입고'로 변경
        # 2. .sheet1 대신 .worksheet("사출성형")를 사용하여 '사출성형' 탭에 저장
        sheet = client.open("원재료입고").worksheet("사출성형")
        
        values = df.values.tolist()
        sheet.append_rows(values)
        return True
    except Exception as e:
        # 에러 발생 시 원인을 터미널에 출력하도록 개선
        print(f"구글 시트 전송 에러: {e}")
        return False

# =============================================
# 7. ✅ 신규: 조치보고서 자동 생성 (Word/PDF 형식 텍스트)
# =============================================
def generate_action_report_text(사출_type, deviation_val, worker_name, action_taken, disposition, root_cause):
    now = datetime.now().strftime('%Y년 %m월 %d일 %H:%M')
    report = f"""
=====================================
       사출성형 이탈 조치 보고서
=====================================
작성일시  : {now}
담당자    : {worker_name}
사출 공정  : {사출_type}
이탈 수치 : {deviation_val}
-------------------------------------
[이탈 원인 분석]
{root_cause}

[즉각 조치 사항]
{action_taken}

[제품 처리 방법]
{disposition}
-------------------------------------
※ 본 보고서는 사출성형 시스템에 자동 저장됩니다.
※ 재발 방지 대책은 월간 검토회의에서 논의됩니다.
=====================================
"""
    return report

# =============================================
# 8. UI 구성
# =============================================
init_db()

# 로그인
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 스마트 사출성형 로그인")
    user_id = st.text_input("사용자 ID (admin / user1 / user2)")
    if st.button("로그인"):
        conn = get_connection()
        user = pd.read_sql_query(f"SELECT * FROM Users WHERE user_id='{user_id}'", conn)
        conn.close()
        if not user.empty:
            st.session_state.logged_in = True
            st.session_state.user_name = user.iloc[0]['name']
            st.session_state.role = user.iloc[0]['role']
            st.rerun()
        else:
            st.error("등록되지 않은 아이디입니다.")
    st.stop()

# 사이드바
st.sidebar.title(f"👤 {st.session_state.user_name}님")
st.sidebar.caption(f"권한: {st.session_state.role}")
if st.sidebar.button("로그아웃"):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown("**⚙️ 시스템 상태**")
st.sidebar.success("🟢 intactAI Edge 연결됨")
st.sidebar.info("🔄 30초마다 자동 갱신")

st.title("🍞 '대진 엔지니어링' 스마트 사출성형 통합 관리 시스템 v2.0")

# 주기 알람
alerts = check_periodic_tasks()
for alert in alerts:
    st.warning(alert)

# 탭 구성
tabs = st.tabs([
    "🔴 사출 실시간 점검",
    "📈 온도 트렌드 차트",       # ✅ 신규
    "🤖 AI 이상 예측",           # ✅ 신규
    "📋 이탈 조치 보고서",       # ✅ 신규
    "📦 입고/제품 검사",
    "📊 데이터 통합 관리"
])

# ─────────────────────────────────────────
# TAB 1: 사출 실시간 점검 (금속유형 구분 추가)
# ─────────────────────────────────────────
with tabs[0]:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔥 성형 가열 (사출-1)")
        st.caption("기준: 175°C 이상 유지")
        temp = st.number_input("현재 온도 (°C)", 160.0, 220.0, 180.0, step=0.5)
        
        # 실시간 게이지 표시
        if temp >= 175:
            st.success(f"✅ 현재 온도: **{temp}°C** — 기준 충족")
        else:
            st.error(f"⚠️ 현재 온도: **{temp}°C** — 기준 미달 (이탈!)")

        if st.button("🌡️ 온도 수동 기록", key="oven_log"):
            status = "이탈" if temp < 175 else "정상"
            log_id = log_data("성형가열", temp, status)
            if status == "이탈":
                st.error(f"🚨 이탈 기록됨 (log_id={log_id}) → '이탈 조치 보고서' 탭에서 보고서를 작성하세요!")
                st.session_state['last_deviation'] = {
                    'log_id': log_id, '사출_type': '성형가열', 'val': temp
                }
            else:
                st.success("✅ 정상 기록 완료")

    with col2:
        st.subheader("🧲 사출 성형 (사출-2)")
        st.caption("기준: 금속 미검출 /   테스트 통과")

        # ✅ 확장: PP/비PP 구분 탐지
        detection_mode = st.radio(
            "검출 결과",
            ["미검출 (정상)", "PP(Fe) 검출", "비PP(Non-Fe) 검출"],
            horizontal=True
        )

        if detection_mode == "미검출 (정상)":
            st.success("✅ 금속 미검출 — 정상")
            metal_type = "없음"
            metal_status = "정상"
        elif detection_mode == "PP(Fe) 검출":
            st.error("🚨 PP(Fe) 사출 성형! 즉시 라인 정지 및 제품 격리 필요")
            metal_type = "PP(Fe)"
            metal_status = "이탈-PP검출"
        else:
            st.error("🚨 비PP(Non-Fe) 사출 성형! 스테인리스/알루미늄 오염 확인 필요")
            metal_type = "비PP(Non-Fe)"
            metal_status = "이탈-비PP검출"

        size_fe = st.number_input("PP(Fe)   크기 (mm)", 0.5, 5.0, 1.5, step=0.1)
        size_non_fe = st.number_input("비PP(Non-Fe)   크기 (mm)", 0.5, 5.0, 2.0, step=0.1)

        if st.button("🧪 사출 성형 결과 기록", key="metal_log"):
            log_id = log_data("금속검출", size_fe if "PP(Fe)" in metal_type else size_non_fe, metal_status, metal_type)
            if "이탈" in metal_status:
                st.error(f"🚨 이탈 기록됨 (log_id={log_id}) → '이탈 조치 보고서' 탭에서 보고서를 작성하세요!")
                st.session_state['last_deviation'] = {
                    'log_id': log_id, '사출_type': f'금속검출({metal_type})', 'val': size_fe
                }
            else:
                st.success("✅ 정상 기록 완료")

        if st.button("✅   테스트 통과 기록", key="metal_ok"):
            log_data("금속검출", 0.0, "정상", "없음")
            st.success("정기 점검 기록 완료")

# ─────────────────────────────────────────
# TAB 2: ✅ 신규 — 온도 트렌드 차트
# ─────────────────────────────────────────
with tabs[1]:
    st.subheader("📈 성형 가열 온도 트렌드")

    conn = get_connection()
    df_temp = pd.read_sql_query(
        "SELECT val, status, timestamp FROM Monitoring_Log WHERE 사출_type='성형가열' ORDER BY timestamp DESC LIMIT 50",
        conn
    )
    conn.close()

    if df_temp.empty:
        st.info("아직 온도 데이터가 없습니다. 사출 점검 탭에서 데이터를 입력해주세요.")
    else:
        df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'])
        df_temp = df_temp.sort_values('timestamp')
        df_temp = df_temp.rename(columns={'val': '온도(°C)', 'timestamp': '시간'})

        # 기준선 추가
        df_temp['기준온도(175°C)'] = 175

        import plotly.graph_objects as go
        fig = go.Figure()

        # 정상/이탈 구분 색상
        colors = ['red' if s == '이탈' else 'blue' for s in df_temp['status']]

        fig.add_trace(go.Scatter(
            x=df_temp['시간'], y=df_temp['온도(°C)'],
            mode='lines+markers',
            name='실측 온도',
            line=dict(color='royalblue', width=2),
            marker=dict(color=colors, size=8, symbol='circle')
        ))
        fig.add_trace(go.Scatter(
            x=df_temp['시간'], y=df_temp['기준온도(175°C)'],
            mode='lines',
            name='기준온도 (175°C)',
            line=dict(color='red', width=1.5, dash='dash')
        ))
        fig.add_hrect(y0=0, y1=175, fillcolor="red", opacity=0.05, line_width=0)
        fig.update_layout(
            title="성형 가열 온도 이력 (최근 50건)",
            xaxis_title="시간",
            yaxis_title="온도 (°C)",
            legend=dict(orientation="h"),
            height=400,
            plot_bgcolor='white',
            yaxis=dict(range=[160, 220])
        )
        st.plotly_chart(fig, use_container_width=True)

        # 이탈 건수 요약
        total = len(df_temp)
        deviated = (df_temp['status'] == '이탈').sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("총 기록 건수", total)
        c2.metric("이탈 건수", deviated, delta=f"-{deviated}" if deviated > 0 else "0", delta_color="inverse")
        c3.metric("정상률", f"{round((total-deviated)/total*100,1)}%" if total > 0 else "-")

    st.divider()
    st.subheader("🧲 사출 성형 이력")

    conn = get_connection()
    df_metal = pd.read_sql_query(
        "SELECT metal_type, status, timestamp FROM Monitoring_Log WHERE 사출_type='금속검출' ORDER BY timestamp DESC LIMIT 30",
        conn
    )
    conn.close()

    if df_metal.empty:
        st.info("아직 사출 성형 데이터가 없습니다.")
    else:
        df_metal['timestamp'] = pd.to_datetime(df_metal['timestamp'])
        metal_counts = df_metal[df_metal['metal_type'] != '없음']['metal_type'].value_counts().reset_index()
        metal_counts.columns = ['금속 유형', '검출 건수']
        if not metal_counts.empty:
            import plotly.express as px
            fig2 = px.bar(
                metal_counts, x='금속 유형', y='검출 건수',
                color='금속 유형',
                color_discrete_map={'PP(Fe)': '#e74c3c', '비PP(Non-Fe)': '#f39c12'},
                title="금속 유형별 검출 건수"
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.success("✅ 최근 검출 이력 없음 — 정상 운영 중")

# ─────────────────────────────────────────
# TAB 3: ✅ 신규 — AI 이상 예측 (intactAI)
# ─────────────────────────────────────────
with tabs[2]:
    st.subheader("🤖 AI 이상 예측 — intactAI Edge 연동")
    st.caption("최근 데이터를 기반으로 AI가 다음 공정의 이상 가능성을 예측합니다.")

    conn = get_connection()
    df_ai_oven = pd.read_sql_query(
        "SELECT val FROM Monitoring_Log WHERE 사출_type='성형가열' ORDER BY timestamp DESC LIMIT 20", conn
    )
    df_ai_metal = pd.read_sql_query(
        "SELECT val FROM Monitoring_Log WHERE 사출_type='금속검출' ORDER BY timestamp DESC LIMIT 20", conn
    )
    conn.close()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔥 성형 가열 예측")
        if len(df_ai_oven) >= 3:
            pred_oven = run_ai_prediction("성형가열", df_ai_oven['val'].tolist())
            if pred_oven:
                risk_color = "🔴" if "고위험" in pred_oven['risk_level'] else ("🟡" if "주의" in pred_oven['risk_level'] else "🟢")
                st.metric("예측 다음 온도", f"{pred_oven['predicted_val']}°C")
                st.metric("위험 등급", pred_oven['risk_level'])
                st.metric("예측 신뢰도", f"{int(pred_oven['confidence']*100)}%")
                if "고위험" in pred_oven['risk_level']:
                    st.error("⚠️ AI 경보: 다음 측정에서 온도 이탈 가능성 높음! 예열 상태를 즉시 확인하세요.")
                elif "주의" in pred_oven['risk_level']:
                    st.warning("⚡ AI 주의: 온도 하강 추세 감지. 주의 깊게 모니터링하세요.")
                else:
                    st.success("✅ AI 판단: 정상 범위 유지 예측")
        else:
            st.info("예측을 위해 최소 3건 이상의 온도 데이터가 필요합니다.")

    with col2:
        st.markdown("#### 🧲 사출 성형 예측")
        if len(df_ai_metal) >= 3:
            pred_metal = run_ai_prediction("금속검출", df_ai_metal['val'].tolist())
            if pred_metal:
                st.metric("탐지 위험도 점수", f"{pred_metal['predicted_val']}%")
                st.metric("위험 등급", pred_metal['risk_level'])
                st.metric("예측 신뢰도", f"{int(pred_metal['confidence']*100)}%")
                if "고위험" in pred_metal['risk_level']:
                    st.error("⚠️ AI 경보: 금속 오염 빈도 급증 감지! 장비 정밀 점검 및 원자재 공급사 확인 필요.")
                elif "주의" in pred_metal['risk_level']:
                    st.warning("⚡ AI 주의: 산발적 금속 탐지 증가 추세.   테스트 주기를 단축하세요.")
                else:
                    st.success("✅ AI 판단: 금속 오염 위험 낮음")
        else:
            st.info("예측을 위해 최소 3건 이상의 금속검출 데이터가 필요합니다.")

    st.divider()
    st.subheader("📜 AI 예측 이력")
    conn = get_connection()
    df_pred_log = pd.read_sql_query(
        "SELECT * FROM AI_Prediction_Log ORDER BY timestamp DESC LIMIT 20", conn
    )
    conn.close()
    if not df_pred_log.empty:
        st.dataframe(df_pred_log, use_container_width=True)
    else:
        st.info("AI 예측 이력이 없습니다. 위 버튼으로 예측을 실행하세요.")

    st.info("""
    **📌 intactAI 실제 연동 방법**
    - `run_ai_prediction()` 함수 내부를 intactAI REST API 호출로 교체
    - Edge 디바이스에서 실시간 센서값을 직접 intactAI SDK로 전달
    - 예: `intactai.predict(sensor_data=recent_values, model='사출성형_oven_v1')`
    """)

# ─────────────────────────────────────────
# TAB 4: ✅ 신규 — 이탈 조치 보고서 자동 생성
# ─────────────────────────────────────────
with tabs[3]:
    st.subheader("📋 이탈 조치 보고서 작성")

    # 최근 이탈 데이터 자동 불러오기
    conn = get_connection()
    df_dev = pd.read_sql_query(
        "SELECT log_id, 사출_type, val, status, metal_type, timestamp FROM Monitoring_Log WHERE status LIKE '%이탈%' ORDER BY timestamp DESC LIMIT 10",
        conn
    )
    conn.close()

    if df_dev.empty:
        st.info("이탈 기록이 없습니다. 사출 점검 탭에서 이탈 데이터를 기록하면 여기서 보고서를 작성할 수 있습니다.")
    else:
        # 이탈 건 선택
        dev_options = {
            f"[{row['timestamp']}] {row['사출_type']} — {row['status']} (val={row['val']})": row['log_id']
            for _, row in df_dev.iterrows()
        }
        selected_label = st.selectbox("📌 보고서를 작성할 이탈 건 선택", list(dev_options.keys()))
        selected_log_id = dev_options[selected_label]
        selected_row = df_dev[df_dev['log_id'] == selected_log_id].iloc[0]

        st.info(f"선택된 이탈: **{selected_row['사출_type']}** | 이탈값: **{selected_row['val']}** | 시각: **{selected_row['timestamp']}**")

        with st.form("action_report_form"):
            worker_name = st.text_input("담당자 이름", value=st.session_state.user_name)
            root_cause = st.text_area("이탈 원인 분석", placeholder="예: 성형 히터 노후화로 인한 온도 불균일 발생...")
            action_taken = st.text_area("즉각 조치 사항", placeholder="예: 라인 일시 정지 후 히터 점검, 온도 재조정 후 재가동...")
            disposition = st.selectbox("제품 처리 방법", [
                "재처리 후 출하", "폐기 처리", "보류(추가 검사 필요)", "출하 가능(경미한 이탈)"
            ])
            submitted = st.form_submit_button("📝 보고서 저장 및 생성")

        if submitted:
            save_action_report(
                selected_log_id, selected_row['사출_type'], selected_row['val'],
                worker_name, action_taken, disposition, root_cause
            )
            report_text = generate_action_report_text(
                selected_row['사출_type'], selected_row['val'],
                worker_name, action_taken, disposition, root_cause
            )
            st.success("✅ 조치 보고서가 DB에 저장되었습니다!")
            st.text_area("📄 생성된 보고서 미리보기", report_text, height=350)

            # 텍스트 파일 다운로드
            st.download_button(
                "📥 보고서 텍스트 다운로드",
                report_text.encode('utf-8'),
                file_name=f"사출성형_이탈보고서_{selected_row['사출_type']}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
            )

    st.divider()
    st.subheader("📜 조치 보고서 이력")
    conn = get_connection()
    df_reports = pd.read_sql_query("SELECT * FROM Action_Report ORDER BY report_time DESC", conn)
    conn.close()
    if not df_reports.empty:
        st.dataframe(df_reports, use_container_width=True)
    else:
        st.info("작성된 보고서가 없습니다.")

# ─────────────────────────────────────────
# TAB 5: 입고/제품 검사
# ─────────────────────────────────────────
with tabs[4]:
    st.subheader("기타 공정 데이터 입력")
    process = st.selectbox("공정 선택", ["원료 입고 검사", "최종 제품 품질 검사"])
    val_text = st.text_input("점검 결과/수치")
    if st.button("공정 데이터 저장"):
        log_data(process, 0.0, val_text)
        st.success(f"{process} 기록 저장됨")

# ─────────────────────────────────────────
# TAB 6: 데이터 통합 관리
# ─────────────────────────────────────────
with tabs[5]:
    st.subheader("데이터 분석 및 내보내기")
    conn = get_connection()
    df_all = pd.read_sql_query("SELECT * FROM Monitoring_Log ORDER BY timestamp DESC", conn)
    conn.close()

    st.dataframe(df_all, use_container_width=True)

    st.divider()
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("📤 구글 시트 데이터 누적 전송"):
            if send_to_google_sheets(df_all):
                st.success("구글 시트 하단에 데이터가 추가되었습니다.")
            else:
                st.error("전송 실패 (credentials.json 확인 필요)")

    with c2:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_all.to_excel(writer, index=False, sheet_name='사출성형_LOG')
        st.download_button("📥 엑셀(.xlsx) 다운로드", output.getvalue(), "사출성형_Report.xlsx")

    with c3:
        csv = df_all.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 CSV 다운로드", csv, "사출성형_Report.csv")

st.caption("Intact AI Edge System v2.0 | 실시간 네트워크 독립형 사출성형 솔루션 | 금속유형 구분 · AI 예측 · 자동 보고서")
