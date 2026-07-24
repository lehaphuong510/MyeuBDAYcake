import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from streamlit_calendar import calendar

# --- CẤU HÌNH GIAO DIỆN & UX/UI ---
st.set_page_config(page_title="Timeline Management", layout="wide")

st.markdown("""
<style>
    h1, h2, h3, h4, .theme-text {
        background: linear-gradient(to right, #D81B60, #8E24AA);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-transform: uppercase;
        white-space: nowrap;
        text-align: left;
        font-weight: bold;
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-weight: bold;
        color: #D81B60;
        font-size: 1.1rem;
    }
    .task-box {
        border-left: 5px solid #D81B60;
        background-color: #fcfcfc;
        padding: 15px;
        margin-bottom: 15px;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .task-title {
        color: #8E24AA;
        font-weight: bold;
        font-size: 1.15em;
        margin-bottom: 8px;
    }
    .stButton>button {
        background: linear-gradient(to right, #D81B60, #8E24AA);
        color: white;
        text-transform: uppercase;
        font-weight: bold;
        border: none;
    }
    .process-box {
        background: linear-gradient(to right, #D81B60, #8E24AA);
        color: white;
        border-radius: 15px;
        padding: 12px;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
        margin-bottom: 15px;
    }
    .overdue-alert {
        background-color: #ffebee;
        color: #c62828;
        padding: 10px;
        border-radius: 5px;
        font-weight: bold;
        margin-bottom: 10px;
        border-left: 5px solid #c62828;
    }
</style>
""", unsafe_allow_html=True)

# NÚT REFRESH DATA BÊN SIDEBAR
with st.sidebar:
    st.markdown("### ⚙️ QUẢN TRỊ")
    if st.button("🔄 LÀM MỚI DỮ LIỆU"):
        st.session_state.clear()
        st.rerun()
    st.caption("Nhấn nút này nếu bạn vừa sửa file Google Sheets và muốn cập nhật lại.")

# --- KẾT NỐI GOOGLE SHEETS ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1SQrD2ps8L9mEXM8UTsqMalI090_mMT3WTLHY9lAhtBI/edit"

@st.cache_resource
def get_google_sheets():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    
    # Gom hết các lệnh mở sheet vào trong cache để không bị chạy lại mỗi khi tick
    sheet = client.open_by_url(SPREADSHEET_URL)
    ws_data = sheet.worksheet("Data")
    ws_tasks = sheet.worksheet("Tasks")
    return ws_data, ws_tasks

ws_data, ws_tasks = get_google_sheets()

# --- HÀM XỬ LÝ DỮ LIỆU LOGIC ---
def load_and_sync_tasks():
    # Load Data gốc
    if "source_data" not in st.session_state:
        st.session_state.source_data = ws_data.get_all_records()
    df_data = pd.DataFrame(st.session_state.source_data)
    
    if 'Ngày sinh nhật' in df_data.columns and 'Ngày giao bánh' in df_data.columns:
        df_data['Ngày sinh nhật'] = df_data.apply(
            lambda row: row['Ngày giao bánh'] if pd.isna(row['Ngày sinh nhật']) or str(row['Ngày sinh nhật']).strip() == '' else row['Ngày sinh nhật'], 
            axis=1
        )
    
    # Load Tasks
    if "tasks_data" not in st.session_state:
        st.session_state.tasks_data = ws_tasks.get_all_records()
        
    df_tasks = pd.DataFrame(st.session_state.tasks_data)
    existing_task_ids = df_tasks['Task_ID'].astype(str).tolist() if not df_tasks.empty else []
    
    new_tasks_to_add = []
    new_tasks_for_state = []
    
    for idx, row in df_data.iterrows():
        ten = str(row.get('Tên', '')).strip()
        if not ten: continue
        
        ngay_giao_str = str(row.get('Ngày giao bánh', ''))
        try:
            ngay_giao = datetime.strptime(ngay_giao_str, "%d/%m/%Y").date()
        except:
            continue
            
        tp = str(row.get('TP', '')).strip()
        loai_banh = str(row.get('Loại bánh', '')).strip()
        
        tasks_to_create = []
        if tp == 'TPHCM' or (tp != 'TPHCM' and loai_banh == 'Gato'):
            tasks_to_create = [
                (ngay_giao - timedelta(days=4), "Remind tiệm bánh"),
                (ngay_giao - timedelta(days=1), "Follow up"),
                (ngay_giao, "Giao bánh")
            ]
        elif tp != 'TPHCM' and loai_banh == 'Cookies':
            tasks_to_create = [
                (ngay_giao - timedelta(days=8), "Thông báo với tiệm bánh"),
                (ngay_giao - timedelta(days=4), "Đặt đơn ship"),
                (ngay_giao - timedelta(days=1), "Remind shipper"),
                (ngay_giao, "Giao bánh")
            ]
            
        for t_date, t_name in tasks_to_create:
            task_id = f"{ten}_{t_date.strftime('%Y%m%d')}_{t_name}"
            if task_id not in existing_task_ids:
                row_data = [
                    task_id, t_date.strftime("%d/%m/%Y"), ten, tp, loai_banh, t_name,
                    str(row.get('Tên trên thiệp/ bánh', '')), str(row.get('DT', '')), 
                    str(row.get('Địa chỉ', '')), str(row.get('Lưu ý', '')), "Chưa hoàn thành"
                ]
                new_tasks_to_add.append(row_data)
                
                # Tạo dict để nhét vào RAM
                new_tasks_for_state.append({
                    "Task_ID": task_id, "Ngày thực hiện": row_data[1], "Tên người nhận": ten,
                    "TP": tp, "Loại bánh": loai_banh, "Tên Task": t_name,
                    "Tên trên thiệp": row_data[6], "SĐT": row_data[7], "Địa chỉ": row_data[8],
                    "Lưu ý": row_data[9], "Trạng thái": "Chưa hoàn thành"
                })
                existing_task_ids.append(task_id)
                
    if new_tasks_to_add:
        ws_tasks.append_rows(new_tasks_to_add)
        st.session_state.tasks_data.extend(new_tasks_for_state)
        df_tasks = pd.DataFrame(st.session_state.tasks_data)
        
    return df_tasks

# --- UI RENDERING ---
st.markdown("<h1>BDAY CAKE 19/07<br>TIMELINE MANAGEMENT</h1>", unsafe_allow_html=True)
st.write("---")

df_tasks = load_and_sync_tasks()
df_tasks['Ngày thực hiện'] = pd.to_datetime(df_tasks['Ngày thực hiện'], format="%d/%m/%Y", errors='coerce')
today = datetime.today().date()

# Overdue logic
overdue_tasks = df_tasks[(df_tasks['Ngày thực hiện'].dt.date < today) & (df_tasks['Trạng thái'] != "Hoàn thành")]
if not overdue_tasks.empty:
    for _, r in overdue_tasks.iterrows():
        st.markdown(f"<div class='overdue-alert'>⚠️ {r['Tên người nhận']} - {r['Tên Task']} đã quá deadline</div>", unsafe_allow_html=True)

# 1. TASK MANAGEMENT
st.markdown("<h2>TASK MANAGEMENT</h2>", unsafe_allow_html=True)
tab_cal, tab_todo = st.tabs(["🗓️ LỊCH (CALENDAR)", "📋 TO-DO LIST (CHI TIẾT)"])

with tab_cal:
    calendar_events = []
    for _, r in df_tasks.iterrows():
        prefix = r['Tên người nhận'] if r['Tên người nhận'] != "Khác" else "Khác"
        
        is_done = r['Trạng thái'] == "Hoàn thành"
        is_overdue = r['Ngày thực hiện'].date() < today and not is_done
        
        if is_done:
            bg_color = "#9E9E9E"
        elif is_overdue:
            bg_color = "#E53935"
        else:
            bg_color = "#D81B60"
        
        calendar_events.append({
            "title": f"{prefix} | {r['Tên Task']}",
            "start": r['Ngày thực hiện'].strftime("%Y-%m-%d"),
            "backgroundColor": bg_color,
            "borderColor": bg_color
        })

    calendar_options = {
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek"
        },
        "initialView": "dayGridMonth"
    }
    calendar(events=calendar_events, options=calendar_options)

with tab_todo:
    sub_tab_0, sub_tab_1, sub_tab_2, sub_tab_3 = st.tabs(["⚠️ QUÁ HẠN", "🕒 HÔM NAY", "📆 TRONG VÒNG 8 NGÀY", "📅 TRONG VÒNG 1 THÁNG"])
    
    def render_task_list(df_filter, tab_key_suffix):
        if df_filter.empty:
            st.info("Không có task nào trong giai đoạn này!")
            return
            
        for idx, r in df_filter.iterrows():
            date_str = r['Ngày thực hiện'].strftime('%d/%m/%Y')
            prefix = r['Tên người nhận'] if r['Tên người nhận'] != "Khác" else "Khác"
            tp_loai = f"{r['TP']} - {r['Loại bánh']}" if r['TP'] else ""
            title = f"{date_str} | {prefix} | {tp_loai} - {r['Tên Task']}"
            
            st.markdown(f"""
            <div class='task-box'>
                <div class='task-title'>{title}</div>
                <div><b>Tên thiệp:</b> {r['Tên trên thiệp']} | <b>SĐT:</b> {r['SĐT']}</div>
                <div><b>Địa chỉ:</b> {r['Địa chỉ']}</div>
                <div><b>Lưu ý:</b> {r['Lưu ý']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            is_done = r['Trạng thái'] == "Hoàn thành"
            checked = st.checkbox(f"Hoàn thành task: {r['Tên Task']} ({prefix})", value=is_done, key=f"{r['Task_ID']}_{tab_key_suffix}")
            
            if checked != is_done:
                new_val = "Hoàn thành" if checked else "Chưa hoàn thành"
                
                # Push lên Google Sheets
                row_in_sheet = idx + 2
                ws_tasks.update_cell(row_in_sheet, 11, new_val)
                
                # Sync vào RAM để khỏi load lại API
                st.session_state.tasks_data[idx]['Trạng thái'] = new_val
                st.rerun()

    with sub_tab_0:
        render_task_list(overdue_tasks, "overdue")
    with sub_tab_1:
        render_task_list(df_tasks[df_tasks['Ngày thực hiện'].dt.date == today], "today")
    with sub_tab_2:
        render_task_list(df_tasks[(df_tasks['Ngày thực hiện'].dt.date >= today) & (df_tasks['Ngày thực hiện'].dt.date <= today + timedelta(days=8))], "8days")
    with sub_tab_3:
        render_task_list(df_tasks[(df_tasks['Ngày thực hiện'].dt.date >= today) & (df_tasks['Ngày thực hiện'].dt.date <= today + timedelta(days=30))], "30days")

st.write("---")

# 2. ADD TASK
st.markdown("<h2>ADD THÊM TASK MỚI</h2>", unsafe_allow_html=True)
list_names = [n for n in df_tasks['Tên người nhận'].unique() if n and n != "Khác"]

with st.form("add_task_form"):
    belong_to = st.selectbox("Task này thuộc:", list_names + ["Khác"])
    task_date = st.date_input("Ngày thực hiện")
    task_name = st.text_input("Task (Fill vào)")
    
    submitted = st.form_submit_button("CREATE TASK")
    if submitted and task_name:
        tp, loai, thiep, sdt, diachi, luuy = "", "", "", "", "", ""
        if belong_to != "Khác":
            sample = df_tasks[df_tasks['Tên người nhận'] == belong_to].iloc[0]
            tp, loai, thiep, sdt = sample['TP'], sample['Loại bánh'], sample['Tên trên thiệp'], sample['SĐT']
            diachi, luuy = sample['Địa chỉ'], sample['Lưu ý']
            
        new_id = f"Manual_{belong_to}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        ws_tasks.append_row([
            new_id, task_date.strftime("%d/%m/%Y"), belong_to, tp, loai, task_name,
            thiep, sdt, diachi, luuy, "Chưa hoàn thành"
        ])
        
        # Sync vào RAM ngay lập tức
        st.session_state.tasks_data.append({
            "Task_ID": new_id, "Ngày thực hiện": task_date.strftime("%d/%m/%Y"), 
            "Tên người nhận": belong_to, "TP": tp, "Loại bánh": loai, "Tên Task": task_name,
            "Tên trên thiệp": thiep, "SĐT": sdt, "Địa chỉ": diachi, "Lưu ý": luuy, "Trạng thái": "Chưa hoàn thành"
        })
        st.success("Tạo task thành công!")
        st.rerun()

st.write("---")

# 3. OVERALL PROCESS
st.markdown("<h2>OVERALL PROCESS</h2>", unsafe_allow_html=True)

process_cols = st.columns(3)
grouped = df_tasks.groupby('Tên người nhận')

not_yet, in_progress, completed = [], [], []

for name, group in grouped:
    total = len(group)
    done = len(group[group['Trạng thái'] == "Hoàn thành"])
    if done == 0:
        not_yet.append(name)
    elif done == total:
        completed.append(name)
    else:
        in_progress.append(name)

with process_cols[0]:
    st.markdown("<div class='process-box'>⏳ NOT YET</div>", unsafe_allow_html=True)
    for n in not_yet: st.write(f"- {n}")
with process_cols[1]:
    st.markdown("<div class='process-box'>🚀 IN PROGRESS</div>", unsafe_allow_html=True)
    for n in in_progress: st.write(f"- {n}")
with process_cols[2]:
    st.markdown("<div class='process-box'>✅ COMPLETED</div>", unsafe_allow_html=True)
    for n in completed: st.write(f"- {n}")
