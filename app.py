import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime
import streamlit.components.v1 as components
import time
import gspread

st.set_page_config(page_title="工程進度管理系統", layout="wide")

# ====== 🌟 隱藏列印時的側邊欄 ======
print_css = """
<style>
@media print {
    [data-testid="stSidebar"], header, button { display: none !important; }
    .block-container { max-width: 100% !important; padding: 0 !important; }
}
</style>
"""
st.markdown(print_css, unsafe_allow_html=True)

# ====== 🤖 狀態自動診斷模組 ======
def evaluate_status(row):
    plan_start = row['預定開始日']
    plan_end = row['預定完成日']
    act_start = row['實際開始日']
    act_end = row['實際完成日']
    today = pd.Timestamp(datetime.date.today())

    if pd.isna(plan_start) or pd.isna(plan_end):
        return ""

    if pd.notna(act_end):
        delay = (act_end - plan_end).days
        if delay > 0:
            return f"🔴 延遲完工 {delay} 天"
        elif delay < 0:
            return f"🟢 提前完工 {abs(delay)} 天"
        else:
            return "✅ 如期完工"
    else:
        if pd.isna(act_start):
            if today < plan_start:
                return "⚪ 未開工"
            else:
                delay = (today - plan_start).days
                return f"🟡 延遲開工 {delay} 天"
        else:
            if today > plan_end:
                delay = (today - plan_end).days
                return f"🔴 進度落後 {delay} 天"
            else:
                return "🔵 施工中"

# ====== 🎨 將甘特圖打包成專屬繪圖功能 ======
def draw_gantt_chart(df):
    plot_list = []
    today = pd.Timestamp(datetime.date.today())
    lbl_plan = "<span style='font-size: 13px; color: #555555;'>預定</span>"
    lbl_act = "<span style='font-size: 13px; color: #555555;'>實際</span>"

    for index, row in df.iterrows():
        task_name = row['工程項目']
        
        if pd.notna(row['預定開始日']) and pd.notna(row['預定完成日']):
            plot_list.append({"工程項目": task_name, "排程類別": lbl_plan, "開始日": row['預定開始日'], "完成日": row['預定完成日'] + pd.Timedelta(days=1), "進度狀態": "預定計畫"})
            
        if pd.notna(row['實際開始日']):
            is_finished = pd.notna(row['實際工期(天)'])
            actual_start = row['實際開始日']
            planned_end = row['預定完成日']
            
            if is_finished and pd.notna(row['實際完成日']):
                actual_end = row['實際完成日']
                if actual_end > planned_end:
                    green_end = min(actual_end, planned_end)
                    if green_end >= actual_start:
                        plot_list.append({"工程項目": task_name, "排程類別": lbl_act, "開始日": actual_start, "完成日": green_end + pd.Timedelta(days=1), "進度狀態": "實際進度"})
                    orange_start = max(actual_start, planned_end + pd.Timedelta(days=1))
                    if actual_end >= orange_start:
                        plot_list.append({"工程項目": task_name, "排程類別": lbl_act, "開始日": orange_start, "完成日": actual_end + pd.Timedelta(days=1), "進度狀態": "延遲完工"})
                else:
                    plot_list.append({"工程項目": task_name, "排程類別": lbl_act, "開始日": actual_start, "完成日": actual_end + pd.Timedelta(days=1), "進度狀態": "實際進度"})
            else:
                if today > planned_end:
                    green_end = planned_end
                    if green_end >= actual_start:
                        plot_list.append({"工程項目": task_name, "排程類別": lbl_act, "開始日": actual_start, "完成日": green_end + pd.Timedelta(days=1), "進度狀態": "實際進度"})
                    red_start = max(actual_start, planned_end + pd.Timedelta(days=1))
                    if today >= red_start:
                        plot_list.append({"工程項目": task_name, "排程類別": lbl_act, "開始日": red_start, "完成日": today + pd.Timedelta(days=1), "進度狀態": "進度落後"})
                else:
                    plot_list.append({"工程項目": task_name, "排程類別": lbl_act, "開始日": actual_start, "完成日": today + pd.Timedelta(days=1), "進度狀態": "實際進度"})
        else:
            planned_start = row['預定開始日']
            if pd.notna(planned_start) and today > planned_start:
                plot_list.append({"工程項目": task_name, "排程類別": lbl_act, "開始日": planned_start, "完成日": today + pd.Timedelta(days=1), "進度狀態": "進度落後"})

    plot_df = pd.DataFrame(plot_list)
    if not plot_df.empty:
        min_date = plot_df['開始日'].min() - pd.Timedelta(days=2)
        max_date = plot_df['完成日'].max() + pd.Timedelta(days=3)
        min_date = min(min_date, today - pd.Timedelta(days=2))
        max_date = max(max_date, today + pd.Timedelta(days=3))
    else:
        min_date = today - pd.Timedelta(days=3)
        max_date = today + pd.Timedelta(days=7)

    x_range = [min_date.strftime('%Y-%m-%d'), max_date.strftime('%Y-%m-%d')]
    fig = go.Figure()

    y_axis_tasks = []
    y_axis_types = []
    for task in df['工程項目']:
        y_axis_tasks.extend([task, task])
        y_axis_types.extend([lbl_plan, lbl_act]) 

    fig.add_trace(go.Bar(
        y=[y_axis_tasks, y_axis_types], x=[86400000.0] * len(y_axis_tasks), base=[min_date.strftime('%Y-%m-%d')] * len(y_axis_tasks),
        marker_color='rgba(0,0,0,0)', showlegend=False, hoverinfo='skip'
    ))

    color_map = {"預定計畫": "#00B0F0", "實際進度": "#00B050", "進度落後": "#FF0000", "延遲完工": "#FFC000"}

    if not plot_df.empty:
        plot_df['持續時間'] = (plot_df['完成日'] - plot_df['開始日']).dt.total_seconds() * 1000
        added_legends = set()
        for state, color in color_map.items():
            df_sub = plot_df[plot_df['進度狀態'] == state]
            if not df_sub.empty:
                show_lg = state not in added_legends
                added_legends.add(state)
                fig.add_trace(go.Bar(
                    base=df_sub['開始日'].dt.strftime('%Y-%m-%d'), x=df_sub['持續時間'], y=[df_sub['工程項目'], df_sub['排程類別']], 
                    orientation='h', name=state, marker_color=color, showlegend=show_lg, width=0.3 
                ))

    date_range = pd.date_range(start=min_date, end=max_date)
    tickvals = date_range.strftime('%Y-%m-%d').tolist()
    ticktext = [f"{d.month}<br>月<br>{d.day}<br>日" for d in date_range]

    total_days = len(date_range)
    fixed_chart_width = 200 + (total_days * 40)

    fig.update_layout(
        barmode='overlay', font=dict(family="Microsoft JhengHei"), xaxis_title="", yaxis_title="", 
        height=180 + len(df)*60, width=fixed_chart_width, margin=dict(l=10, r=10, t=80, b=10), uirevision='constant' 
    )
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=18, color="black"), showgrid=True, gridcolor='#E0E0E0')
    fig.update_xaxes(type='date', range=x_range, tickmode='array', tickvals=tickvals, ticktext=ticktext, showgrid=True, gridcolor='#E0E0E0', gridwidth=1, tickangle=0, side="top")
    fig.add_vline(x=today.strftime('%Y-%m-%d'), line_width=2, line_dash="dash", line_color="red")

    st.plotly_chart(fig, use_container_width=False)


# ====== ☁️ 雲端資料庫連線設定 ======
SHEET_NAME = "工程專案進度資料庫" 

@st.cache_resource
def get_google_sheet_connection():
    try:
        if "gcp_service_account" in st.secrets:
            credentials_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(credentials_dict)
            return gc.open(SHEET_NAME)
        else:
            gc = gspread.service_account(filename="secrets.json")
            return gc.open(SHEET_NAME)
    except Exception as e:
        st.error(f"連線失敗：{e} (請確認金鑰設定是否正確)")
        st.stop()

sh = get_google_sheet_connection()

# ====== 🧠 系統資料庫讀取 ======
if 'projects' not in st.session_state:
    st.session_state.projects = {}
    st.session_state.saved_projects = {}
    st.session_state.editor_versions = {}

    worksheets = sh.worksheets()
    
    if len(worksheets) == 1 and worksheets[0].title == "工作表1" and not worksheets[0].get_all_values():
        default_df = pd.DataFrame({
            "工程項目": ["構造物開挖", "墊底混凝土", "基礎鋼筋綁紮", "基礎模板組立"],
            "預定開始日": [datetime.date(2026, 3, 1), datetime.date(2026, 3, 3), datetime.date(2026, 3, 9), datetime.date(2026, 3, 12)],
            "預定工期(天)": [2, 6, 3, 1],
            "實際開始日": [datetime.date(2026, 3, 1), datetime.date(2026, 3, 4), None, None],
            "實際工期(天)": [2, 3, None, None] 
        })
        default_name = "3K+689.8~751.25 右側擋土牆工程"
        
        ws = worksheets[0]
        ws.update_title(default_name)
        save_df = default_df.copy()
        for col in save_df.columns:
            save_df[col] = save_df[col].astype(str).replace(['None', 'nan', 'NaT', '<NA>'], '')
        ws.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        
        st.session_state.projects[default_name] = default_df
        st.session_state.saved_projects[default_name] = default_df.copy()
    else:
        for ws in worksheets:
            proj_name = ws.title
            if proj_name == "工作表1" and not ws.get_all_values():
                continue 
                
            records = ws.get_all_records()
            if records:
                df_loaded = pd.DataFrame(records)
                for col in ['預定開始日', '實際開始日']:
                    if col in df_loaded.columns:
                        df_loaded[col] = pd.to_datetime(df_loaded[col], errors='coerce').apply(lambda x: x.date() if pd.notnull(x) else None)
                for col in ['預定工期(天)', '實際工期(天)']:
                    if col in df_loaded.columns:
                        df_loaded[col] = pd.to_numeric(df_loaded[col], errors='coerce').astype('Int64')

                st.session_state.projects[proj_name] = df_loaded
                st.session_state.saved_projects[proj_name] = df_loaded.copy()

# ====== 📂 左側邊欄：選單 ======
with st.sidebar:
    st.title("☁️ 雲端工項庫")
    project_list = list(st.session_state.projects.keys())
    
    if not project_list:
        st.warning("雲端資料庫目前無工項。")
        current_project = None
    else:
        options = ["🌐 總覽所有工項"] + project_list
        current_project = st.selectbox("👇 請選擇要查看的工項：", options)
    st.divider()

# ====== 💻 主畫面分支判斷 ======

if current_project == "🌐 總覽所有工項":
    st.title("🌐 台1替 所有工項進度總覽")
    st.caption("系統已自動抓取各工項的最早開工日與最晚完工日")
    
    overview_records = []
    for p_name, p_df in st.session_state.projects.items():
        temp_df = p_df.copy()
        temp_df['預定開始日'] = pd.to_datetime(temp_df['預定開始日'])
        temp_df['實際開始日'] = pd.to_datetime(temp_df['實際開始日'])
        temp_df['預定完成日'] = temp_df['預定開始日'] + pd.to_timedelta(pd.to_numeric(temp_df['預定工期(天)'], errors='coerce') - 1, unit='D')
        temp_df['實際完成日'] = temp_df['實際開始日'] + pd.to_timedelta(pd.to_numeric(temp_df['實際工期(天)'], errors='coerce') - 1, unit='D')
        
        # 🌟 邏輯升級：過濾掉沒有預定日期的空白列
        valid_tasks = temp_df.dropna(subset=['預定開始日'])
        
        if valid_tasks.empty:
            continue
            
        plan_start = valid_tasks['預定開始日'].min()
        plan_end = valid_tasks['預定完成日'].max()
        act_start = valid_tasks['實際開始日'].min()
        
        # 🌟 邏輯升級：必須「所有細項」都有實際完成日，這個大工項才算真正完工！
        is_project_finished = not valid_tasks['實際完成日'].isna().any()
        act_end = valid_tasks['實際完成日'].max() if is_project_finished else pd.NaT
        
        plan_dur = (plan_end - plan_start).days + 1 if pd.notna(plan_start) and pd.notna(plan_end) else None
        act_dur = (act_end - act_start).days + 1 if pd.notna(act_start) and pd.notna(act_end) else None
        
        overview_records.append({
            "工程項目": p_name, 
            "預定開始日": plan_start,
            "預定工期(天)": plan_dur,
            "預定完成日": plan_end,
            "實際開始日": act_start,
            "實際工期(天)": act_dur,
            "實際完成日": act_end
        })
        
    df_overview = pd.DataFrame(overview_records)
    
    if not df_overview.empty:
        df_overview['狀態評估'] = df_overview.apply(evaluate_status, axis=1)
        
        st.subheader("📊 1. 總覽時間表")
        display_df = df_overview[['工程項目', '預定開始日', '預定完成日', '實際開始日', '實際完成日', '狀態評估']].copy()
        display_df['預定開始日'] = display_df['預定開始日'].dt.strftime('%Y-%m-%d').fillna('')
        display_df['預定完成日'] = display_df['預定完成日'].dt.strftime('%Y-%m-%d').fillna('')
        display_df['實際開始日'] = display_df['實際開始日'].dt.strftime('%Y-%m-%d').fillna('')
        display_df['實際完成日'] = display_df['實際完成日'].dt.strftime('%Y-%m-%d').fillna('')
        display_df.rename(columns={'工程項目': '工項名稱'}, inplace=True)
        st.dataframe(display_df, use_container_width=True)

        st.subheader("📈 2. 跨工項總覽甘特圖")
        draw_gantt_chart(df_overview)
    else:
        st.info("目前尚無有效資料可供總覽。")

elif current_project:
    st.title(f"🚧 {current_project} - 進度管理儀表板")
    st.subheader("📝 1. 填寫現場進度")

    if current_project not in st.session_state.editor_versions:
        st.session_state.editor_versions[current_project] = 0
    editor_key = f"editor_{current_project}_{st.session_state.editor_versions[current_project]}"

    edited_df = st.data_editor(
        st.session_state.projects[current_project], 
        num_rows="dynamic", 
        use_container_width=True, 
        key=editor_key,
        column_config={
            "預定開始日": st.column_config.DateColumn("預定開始日", format="YYYY-MM-DD"),
            "實際開始日": st.column_config.DateColumn("實際開始日", format="YYYY-MM-DD"),
            "預定工期(天)": st.column_config.NumberColumn("預定工期(天)", min_value=1, step=1),
            "實際工期(天)": st.column_config.NumberColumn("實際工期(天)", min_value=1, step=1)
        }
    )

    df = edited_df.copy()
    df['預定開始日'] = pd.to_datetime(df['預定開始日'])
    df['實際開始日'] = pd.to_datetime(df['實際開始日'])
    df['預定完成日'] = df['預定開始日'] + pd.to_timedelta(df['預定工期(天)'] - 1, unit='D')
    df['實際完成日'] = df['實際開始日'] + pd.to_timedelta(df['實際工期(天)'] - 1, unit='D')

    df['狀態評估'] = df.apply(evaluate_status, axis=1)

    st.subheader("📊 2. 系統自動計算結果")
    display_df = df[['工程項目', '預定開始日', '預定工期(天)', '預定完成日', '實際開始日', '實際完成日', '狀態評估']].copy()
    display_df['預定開始日'] = display_df['預定開始日'].dt.strftime('%Y-%m-%d').fillna('')
    display_df['預定完成日'] = display_df['預定完成日'].dt.strftime('%Y-%m-%d').fillna('')
    display_df['實際開始日'] = display_df['實際開始日'].dt.strftime('%Y-%m-%d').fillna('')
    display_df['實際完成日'] = display_df['實際完成日'].dt.strftime('%Y-%m-%d').fillna('')
    st.dataframe(display_df, use_container_width=True)

    st.subheader("📈 3. 工項甘特圖 (預定 vs 實際)")
    draw_gantt_chart(df)

# ====== 📂 左側邊欄：操作區 ======
with st.sidebar:
    if current_project and current_project != "🌐 總覽所有工項": 
        st.write("🛠️ **工項操作**")
        col1, col2 = st.columns(2)
        col3, col4 = st.columns(2)
        
        if col1.button("☁️ 雲端存檔", use_container_width=True):
            with st.spinner('🚀 正在同步至 Google 試算表...'):
                st.session_state.projects[current_project] = edited_df.copy() 
                st.session_state.saved_projects[current_project] = edited_df.copy() 
                st.session_state.editor_versions[current_project] += 1 
                
                try:
                    ws = sh.worksheet(current_project)
                except gspread.exceptions.WorksheetNotFound:
                    ws = sh.add_worksheet(title=current_project, rows="100", cols="20")
                
                save_df = edited_df.copy()
                for col in save_df.columns:
                    save_df[col] = save_df[col].astype(str).replace(['None', 'nan', 'NaT', '<NA>'], '')
                
                ws.clear() 
                ws.update([save_df.columns.values.tolist()] + save_df.values.tolist()) 
                
                st.toast("✅ 雲端存檔成功！全辦公室已同步。", icon="✅")
                time.sleep(1.5)
                st.rerun()

        csv_data = display_df.to_csv(index=False, encoding='utf-8-sig')
        col2.download_button(
            label="📥 下載完整備份", 
            data=csv_data, 
            file_name=f"{current_project}_完整進度表.csv", 
            mime="text/csv", 
            use_container_width=True
        )

        if col3.button("↩️ 復原", use_container_width=True):
            st.session_state.projects[current_project] = st.session_state.saved_projects[current_project].copy()
            st.session_state.editor_versions[current_project] += 1
            st.rerun()

        if col4.button("🖨️ 列印", use_container_width=True):
            unique_key = str(time.time())
            print_script = f"<script>window.parent.print();</script><span style='display:none;'>{unique_key}</span>"
            components.html(print_script, height=0)
            
        st.divider()
    
    elif current_project == "🌐 總覽所有工項":
        st.write("🛠️ **總覽操作**")
        col_a, col_b = st.columns(2)
        
        if 'df_overview' in locals() and not df_overview.empty:
            csv_overview = display_df.to_csv(index=False, encoding='utf-8-sig')
            col_a.download_button(
                label="📥 下載總覽報表", 
                data=csv_overview, 
                file_name="台1替_全工項總覽進度表.csv", 
                mime="text/csv", 
                use_container_width=True
            )
        
        if col_b.button("🖨️ 列印圖表", use_container_width=True):
            unique_key = str(time.time())
            components.html(f"<script>window.parent.print();</script><span style='display:none;'>{unique_key}</span>", height=0)
        st.divider()

    st.write("➕ **建立新工項**")
    new_project_name = st.text_input("輸入新工項名稱：", label_visibility="collapsed", placeholder="輸入名稱後按 Enter...")
    if st.button("新增工項", use_container_width=True):
        if new_project_name and new_project_name not in st.session_state.projects and new_project_name != "🌐 總覽所有工項":
            with st.spinner('🚀 正在雲端建立新工項...'):
                new_df = pd.DataFrame({
                    "工程項目": ["新增細項..."], "預定開始日": [datetime.date.today()], "預定工期(天)": [1], "實際開始日": [None], "實際工期(天)": [None]
                })
                st.session_state.projects[new_project_name] = new_df
                st.session_state.saved_projects[new_project_name] = new_df.copy() 
                st.session_state.editor_versions[new_project_name] = 0
                
                try:
                    ws = sh.add_worksheet(title=new_project_name, rows="100", cols="20")
                    save_df = new_df.copy()
                    for col in save_df.columns:
                        save_df[col] = save_df[col].astype(str).replace(['None', 'nan', 'NaT', '<NA>'], '')
                    ws.update([save_df.columns.values.tolist()] + save_df.values.tolist())
                except Exception as e:
                    st.error(f"建立失敗：{e}")
                
                st.rerun()