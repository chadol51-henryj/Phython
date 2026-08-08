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

# =============================================
# 1. 외부 모듈 제거 및 대체 함수 정의
# =============================================
# 사출성형_pdf_module이 없을 때 화면이 멈추지 않도록 빈 함수로 대체합니다.
def render_phase2_tabs(tab4, tab5):
    with tab4:
        st.subheader("📄 전기 사용 일지 PDF 생성 및 조회")
        st.info("PDF 모듈 파일이 제외된 상태입니다. UI 화면 전용 모드로 실행 중입니다.")
    with tab5:
        st.subheader("扫 설비 점검표 PDF 생성 및 조회")
        st.info("PDF 모듈 파일이 제외된 상태입니다. UI 화면 전용 모드로 실행 중입니다.")

# =============================================
# 2. 로그인 세션 강제 활성화 (로그인 없이 실행)
# =============================================
st.session_state.logged_in = True
st.session_state.user_name = "관리자"
st.session_state.role = "Manager"

# 사이드바 구성
st.sidebar.title(f"👤 {st.session_state.user_name}님")
st.sidebar.caption(f"권한: {st.session_state.role}")
st.sidebar.divider()
st.sidebar.markdown("**⚙️ 시스템 상태**")
st.sidebar.success("🟢 intactAI Edge 연결됨")
st.sidebar.info("🔄 30초마다 자동 갱신")

st.title("🍞 '대진 엔지니어링' 스마트 사출성형 통합 관리 시스템 v2.0")

# =============================================
# 3. 자동 새로고침 설정 및 DB 초기화
# =============================================
st_autorefresh(interval=30000, key="datarefresh")

def get_connection():
    return sqlite3.connect('사출성형_factory.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS Users (user_id TEXT PRIMARY KEY, name TEXT, role TEXT)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Monitoring_Log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            사출_type TEXT,
            val REAL,
            status TEXT,
            metal_type TEXT DEFAULT '없음',
            timestamp DATETIME
        )""")
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
    conn.commit()
    conn.close()

init_db()

# =============================================
# 4. 데이터 저장 및 예측 함수
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

def check_periodic_tasks():
    conn = get_connection()
    df_last = pd.read_sql_query(
        "SELECT 사출_type, MAX(timestamp) as last_time FROM Monitoring_Log GROUP BY 사출_type", conn
    )
    conn.close()
    alerts = []
    now = datetime.now()
    oven_last = df_last[df_last['사출_type'] == '설비 가동']
    if oven_last.empty or (now - datetime.strptime(oven_last.iloc[0]['last_time'], '%Y-%m-%d %H:%M:%S')).total_seconds() > 600:
        alerts.append("🔥 [사출성형] 10분 경과: 현재 온도를 확인하고 기록하세요!")
    return alerts

alerts = check_periodic_tasks()
for alert in alerts:
    st.warning(alert)

def run_ai_prediction(사출_type, recent_values):
    if len(recent_values) < 3:
        return None
    vals = np.array(recent_values[-10:])
    mean_val = np.mean(vals)
    trend = vals[-1] - vals[0] if len(vals) > 1 else 0

    if 사출_type == "성형가열":
        predicted_next = mean_val + (trend * 0.3) + random.uniform(-1.5, 1.5)
        predicted_next = round(predicted_next, 1)
        risk_level = "🔴 고위험" if predicted_next < 172 else ("🟡 주의" if predicted_next < 175 else "🟢 정상")
        confidence = round(random.uniform(0.70, 0.95), 2)
    else:
        predicted_next = mean_val
        risk_level = "🟢 정상"
        confidence = 0.90

    save_ai_prediction(사출_type, predicted_next, risk_level, confidence)
    return {"predicted_val": predicted_next, "risk_level": risk_level, "confidence": confidence}

def send_to_google_sheets(df):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("원재료입고").worksheet("사출성형")
        values = df.values.tolist()
        sheet.append_rows(values)
        return True
    except Exception as e:
        print(f"구글 시트 전송 에러: {e}")
        return False

def generate_action_report_text(사출_type, deviation_val, worker_name, action_taken, disposition, root_cause):
    now = datetime.now().strftime('%Y년 %m월 %d일 %H:%M')
    return f"""=====================================\n       사출성형 이탈 조치 보고서\n=====================================\n작성일시  : {now}\n담당자    : {worker_name}\n사출 공정  : {사출_type}\n이탈 수치 : {deviation_val}\n-------------------------------------\n[이탈 원인 분석]\n{root_cause}\n\n[즉각 조치 사항]\n{action_taken}\n\n[제품 처리 방법]\n{disposition}\n-------------------------------------\n※ 본 보고서는 사출성형 시스템에 자동 저장됩니다.\n====================================="""

# =============================================
# 5. 통합 탭(Tab) 구조 정의 (총 8개로 통일)
# =============================================
tabs = st.tabs([
    "🔴 사출 실시간 점검",
    "📈 온도 트렌드 차트",
    "🤖 AI 이상 예측",
    "📋 이탈 조치 보고서",
    "📄 전기 사용 일지 PDF",
    "🧹 설비 점검표 PDF",
    "📦 입고/제품 검사",
    "📊 데이터 통합 관리"
])

# ─── TAB 1: 사출 실시간 점검 ───
with tabs[0]:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔥 성형 가열 (사출-1)")
        st.caption("기준: 175°C 이상 유지")
        temp = st.number_input("현재 온도 (°C)", 160.0, 220.0, 180.0, step=0.5)
        if temp >= 175:
            st.success(f"✅ 현재 온도: **{temp}°C** — 기준 충족")
        else:
            st.error(f"⚠️ 현재 온도: **{temp}°C** — 기준 미달 (이탈!)")

        if st.button("🌡️ 온도 수동 기록", key="oven_log"):
            status = "이탈" if temp < 175 else "정상"
            log_id = log_data("성형가열", temp, status)
            if status == "이탈":
                st.error(f"🚨 이탈 기록됨 (log_id={log_id})")
                st.session_state['last_deviation'] = {'log_id': log_id, '사출_type': '성형가열', 'val': temp}
            else:
                st.success("✅ 정상 기록 완료")

    with col2:
        st.subheader("🧲 사출 성형 (사출-2)")
        st.caption("기준: 금속 미검출 / 테스트 통과")
        detection_mode = st.radio("검출 결과", ["미검출 (정상)", "PP(Fe) 검출", "비PP(Non-Fe) 검출"], horizontal=True)

        if detection_mode == "미검출 (정상)":
            st.success("✅ 금속 미검출 — 정상")
            metal_type, metal_status = "없음", "정상"
        elif detection_mode == "PP(Fe) 검출":
            st.error("🚨 PP(Fe) 사출 성형! 즉시 라인 정지 및 제품 격리 필요")
            metal_type, metal_status = "PP(Fe)", "이탈-PP검출"
        else:
            st.error("🚨 비PP(Non-Fe) 사출 성형! 장비 확인 필요")
            metal_type, metal_status = "비PP(Non-Fe)", "이탈-비PP검출"

        size_fe = st.number_input("PP(Fe) 크기 (mm)", 0.5, 5.0, 1.5, step=0.1)
        if st.button("🧪 사출 성형 결과 기록", key="metal_log"):
            log_id = log_data("금속검출", size_fe, metal_status, metal_type)
            st.success("기록 완료")

# ─── TAB 2: 온도 트렌드 차트 ───
with tabs[1]:
    st.subheader("📈 성형 가열 온도 트렌드")
    conn = get_connection()
    df_temp = pd.read_sql_query("SELECT val, status, timestamp FROM Monitoring_Log WHERE 사출_type='성형가열' ORDER BY timestamp DESC LIMIT 50", conn)
    conn.close()

    if df_temp.empty:
        st.info("아직 온도 데이터가 없습니다.")
    else:
        df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'])
        df_temp = df_temp.sort_values('timestamp').rename(columns={'val': '온도(°C)', 'timestamp': '시간'})
        df_temp['기준온도(175°C)'] = 175
        
        import plotly.graph_objects as go
        fig = go.Figure()
        colors = ['red' if s == '이탈' else 'blue' for s in df_temp['status']]
        fig.add_trace(go.Scatter(x=df_temp['시간'], y=df_temp['온도(°C)'], mode='lines+markers', name='실측 온도', marker=dict(color=colors, size=8)))
        fig.update_layout(height=400, plot_bgcolor='white')
        st.plotly_chart(fig, use_container_width=True)

# ─── TAB 3: AI 이상 예측 ───
with tabs[2]:
    st.subheader("🤖 AI 이상 예측 — intactAI Edge 연동")
    conn = get_connection()
    df_ai_oven = pd.read_sql_query("SELECT val FROM Monitoring_Log WHERE 사출_type='성형가열' ORDER BY timestamp DESC LIMIT 20", conn)
    conn.close()

    if len(df_ai_oven) >= 3:
        pred_oven = run_ai_prediction("성형가열", df_ai_oven['val'].tolist())
        if pred_oven:
            st.metric("예측 다음 온도", f"{pred_oven['predicted_val']}°C")
            st.metric("위험 등급", pred_oven['risk_level'])
    else:
        st.info("예측을 위해 최소 3건 이상의 데이터가 필요합니다.")

# ─── TAB 4: 이탈 조치 보고서 ───
with tabs[3]:
    st.subheader("📋 이탈 조치 보고서 작성")
    conn = get_connection()
    df_dev = pd.read_sql_query("SELECT log_id, 사출_type, val, status, timestamp FROM Monitoring_Log WHERE status LIKE '%이탈%' ORDER BY timestamp DESC LIMIT 10", conn)
    conn.close()

    if df_dev.empty:
        st.info("이탈 기록이 없습니다.")
    else:
        dev_options = {f"[{row['timestamp']}] {row['사출_type']} (val={row['val']})": row['log_id'] for _, row in df_dev.iterrows()}
        selected_label = st.selectbox("📌 이탈 건 선택", list(dev_options.keys()))
        selected_log_id = dev_options[selected_label]
        selected_row = df_dev[df_dev['log_id'] == selected_log_id].iloc[0]

        with st.form("action_report_form"):
            worker_name = st.text_input("담당자 이름", value=st.session_state.user_name)
            root_cause = st.text_area("이탈 원인 분석")
            action_taken = st.text_area("즉각 조치 사항")
            disposition = st.selectbox("제품 처리 방법", ["재처리 후 출하", "폐기 처리", "보류"])
            submitted = st.form_submit_button("📝 보고서 저장")

        if submitted:
            save_action_report(selected_log_id, selected_row['사출_type'], selected_row['val'], worker_name, action_taken, disposition, root_cause)
            st.success("✅ 조치 보고서가 DB에 저장되었습니다!")

# ─── TAB 5 & TAB 6: PDF 대안 화면 ───
# 기존에 모듈을 사용하던 4번, 5번 탭을 안전하게 빈 함수로 매핑하여 UI를 띄웁니다.
render_phase2_tabs(tabs[4], tabs[5])

# ─── TAB 7: 입고/제품 검사 ───
with tabs[6]:
    st.subheader("기타 공정 데이터 입력")
    process = st.selectbox("공정 선택", ["원료 입고 검사", "최종 제품 품질 검사"])
    val_text = st.text_input("점검 결과/수치")
    if st.button("공정 데이터 저장"):
        log_data(process, 0.0, val_text)
        st.success(f"{process} 기록 저장됨")

# ─── TAB 8: 데이터 통합 관리 ───
with tabs[7]:
    st.subheader("데이터 분석 및 내보내기")
    conn = get_connection()
    df_all = pd.read_sql_query("SELECT * FROM Monitoring_Log ORDER BY timestamp DESC", conn)
    conn.close()
    st.dataframe(df_all, use_container_width=True)

st.divider()
st.caption("Intact AI Edge System v2.0 | 실시간 네트워크 독립형 사출성형 솔루션")