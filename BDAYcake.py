import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from streamlit_calendar import calendar
import plotly.graph_objects as go
import time

# --- CẤU HÌNH GIAO DIỆN & UX/UI ---
st.set_page_config(page_title="Timeline Management", page_icon="🎂", layout="wide")

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
        cursor: pointer;
        outline: none;
    }
    details > summary { list-style: none; }
    details > summary::-webkit-details-marker { display: none; }
    .task-title::before {
        content: "▶";
        display: inline-block;
        margin-right: 10px;
        color: #D81B60;
        font-size: 0.8em;
        transition: transform 0.2s ease;
    }
    details[open] > .task-title::before { transform: rotate(90deg); }
    .task-content {
        margin-top: 12px;
        padding-top: 12px;
        border-top: 1px dashed #f8bbd0;
        color: #333333;
        line-height: 1.6;
    }
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button {
        background: linear-gradient(to right, #D81B60, #8E24AA) !important;
        color: white !important;
        text-transform: uppercase !important;
        font-weight: bold !important;
        border: none !important;
        transition: 0.3s;
    }
    div.stButton > button[kind="secondary"] {
        background: transparent !important;
        color: #8E24AA !important;
        border: 1.5px solid #D81B60 !important;
        font-weight: bold !important;
        border-radius: 8px !important;
    }
    .process-box { background: linear-gradient(to right, #D81B60, #8E24AA); color: white; border-radius: 15px; padding: 12px; text-align: center; font-weight: bold; font-size: 1.2em; margin-bottom: 5px; }
    .overdue-alert { background-color: #ffebee; color: #c62828; padding: 10px; border-radius: 5px; font-weight: bold; margin-bottom: 10px; border-left: 5px solid #c62828; }
    .agenda-link { display: block; padding: 10px 15px; margin-bottom: 10px; text-decoration: none !important; color: #8E24AA !important; background-color: #fce4ec; border-radius: 8px; font-weight: bold; border-left: 4px solid #D81B60; }
    .note-box { background: linear-gradient(to right, rgba(248, 187, 208, 0.5), rgba(225, 190, 231, 0.5)); padding: 15px; margin-bottom: 5px; border-radius: 8px; color: #4A148C; border-left: 5px solid rgba(171, 71, 188, 0.8); }
    .loc-header-tphcm { background-color: #555555; color: white; text-align: center; border-radius: 5px; font-weight: bold; padding: 6px; margin-bottom: 10px; font-size: 0.9em; }
    .loc-header-khac { background-color: #D81B60; color: white; text-align: center; border-radius: 5px; font-weight: bold; padding: 6px; margin-bottom: 10px; font-size: 0.9em; }
</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI GOOGLE SHEETS ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1SQrD2ps8L9mEXM8UTsqMalI090_mMT3WTLHY9lAhtBI/edit"

@st.cache_resource
def get_google_sheets():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SPREADSHEET_URL)
    ws_data = sheet.worksheet("Data")
    ws_tasks = sheet.worksheet("Tasks")
    sheet_titles = [w.title for w in sheet.worksheets()]
    if "Notes" not in sheet_titles:
        ws_notes = sheet.add_worksheet(title="Notes", rows="100", cols="2")
        ws_notes.append_row(["Thời gian", "Nội dung Note"])
    else: ws_notes = sheet.worksheet("Notes")
    return ws_data, ws_tasks, ws_notes

ws_data, ws_tasks, ws_notes = get_google_sheets()

# --- HÀM XỬ LÝ DỮ LIỆU LOGIC ---
def load_and_sync_tasks():
    if "source_data" not in st.session_state:
        st.session_state.source_data = ws_data.get_all_records()
    df_data = pd.DataFrame(st.session_state.source_data)
    
    if 'Ngày sinh nhật' in df_data.columns and 'Ngày giao bánh' in df_data.columns:
        df_data['Ngày sinh nhật'] = df_data.apply(
            lambda row: row['Ngày giao bánh'] if pd.isna(row['Ngày sinh nhật']) or str(row['Ngày sinh nhật']).strip() == '' else row['Ngày sinh nhật'], 
            axis=1
        )
        
    bday_map = {}
    for _, r in df_data.iterrows():
        t = str(r.get('Tên', '')).strip()
        if t: bday_map[t] = str(r.get('Ngày sinh nhật', ''))
    st.session_state.birthday_map = bday_map
    
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
        try: ngay_giao = datetime.strptime(ngay_giao_str, "%d/%m/%Y").date()
        except: continue
            
        tp = str(row.get('TP', '')).strip()
        loai_banh = str(row.get('Loại bánh', '')).strip()
        sdt = str(row.get('DT', '')).strip()
        if sdt.endswith('.0'): sdt = sdt[:-2] 
        if sdt and not sdt.startswith('0') and sdt.isdigit(): sdt = '0' + sdt
        
        tasks_to_create = []
        if tp == 'TPHCM' or (tp != 'TPHCM' and loai_banh == 'Gato'):
            tasks_to_create = [(ngay_giao - timedelta(days=4), "Remind tiệm bánh"), (ngay_giao - timedelta(days=1), "Follow up"), (ngay_giao, "Giao bánh")]
        elif tp != 'TPHCM' and loai_banh == 'Cookies':
            tasks_to_create = [(ngay_giao - timedelta(days=8), "Thông báo với tiệm bánh"), (ngay_giao - timedelta(days=4), "Đặt đơn ship"), (ngay_giao - timedelta(days=1), "Remind shipper"), (ngay_giao, "Giao bánh")]
            
        bday_str = str(row.get('Ngày sinh nhật', '')).strip()
        if bday_str:
            parts = bday_str.split('/')
            if len(parts) >= 2:
                try:
                    b_day, b_month = int(parts[0]), int(parts[1])
                    b_year = 2026 if 7 <= b_month <= 12 else 2027
                    tasks_to_create.append((datetime(b_year, b_month, b_day).date(), "Gửi Drive CMSN"))
                except ValueError: pass
            
        for t_date, t_name in tasks_to_create:
            task_id = f"{ten}_{t_date.strftime('%Y%m%d')}_{t_name}"
            if task_id not in existing_task_ids:
                row_data = [task_id, t_date.strftime("%d/%m/%Y"), ten, tp, loai_banh, t_name, str(row.get('Tên trên thiệp/ bánh', '')), sdt, str(row.get('Địa chỉ', '')), str(row.get('Lưu ý', '')), "Chưa hoàn thành"]
                new_tasks_to_add.append(row_data)
                new_tasks_for_state.append({
                    "Task_ID": task_id, "Ngày thực hiện": row_data[1], "Tên người nhận": ten, "TP": tp, "Loại bánh": loai_banh, "Tên Task": t_name,
                    "Tên trên thiệp": row_data[6], "SĐT": row_data[7], "Địa chỉ": row_data[8], "Lưu ý": row_data[9], "Trạng thái": "Chưa hoàn thành"
                })
                existing_task_ids.append(task_id)
                
    if new_tasks_to_add:
        ws_tasks.append_rows(new_tasks_to_add)
        st.session_state.tasks_data.extend(new_tasks_for_state)
        df_tasks = pd.DataFrame(st.session_state.tasks_data)
    return df_tasks

df_tasks = load_and_sync_tasks()
if not df_tasks.empty:
    df_tasks['Ngày thực hiện'] = pd.to_datetime(df_tasks['Ngày thực hiện'], format="%d/%m/%Y", errors='coerce')

today = (datetime.utcnow() + timedelta(hours=7)).date()
STANDARD_TASKS = ["Remind tiệm bánh", "Follow up", "Giao bánh", "Thông báo với tiệm bánh", "Đặt đơn ship", "Remind shipper", "Gửi Drive CMSN"]

# --- CÁC HÀM XỬ LÝ CHỈNH SỬA (DIALOGS) ---

@st.dialog("✏️ SỬA TASK LẺ (SỬA NGỌN)")
def edit_single_task_dialog(task_id):
    task_idx = next((i for i, t in enumerate(st.session_state.tasks_data) if t['Task_ID'] == task_id), None)
    if task_idx is None: return
    t_data = st.session_state.tasks_data[task_idx]
    
    with st.form(f"edit_task_{task_id}"):
        try: cur_date = datetime.strptime(t_data['Ngày thực hiện'], "%d/%m/%Y").date()
        except: cur_date = today
        
        new_date = st.date_input("Ngày thực hiện mới", cur_date)
        new_name = st.text_input("Tên Task", t_data['Tên Task'])
        new_note = st.text_area("Lưu ý riêng cho Task này", t_data['Lưu ý'])
        
        if st.form_submit_button("💾 LƯU THAY ĐỔI", type="primary"):
            ws_tasks.update_cell(task_idx + 2, 2, new_date.strftime("%d/%m/%Y"))
            ws_tasks.update_cell(task_idx + 2, 6, new_name)
            ws_tasks.update_cell(task_idx + 2, 10, new_note)
            st.session_state.clear()
            st.rerun()

@st.dialog("🔍 THÔNG TIN CHI TIẾT")
def show_detail_dialog(person_name):
    if person_name == "Khác" or df_tasks.empty:
        st.info("Không có thông tin chi tiết cho mục này.")
        return
        
    p_data = df_tasks[df_tasks['Tên người nhận'] == person_name].iloc[0]
    bday = st.session_state.birthday_map.get(person_name, "Không rõ")
    
    orig_df = pd.DataFrame(st.session_state.source_data)
    p_idx = orig_df.index[orig_df['Tên'] == person_name].tolist()
    
    ngay_giao = "Không rõ"
    if p_idx: ngay_giao = str(orig_df.iloc[p_idx[0]].get('Ngày giao bánh', 'Không rõ')).strip()
    
    sdt = str(p_data['SĐT']).strip()
    if sdt.endswith('.0'): sdt = sdt[:-2]
    if sdt and not sdt.startswith('0') and sdt.isdigit(): sdt = '0' + sdt
        
    st.markdown(f"""
    <div style='font-size: 1.1em; line-height: 1.8; color: #333;'>
        <b>👤 Tên:</b> <span style='color:#D81B60; font-size: 1.15em;'>{person_name}</span><br>
        <b>💌 Tên trên thiệp:</b> {p_data['Tên trên thiệp']}<br>
        <b>🏙️ Thành phố:</b> {p_data['TP']}<br>
        <b>🎂 Loại bánh:</b> {p_data['Loại bánh']}<br>
        <b>🚚 Ngày giao bánh:</b> <span style='color:#8E24AA; font-weight: bold;'>{ngay_giao}</span><br>
        <b>🎈 Ngày sinh nhật:</b> {bday}<br>
        <b>📞 SĐT:</b> {sdt}<br>
        <b>🏠 Địa chỉ:</b> {p_data['Địa chỉ']}<br>
        <b>📝 Lưu ý chung:</b> {p_data['Lưu ý']}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    with st.expander("⚙️ SỬA ĐƠN HÀNG GỐC (Tự động tính lại Task)"):
        if not p_idx:
            st.error("Không tìm thấy dữ liệu gốc trong Sheet Data.")
            return
            
        row_idx = p_idx[0]
        p_orig = orig_df.iloc[row_idx]
        headers = orig_df.columns.tolist()
        
        with st.form(f"edit_root_{person_name}"):
            st.caption("Lưu ý: Sửa ở đây sẽ xóa hết Task cũ và tạo lại toàn bộ Task mới theo Leadtime.")
            c1, c2 = st.columns(2)
            with c1:
                new_tp = st.selectbox("Thành phố", ["TPHCM", "Khác"], index=0 if p_orig.get('TP') == "TPHCM" else 1)
                try: ng_giao_dt = datetime.strptime(str(p_orig.get('Ngày giao bánh', '')), "%d/%m/%Y").date()
                except: ng_giao_dt = today
                new_ngay = st.date_input("Ngày giao bánh mới", ng_giao_dt)
            with c2:
                new_loai = st.selectbox("Loại bánh", ["Gato", "Cookies"], index=0 if p_orig.get('Loại bánh') == "Gato" else 1)
                new_bday = st.text_input("Ngày sinh nhật (DD/MM)", str(p_orig.get('Ngày sinh nhật', '')))
            
            new_note = st.text_area("Lưu ý chung", str(p_orig.get('Lưu ý', '')))
            
            if st.form_submit_button("🔄 LƯU & TẠO LẠI TASK", type="primary"):
                ws_data.update_cell(row_idx+2, headers.index('TP')+1, new_tp)
                ws_data.update_cell(row_idx+2, headers.index('Loại bánh')+1, new_loai)
                ws_data.update_cell(row_idx+2, headers.index('Ngày giao bánh')+1, new_ngay.strftime("%d/%m/%Y"))
                if 'Ngày sinh nhật' in headers: ws_data.update_cell(row_idx+2, headers.index('Ngày sinh nhật')+1, new_bday)
                if 'Lưu ý' in headers: ws_data.update_cell(row_idx+2, headers.index('Lưu ý')+1, new_note)
                
                df_tasks_temp = pd.DataFrame(st.session_state.tasks_data)
                task_indices = df_tasks_temp.index[df_tasks_temp['Tên người nhận'] == person_name].tolist()
                for i in sorted(task_indices, reverse=True): ws_tasks.delete_rows(i + 2)
                    
                st.session_state.clear()
                st.rerun()

# --- SIDEBAR & BỘ LỌC TÌM KIẾM ---
with st.sidebar:
    st.markdown("### ⚙️ QUẢN TRỊ")
    if st.button("🔄 LÀM MỚI DỮ LIỆU", type="primary"):
        st.session_state.clear(); st.rerun()
    st.caption("Nhấn nút này nếu bạn vừa sửa file Google Sheets.")
    st.markdown("---")
    st.markdown("### 🔍 BỘ LỌC NHANH")
    all_names = sorted(list(set([n for n in df_tasks['Tên người nhận'].unique() if n and n != "Khác"]))) if not df_tasks.empty else []
    filter_names = st.multiselect("👤 Tìm theo Khách hàng:", all_names, placeholder="Tất cả...")
    filter_tasks_options = STANDARD_TASKS + ["Khác"]
    filter_tasks = st.multiselect("🏷️ Tìm theo Loại Task:", filter_tasks_options, placeholder="Tất cả...")
    filter_status = st.multiselect("🚦 Trạng thái:", ["Chưa hoàn thành", "Hoàn thành"], default=["Chưa hoàn thành", "Hoàn thành"])
    st.markdown("---")
    st.markdown("### 📑 AGENDA CỦA TRANG")
    st.markdown("""
        <a href="#task-management" target="_self" class="agenda-link">📍 TASK MANAGEMENT</a>
        <a href="#section-add-task" target="_self" class="agenda-link">📍 ADD THÊM TASK MỚI</a>
        <a href="#overall-process" target="_self" class="agenda-link">📍 OVERALL PROCESS</a>
        <a href="#create-note" target="_self" class="agenda-link">📍 CREATE NOTE</a>
    """, unsafe_allow_html=True)

df_filtered = df_tasks.copy()
if not df_filtered.empty:
    if filter_names: df_filtered = df_filtered[df_filtered['Tên người nhận'].isin(filter_names)]
    if filter_tasks:
        if "Khác" in filter_tasks:
            selected_st_tasks = [t for t in filter_tasks if t != "Khác"]
            df_filtered = df_filtered[df_filtered['Tên Task'].isin(selected_st_tasks) | ~df_filtered['Tên Task'].isin(STANDARD_TASKS)]
        else: df_filtered = df_filtered[df_filtered['Tên Task'].isin(filter_tasks)]
    if filter_status: df_filtered = df_filtered[df_filtered['Trạng thái'].isin(filter_status)]

st.markdown("<h1>BDAY CAKE 19/07<br>TIMELINE MANAGEMENT</h1>", unsafe_allow_html=True)
st.write("---")

overdue_tasks = df_filtered[(df_filtered['Ngày thực hiện'].dt.date < today) & (df_filtered['Trạng thái'] != "Hoàn thành")]
if not overdue_tasks.empty:
    for _, r in overdue_tasks.iterrows():
        st.markdown(f"<div class='overdue-alert'>⚠️ {r['Tên người nhận']} - {r['Tên Task']} đã quá deadline</div>", unsafe_allow_html=True)

# ==========================================
# 1. TASK MANAGEMENT
# ==========================================
st.markdown("<h2 id='task-management'>TASK MANAGEMENT</h2>", unsafe_allow_html=True)
tab_cal, tab_todo = st.tabs(["🗓️ LỊCH (CALENDAR)", "📋 TO-DO LIST (CHI TIẾT)"])

with tab_cal:
    calendar_events = []
    for _, r in df_filtered.iterrows():
        prefix = r['Tên người nhận'] if r['Tên người nhận'] != "Khác" else "Khác"
        is_done = r['Trạng thái'] == "Hoàn thành"
        is_overdue = r['Ngày thực hiện'].date() < today and not is_done
        task_name = str(r['Tên Task']).strip().lower()
        event_class = ""
        
        if is_done: bg_color = "#9E9E9E" 
        elif is_overdue: bg_color = "#c62828" 
        elif task_name == "giao bánh": bg_color = "#8E24AA"  
        elif task_name == "gửi drive cmsn": bg_color = "transparent"; event_class = "bday-task-gradient"
        else: bg_color = "#D81B60"  
            
        event_obj = {"title": f"{prefix} | {r['Tên Task']}", "start": r['Ngày thực hiện'].strftime("%Y-%m-%d"), "backgroundColor": bg_color, "borderColor": "transparent"}
        if event_class: event_obj["className"] = event_class
        calendar_events.append(event_obj)

    calendar_options = {"headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek"}, "initialView": "dayGridMonth"}
    custom_calendar_css = """
    .fc .fc-button-primary { background-image: none !important; border: none !important; box-shadow: none !important; text-transform: uppercase !important; font-weight: bold !important; }
    .fc .fc-today-button { background-color: transparent !important; color: #D81B60 !important; border: none !important; }
    .fc .fc-dayGridMonth-button, .fc .fc-timeGridWeek-button { background-color: #000000 !important; color: white !important; }
    .fc .fc-dayGridMonth-button.fc-button-active, .fc .fc-timeGridWeek-button.fc-button-active { background-color: #D81B60 !important; }
    .bday-task-gradient { background: linear-gradient(to right, #FF7043, #FFCA28) !important; border: none !important; box-shadow: 0 1px 3px rgba(0,0,0,0.2) !important; }
    .bday-task-gradient .fc-event-main, .bday-task-gradient .fc-event-title, .bday-task-gradient .fc-event-time { color: #4A148C !important; font-weight: bold !important; }
    """
    cal_widget = calendar(events=calendar_events, options=calendar_options, custom_css=custom_calendar_css, key="main_calendar")
    if cal_widget.get("callback") == "eventClick":
        clicked_title = cal_widget["eventClick"]["event"]["title"]
        person_name = clicked_title.split(" | ")[0].strip()
        if person_name != "Khác": show_detail_dialog(person_name)

with tab_todo:
    sub_tab_0, sub_tab_1, sub_tab_2, sub_tab_3, sub_tab_4, sub_tab_5, sub_tab_6 = st.tabs([
        "⚠️ QUÁ HẠN", "🕒 HÔM NAY", "🌅 NGÀY MAI", "⏳ 4 NGÀY", "📆 8 NGÀY", "📅 1 THÁNG", "♾️ TẤT CẢ"
    ])
    
    def render_task_list(df_render, tab_key_suffix):
        if df_render.empty:
            st.info("Không có task nào thỏa mãn điều kiện!")
            return
        df_render = df_render.sort_values(by='Ngày thực hiện', ascending=True)
        for _, r in df_render.iterrows():
            date_str = r['Ngày thực hiện'].strftime('%d/%m/%Y')
            prefix = r['Tên người nhận'] if r['Tên người nhận'] != "Khác" else "Khác"
            tp_loai = f"{r['TP']} - {r['Loại bánh']}" if r['TP'] else ""
            title = f"{date_str} | {prefix} | {tp_loai} - {r['Tên Task']}"
            bday = st.session_state.birthday_map.get(prefix, "")
            
            sdt_ht = str(r['SĐT']).strip()
            if sdt_ht.endswith('.0'): sdt_ht = sdt_ht[:-2]
            if sdt_ht and not sdt_ht.startswith('0') and sdt_ht.isdigit(): sdt_ht = '0' + sdt_ht
            
            st.markdown(f"""
            <div class='task-box'>
                <details><summary class='task-title'>{title}</summary>
                    <div class='task-content'>
                        <div><b>Sinh nhật:</b> {bday} | <b>Thiệp:</b> {r['Tên trên thiệp']} | <b>SĐT:</b> {sdt_ht}</div>
                        <div><b>Địa chỉ:</b> {r['Địa chỉ']}</div>
                        <div><b>Lưu ý:</b> {r['Lưu ý']}</div>
                    </div>
                </details>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns([8, 2])
            with c1:
                is_done = r['Trạng thái'] == "Hoàn thành"
                checked = st.checkbox(f"Hoàn thành task: {r['Tên Task']}", value=is_done, key=f"{r['Task_ID']}_{tab_key_suffix}")
                if checked != is_done:
                    new_val = "Hoàn thành" if checked else "Chưa hoàn thành"
                    for real_idx, task_dict in enumerate(st.session_state.tasks_data):
                        if task_dict['Task_ID'] == r['Task_ID']:
                            ws_tasks.update_cell(real_idx + 2, 11, new_val)
                            st.session_state.tasks_data[real_idx]['Trạng thái'] = new_val
                            break
                    st.rerun()
            with c2:
                if st.button("✏️ Edit", key=f"edit_btn_{r['Task_ID']}_{tab_key_suffix}"):
                    edit_single_task_dialog(r['Task_ID'])

    with sub_tab_0: render_task_list(overdue_tasks, "overdue")
    with sub_tab_1: render_task_list(df_filtered[df_filtered['Ngày thực hiện'].dt.date == today], "today")
    with sub_tab_2: render_task_list(df_filtered[df_filtered['Ngày thực hiện'].dt.date == today + timedelta(days=1)], "tomorrow")
    with sub_tab_3: render_task_list(df_filtered[(df_filtered['Ngày thực hiện'].dt.date >= today) & (df_filtered['Ngày thực hiện'].dt.date <= today + timedelta(days=4))], "4days")
    with sub_tab_4: render_task_list(df_filtered[(df_filtered['Ngày thực hiện'].dt.date >= today) & (df_filtered['Ngày thực hiện'].dt.date <= today + timedelta(days=8))], "8days")
    with sub_tab_5: render_task_list(df_filtered[(df_filtered['Ngày thực hiện'].dt.date >= today) & (df_filtered['Ngày thực hiện'].dt.date <= today + timedelta(days=30))], "30days")
    with sub_tab_6: render_task_list(df_filtered[df_filtered['Ngày thực hiện'].dt.date >= today], "all_time")

st.write("---")

# ==========================================
# 2. ADD TASK
# ==========================================
st.markdown("<div id='section-add-task'></div><h2>ADD THÊM TASK MỚI</h2>", unsafe_allow_html=True)
list_names = [n for n in df_tasks['Tên người nhận'].unique() if n and n != "Khác"]

with st.form("add_task_form", clear_on_submit=True):
    belong_to = st.selectbox("Task này thuộc:", list_names + ["Khác"])
    task_date = st.date_input("Ngày thực hiện")
    task_name = st.text_input("Task (Fill vào)")
    submitted = st.form_submit_button("CREATE TASK", type="primary")
    msg_placeholder = st.empty() 
    
    if submitted and task_name:
        tp, loai, thiep, sdt, diachi, luuy = "", "", "", "", "", ""
        if belong_to != "Khác":
            sample = df_tasks[df_tasks['Tên người nhận'] == belong_to].iloc[0]
            tp, loai, thiep = sample['TP'], sample['Loại bánh'], sample['Tên trên thiệp']
            diachi, luuy = sample['Địa chỉ'], sample['Lưu ý']
            sdt = str(sample['SĐT']).strip()
            if sdt.endswith('.0'): sdt = sdt[:-2]
            if sdt and not sdt.startswith('0') and sdt.isdigit(): sdt = '0' + sdt
            
        new_id = f"Manual_{belong_to}_{(datetime.utcnow() + timedelta(hours=7)).strftime('%Y%m%d%H%M%S')}"
        ws_tasks.append_row([new_id, task_date.strftime("%d/%m/%Y"), belong_to, tp, loai, task_name, thiep, sdt, diachi, luuy, "Chưa hoàn thành"])
        st.session_state.tasks_data.append({
            "Task_ID": new_id, "Ngày thực hiện": task_date.strftime("%d/%m/%Y"), "Tên người nhận": belong_to, "TP": tp, "Loại bánh": loai, 
            "Tên Task": task_name, "Tên trên thiệp": thiep, "SĐT": sdt, "Địa chỉ": diachi, "Lưu ý": luuy, "Trạng thái": "Chưa hoàn thành"
        })
        msg_placeholder.success("Đã thêm task thành công!")
        time.sleep(1.2)
        st.rerun()

st.write("---")

# ==========================================
# 3. OVERALL PROCESS
# ==========================================
st.markdown("<h2 id='overall-process'>OVERALL PROCESS</h2>", unsafe_allow_html=True)

# TÍNH TOÁN DATA TỔNG QUAN (CHỊU ẢNH HƯỞNG BỞI FILTER)
person_summary = []
orig_df = pd.DataFrame(st.session_state.source_data) if 'source_data' in st.session_state else pd.DataFrame()

for name, group in df_filtered.groupby('Tên người nhận'):
    if name == "Khác": continue
    total = len(group)
    done = len(group[group['Trạng thái'] == "Hoàn thành"])
    status = "Completed" if done == total else ("Not Yet" if done == 0 else "In Progress")
    tp_val = group['TP'].iloc[0] if 'TP' in group.columns else ""
    loc = "TP.HCM" if tp_val == "TPHCM" else "KHÁC"
    loai_banh = str(group['Loại bánh'].iloc[0]).strip() if 'Loại bánh' in group.columns else ""
    
    month_dt = None
    if not orig_df.empty:
        p_orig = orig_df[orig_df['Tên'] == name]
        if not p_orig.empty:
            try: month_dt = datetime.strptime(str(p_orig.iloc[0].get('Ngày giao bánh', '')).strip(), "%d/%m/%Y")
            except: pass
                
    person_summary.append({"Name": name, "Status": status, "Loc": loc, "Loại bánh": loai_banh, "Month_DT": month_dt})

df_sum = pd.DataFrame(person_summary)

if not df_sum.empty:
    df_valid = df_sum[df_sum['Month_DT'].notnull()].copy()
    df_invalid = df_sum[df_sum['Month_DT'].isnull()].copy()
    
    sorted_months = []
    if not df_valid.empty:
        df_valid['Month_Str'] = df_valid['Month_DT'].dt.strftime("%m/%Y")
        df_valid = df_valid.sort_values('Month_DT')
        sorted_months = df_valid['Month_Str'].unique().tolist()
    if not df_invalid.empty:
        df_invalid['Month_Str'] = "Không rõ"
        sorted_months.append("Không rõ")
        
    df_final = pd.concat([df_valid, df_invalid])
    
    # --- VẼ 2 BIỂU ĐỒ (DASHBOARD) ---
    chart_col1, chart_col2 = st.columns(2)
    
    # Lọc bỏ tháng "Không rõ" để vẽ biểu đồ
    df_chart = df_final[df_final['Month_Str'] != "Không rõ"]
    sorted_chart_months = [m for m in sorted_months if m != "Không rõ"]

    if not df_chart.empty:
        # BIỂU ĐỒ 1: Tình trạng & Tổng Đơn
        ny_counts = [len(df_chart[(df_chart['Month_Str'] == m) & (df_chart['Status'] == 'Not Yet')]) for m in sorted_chart_months]
        ip_counts = [len(df_chart[(df_chart['Month_Str'] == m) & (df_chart['Status'] == 'In Progress')]) for m in sorted_chart_months]
        cp_counts = [len(df_chart[(df_chart['Month_Str'] == m) & (df_chart['Status'] == 'Completed')]) for m in sorted_chart_months]
        total_counts = [ny + ip + cp for ny, ip, cp in zip(ny_counts, ip_counts, cp_counts)]

        fig1 = go.Figure()
        fig1.add_trace(go.Bar(name='Not Yet', x=sorted_chart_months, y=ny_counts, marker_color='#E0E0E0', text=[v if v>0 else "" for v in ny_counts], textposition='auto'))
        fig1.add_trace(go.Bar(name='In Progress', x=sorted_chart_months, y=ip_counts, marker_color='#CE93D8', text=[v if v>0 else "" for v in ip_counts], textposition='auto'))
        fig1.add_trace(go.Bar(name='Completed', x=sorted_chart_months, y=cp_counts, marker_color='#8E24AA', text=[v if v>0 else "" for v in cp_counts], textposition='auto'))
        fig1.add_trace(go.Scatter(name='Total', x=sorted_chart_months, y=total_counts, mode='lines+markers+text', marker=dict(color='#D81B60', size=8), line=dict(color='#D81B60', width=2, dash='dot'), text=[v if v>0 else "" for v in total_counts], textposition='top center'))
        fig1.update_layout(barmode='stack', title="Tiến độ & Tổng đơn / Tháng", plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", ybottom=-0.2), margin=dict(t=40, l=10, r=10, b=10))
        
        with chart_col1: st.plotly_chart(fig1, use_container_width=True)

        # BIỂU ĐỒ 2: Phân bổ Loại Bánh theo Khu vực (Grouped & Stacked)
        x_months = []
        x_locs = []
        y_gato = []
        y_cookie = []

        for m in sorted_chart_months:
            for loc in ["TP.HCM", "KHÁC"]:
                x_months.append(m)
                x_locs.append(loc)
                sub = df_chart[(df_chart['Month_Str'] == m) & (df_chart['Loc'] == loc)]
                y_gato.append(len(sub[sub['Loại bánh'].str.lower() == 'gato']))
                y_cookie.append(len(sub[sub['Loại bánh'].str.lower() == 'cookies']))

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name='Gato', x=[x_months, x_locs], y=y_gato, marker_color='#D81B60', text=[v if v>0 else "" for v in y_gato], textposition='auto'))
        fig2.add_trace(go.Bar(name='Cookies', x=[x_months, x_locs], y=y_cookie, marker_color='#8E24AA', text=[v if v>0 else "" for v in y_cookie], textposition='auto'))
        fig2.update_layout(barmode='stack', title="Phân bổ Loại Bánh & Khu vực", plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", ybottom=-0.2), margin=dict(t=40, l=10, r=10, b=10))
        
        with chart_col2: st.plotly_chart(fig2, use_container_width=True)

    # --- CHẾ ĐỘ VIEW (CŨ) ---
    view_mode = st.selectbox("👁️ CHỌN GÓC NHÌN CHI TIẾT:", ["💻 Laptop mode", "📱 Mobile mode - Status Focused", "📱 Mobile mode - Time Focused"])
    st.write("")

    if "Laptop mode" in view_mode:
        status_cols = st.columns(3)
        with status_cols[0]: st.markdown("<div class='process-box'>⏳ NOT YET</div>", unsafe_allow_html=True)
        with status_cols[1]: st.markdown("<div class='process-box'>🚀 IN PROGRESS</div>", unsafe_allow_html=True)
        with status_cols[2]: st.markdown("<div class='process-box'>✅ COMPLETED</div>", unsafe_allow_html=True)
            
        sub_cols = st.columns(6)
        for st_idx, st_name in enumerate(["Not Yet", "In Progress", "Completed"]):
            for lc_idx, lc_name in enumerate(["TP.HCM", "KHÁC"]):
                cnt = len(df_final[(df_final['Status'] == st_name) & (df_final['Loc'] == lc_name)])
                cls_name = "loc-header-tphcm" if lc_name == "TP.HCM" else "loc-header-khac"
                with sub_cols[st_idx*2 + lc_idx]: st.markdown(f"<div class='{cls_name}'>{lc_name} ({cnt})</div>", unsafe_allow_html=True)

        for month in sorted_months:
            with st.expander(f"Tháng {month}", expanded=False):
                m_cols = st.columns(6)
                col_mapping = {("Not Yet", "TP.HCM"): 0, ("Not Yet", "KHÁC"): 1, ("In Progress", "TP.HCM"): 2, ("In Progress", "KHÁC"): 3, ("Completed", "TP.HCM"): 4, ("Completed", "KHÁC"): 5}
                for stt in ["Not Yet", "In Progress", "Completed"]:
                    for loc in ["TP.HCM", "KHÁC"]:
                        subset = df_final[(df_final['Month_Str'] == month) & (df_final['Status'] == stt) & (df_final['Loc'] == loc)]
                        with m_cols[col_mapping[(stt, loc)]]:
                            for _, row in subset.iterrows():
                                icon = "🎂" if row['Loại bánh'].lower() == "gato" else ("🍪" if row['Loại bánh'].lower() == "cookies" else "🍰")
                                if st.button(f"{icon} {row['Name']}", key=f"btn_{row['Name']}_{month}_{stt}_{loc}_lap", type="secondary", use_container_width=True):
                                    show_detail_dialog(row['Name'])

    elif "Status Focused" in view_mode:
        t_ny, t_ip, t_cp = st.tabs(["⏳ NOT YET", "🚀 IN PROGRESS", "✅ COMPLETED"])
        def render_m1(s_name):
            for month in sorted_months:
                t_m = len(df_final[df_final['Month_Str'] == month])
                if t_m == 0: continue
                c_s = len(df_final[(df_final['Month_Str'] == month) & (df_final['Status'] == s_name)])
                with st.expander(f"Tháng {month} ({c_s}/{t_m})", expanded=False):
                    if c_s == 0: st.info(f"Không có đơn {s_name}.")
                    else:
                        sub = df_final[(df_final['Month_Str'] == month) & (df_final['Status'] == s_name)]
                        for l in ["TP.HCM", "KHÁC"]:
                            sl = sub[sub['Loc'] == l]
                            if not sl.empty:
                                st.markdown(f"**📍 {l}**")
                                for _, r in sl.iterrows():
                                    i = "🎂" if r['Loại bánh'].lower() == "gato" else "🍪"
                                    if st.button(f"{i} {r['Name']}", key=f"btn_{r['Name']}_{month}_{s_name}_{l}_m1", type="secondary", use_container_width=True): show_detail_dialog(r['Name'])
        with t_ny: render_m1("Not Yet")
        with t_ip: render_m1("In Progress")
        with t_cp: render_m1("Completed")

    elif "Time Focused" in view_mode:
        for month in sorted_months:
            total_month = len(df_final[df_final['Month_Str'] == month])
            with st.expander(f"Tháng {month} ({total_month})", expanded=False):
                t_ny, t_ip, t_cp = st.tabs([
                    f"⏳ NOT YET ({len(df_final[(df_final['Month_Str'] == month) & (df_final['Status'] == 'Not Yet')])})", 
                    f"🚀 IN PROGRESS ({len(df_final[(df_final['Month_Str'] == month) & (df_final['Status'] == 'In Progress')])})", 
                    f"✅ COMPLETED ({len(df_final[(df_final['Month_Str'] == month) & (df_final['Status'] == 'Completed')])})"
                ])
                def render_m2(s_name):
                    sub = df_final[(df_final['Month_Str'] == month) & (df_final['Status'] == s_name)]
                    if sub.empty: st.info("Không có dữ liệu."); return
                    for l in ["TP.HCM", "KHÁC"]:
                        sl = sub[sub['Loc'] == l]
                        if not sl.empty:
                            st.markdown(f"**📍 {l}**")
                            for _, r in sl.iterrows():
                                i = "🎂" if r['Loại bánh'].lower() == "gato" else "🍪"
                                if st.button(f"{i} {r['Name']}", key=f"btn_{r['Name']}_{month}_{s_name}_{l}_m2", type="secondary", use_container_width=True): show_detail_dialog(r['Name'])
                with t_ny: render_m2("Not Yet")
                with t_ip: render_m2("In Progress")
                with t_cp: render_m2("Completed")

# ==========================================
# 4. CREATE NOTE
# ==========================================
st.write("---")
st.markdown("<h2 id='create-note'>CREATE NOTE</h2>", unsafe_allow_html=True)
if "notes_data" not in st.session_state: st.session_state.notes_data = ws_notes.get_all_records()

note_col1, note_col2 = st.columns([1, 2])
with note_col1:
    with st.form("add_note_form", clear_on_submit=True):
        note_text = st.text_area("Nhập nội dung Note:", height=150)
        if st.form_submit_button("CREATE NOTE", type="primary") and note_text:
            time_str = (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y %H:%M")
            ws_notes.append_row([time_str, note_text])
            st.session_state.notes_data.append({"Thời gian": time_str, "Nội dung Note": note_text})
            st.rerun()

with note_col2:
    if not st.session_state.notes_data: st.info("Chưa có note nào.")
    else:
        for idx, n in reversed(list(enumerate(st.session_state.notes_data))):
            st.markdown(f"<div class='note-box'><small style='color: #6a1b9a; font-weight: bold;'>🕒 {n.get('Thời gian', '')}</small><br><div style='margin-top: 5px; font-size: 1.1em; white-space: pre-wrap;'>{n.get('Nội dung Note', '')}</div></div>", unsafe_allow_html=True)
            if f"edit_mode_{idx}" not in st.session_state: st.session_state[f"edit_mode_{idx}"] = False
            if st.button("✏️ Edit Note", key=f"btn_edit_{idx}", type="secondary"):
                st.session_state[f"edit_mode_{idx}"] = not st.session_state[f"edit_mode_{idx}"]
                st.rerun()
            if st.session_state[f"edit_mode_{idx}"]:
                new_note_content = st.text_area("Sửa nội dung:", value=n.get('Nội dung Note', ''), key=f"text_edit_{idx}")
                if st.button("Lưu thay đổi", key=f"save_note_{idx}", type="primary"):
                    ws_notes.update_cell(idx + 2, 2, new_note_content)
                    st.session_state.notes_data[idx]['Nội dung Note'] = new_note_content
                    st.session_state[f"edit_mode_{idx}"] = False 
                    st.rerun()
