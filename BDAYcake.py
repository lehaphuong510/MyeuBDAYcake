import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- CẤU HÌNH GIAO DIỆN & UX/UI ---
st.set_page_config(page_title="Timeline Management", layout="wide")

st.markdown("""
<style>
    /* Tone màu hồng đậm sang tím, font in hoa, không rớt chữ */
    h1, h2, h3, h4, .theme-text {
        background: linear-gradient(to right, #D81B60, #8E24AA);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-transform: uppercase;
        white-space: nowrap;
        text-align: left;
        font-weight: bold;
    }
    .stButton>button {
        background: linear-gradient(to right, #D81B60, #8E24AA);
        color: white;
        text-transform: uppercase;
        font-weight: bold;
        border: none;
    }
    .task-box {
        border-left: 5px solid #D81B60;
        background-color: #fcfcfc;
        padding: 15px;
        margin-bottom: 15px;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
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

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1SQrD2ps8L9mEXM8UTsqMalI090_mMT3WTLHY9lAhtBI/edit"
client = get_gspread_client()
sheet = client.open_by_url(SPREADSHEET_URL)
ws_data = sheet.worksheet("Data")
ws_tasks = sheet.worksheet("Tasks")

# --- HÀM XỬ LÝ DỮ LIỆU LOGIC ---
def load_and_sync_tasks():
    # 1. Đọc data gốc
    df_data = pd.DataFrame(ws_data.get_all_records())
    
    # Xử lý rule: Nếu Ngày sinh nhật trống thì lấy Ngày giao bánh
    if 'Ngày sinh nhật' in df_data.columns and 'Ngày giao bánh' in df_data.columns:
        df_data['Ngày sinh nhật'] = df_data.apply(
            lambda row: row['Ngày giao bánh'] if pd.isna(row['Ngày sinh nhật']) or str(row['Ngày sinh nhật']).strip() == '' else row['Ngày sinh nhật'], 
            axis=1
        )
    
    # 2. Đọc tasks hiện tại (để không tạo trùng)
    tasks_records = ws_tasks.get_all_records()
    df_tasks = pd.DataFrame(tasks_records)
    existing_task_ids = df_tasks['Task_ID'].astype(str).tolist() if not df_tasks.empty else []
    
    new_tasks_to_add = []
    
    # 3. Generate task theo rule
    for idx, row in df_data.iterrows():
        ten = str(row.get('Tên', '')).strip()
        if not ten: continue
        
        ngay_giao_str = str(row.get('Ngày giao bánh', ''))
        try:
            ngay_giao = datetime.strptime(ngay_giao_str, "%d/%m/%Y").date()
        except:
            continue # Bỏ qua nếu sai format ngày
            
        tp = str(row.get('TP', '')).strip()
        loai_banh = str(row.get('Loại bánh', '')).strip()
        
        tasks_to_create = []
        # Rule A1 & A2
        if tp == 'TPHCM' or (tp != 'TPHCM' and loai_banh == 'Gato'):
            tasks_to_create = [
                (ngay_giao - timedelta(days=4), "Remind tiệm bánh"),
                (ngay_giao - timedelta(days=1), "Follow up"),
                (ngay_giao, "Giao bánh")
            ]
        # Rule A3
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
                new_tasks_to_add.append([
                    task_id, t_date.strftime("%d/%m/%Y"), ten, tp, loai_banh, t_name,
                    str(row.get('Tên trên thiệp/ bánh', '')), str(row.get('DT', '')), 
                    str(row.get('Địa chỉ', '')), str(row.get('Lưu ý', '')), "Chưa hoàn thành"
                ])
                existing_task_ids.append(task_id) # Tránh duplicate cục bộ
                
    # 4. Đẩy new tasks lên Google Sheets
    if new_tasks_to_add:
        ws_tasks.append_rows(new_tasks_to_add)
        df_tasks = pd.DataFrame(ws_tasks.get_all_records()) # Load lại sau khi thêm
        
    return df_tasks

# --- UI RENDERING ---
st.markdown("<h1>BDAY CAKE 19/07<br>TIMELINE MANAGEMENT</h1>", unsafe_allow_html=True)
st.write("---")

# Load Data
df_tasks = load_and_sync_tasks()
df_tasks['Ngày thực hiện'] = pd.to_datetime(df_tasks['Ngày thực hiện'], format="%d/%m/%Y", errors='coerce')
today = datetime.today().date()

# 1. OVERALL PROCESS & OVERDUE WARNING
st.markdown("<h2>OVERALL PROCESS</h2>", unsafe_allow_html=True)

# Overdue logic
overdue_tasks = df_tasks[(df_tasks['Ngày thực hiện'].dt.date < today) & (df_tasks['Trạng thái'] != "Hoàn thành")]
if not overdue_tasks.empty:
    for _, r in overdue_tasks.iterrows():
        st.markdown(f"<div class='overdue-alert'>⚠️ {r['Tên người nhận']} - {r['Tên Task']} đã quá deadline</div>", unsafe_allow_html=True)

# Group Process logic
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
    st.markdown("<h4 class='theme-text'>NOT YET</h4>", unsafe_allow_html=True)
    for n in not_yet: st.write(f"- {n}")
with process_cols[1]:
    st.markdown("<h4 class='theme-text'>IN PROGRESS</h4>", unsafe_allow_html=True)
    for n in in_progress: st.write(f"- {n}")
with process_cols[2]:
    st.markdown("<h4 class='theme-text'>COMPLETED</h4>", unsafe_allow_html=True)
    for n in completed: st.write(f"- {n}")

st.write("---")

# 2. CALENDAR & TO-DO LIST (TABS)
tab_cal, tab_todo = st.tabs(["LỊCH (CALENDAR TÓM TẮT)", "TO-DO LIST (CHI TIẾT)"])

with tab_cal:
    st.markdown("<h2>CALENDAR THEO THÁNG</h2>", unsafe_allow_html=True)
    # Hiển thị theo dạng list gom nhóm theo ngày (vì st chưa support grid calendar native tốt)
    cal_df = df_tasks.sort_values(by='Ngày thực hiện')
    for d, group in cal_df.groupby(cal_df['Ngày thực hiện'].dt.date):
        st.markdown(f"**🗓️ {d.strftime('%d/%m/%Y')}**")
        for _, r in group.iterrows():
            prefix = r['Tên người nhận'] if r['Tên người nhận'] != "Khác" else "Khác"
            tp_loai = f"{r['TP']} - {r['Loại bánh']}" if r['TP'] else ""
            display_str = f"👉 {prefix} | {tp_loai} - {r['Tên Task']}"
            st.write(display_str)
        st.write("")

with tab_todo:
    sub_tab_1, sub_tab_2, sub_tab_3 = st.tabs(["HÔM NAY", "TRONG VÒNG 8 NGÀY TỚI", "TRONG VÒNG 1 THÁNG TỚI"])
    
    def render_task_list(df_filter):
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
            
            # Logic Checkbox update thẳng lên Gsheet
            is_done = r['Trạng thái'] == "Hoàn thành"
            checked = st.checkbox(f"Hoàn thành task: {r['Tên Task']} ({prefix})", value=is_done, key=r['Task_ID'])
            
            if checked != is_done:
                new_val = "Hoàn thành" if checked else "Chưa hoàn thành"
                # Tìm dòng trong Gsheet (Row tính từ 1, bỏ header là 2)
                cell = ws_tasks.find(r['Task_ID'])
                if cell:
                    ws_tasks.update_cell(cell.row, 11, new_val) # Cột 11 là Trạng thái
                st.rerun() # Refresh app để update list

    with sub_tab_1:
        render_task_list(df_tasks[df_tasks['Ngày thực hiện'].dt.date == today])
    with sub_tab_2:
        render_task_list(df_tasks[(df_tasks['Ngày thực hiện'].dt.date >= today) & (df_tasks['Ngày thực hiện'].dt.date <= today + timedelta(days=8))])
    with sub_tab_3:
        render_task_list(df_tasks[(df_tasks['Ngày thực hiện'].dt.date >= today) & (df_tasks['Ngày thực hiện'].dt.date <= today + timedelta(days=30))])

st.write("---")

# 3. ADD TASK
st.markdown("<h2>ADD THÊM TASK MỚI</h2>", unsafe_allow_html=True)
list_names = [n for n in df_tasks['Tên người nhận'].unique() if n and n != "Khác"]

with st.form("add_task_form"):
    belong_to = st.selectbox("Task này thuộc:", list_names + ["Khác"])
    task_date = st.date_input("Ngày thực hiện")
    task_name = st.text_input("Task (Fill vào)")
    
    submitted = st.form_submit_button("CREATE TASK")
    if submitted and task_name:
        # Nếu thuộc về "Khác", lấy thông tin trống. Nếu thuộc 1 người có sẵn, lấy data của người đó để map xuống
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
        st.success("Tạo task thành công!")
        st.rerun()
