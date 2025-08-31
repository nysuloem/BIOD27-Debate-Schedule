import streamlit as st
import csv
from datetime import datetime
import os
import threading
import html
import pytz # New library for timezone handling

# --- CONFIGURATION ---
# IMPORTANT: Set the year for the debates to the current year.
DEBATE_YEAR = 2025 

# IMPORTANT: Set your secret password for the instructor panel.
INSTRUCTOR_PASSWORD = "changeme" 

# IMPORTANT: Set the timezone for your location. This ensures all date comparisons are accurate.
# For London, Ontario, "America/Toronto" is correct.
TIMEZONE = "America/Toronto"

# IMPORTANT: SET YOUR REVEAL SCHEDULE HERE
# These keys ("Sep 26", "Oct 3", etc.) MUST correspond to the dates in your CSV.
# The code will now automatically read the date from the CSV and match it to these keys.
tz = pytz.timezone(TIMEZONE)
REVEAL_SCHEDULE = {
    "Sep 26": tz.localize(datetime(DEBATE_YEAR, 9, 24, 0, 0)),
    "Oct 10":  tz.localize(datetime(DEBATE_YEAR, 10, 8, 0, 0)),
    "Oct 24": tz.localize(datetime(DEBATE_YEAR, 10, 22, 0, 0)),
    "Nov 07":  tz.localize(datetime(DEBATE_YEAR, 11, 5, 0, 0)),
    "Nov 21": tz.localize(datetime(DEBATE_YEAR, 11, 19, 0, 0))
}

SCHEDULE_FILE = 'schedule.csv'
SUBMISSIONS_FILE = 'submissions.csv'
SUBMISSION_HEADERS = ['Debate Number', 'Stakeholder', 'Team Name', 'Position', 'Submission Time']

# --- FILE LOCKING FOR SAFE SIMULTANEOUS WRITES ---
file_lock = threading.Lock()

# --- DATA HANDLING & HELPER FUNCTIONS ---

def get_reveal_date_for_debate(debate_row):
    """
    Smarter function that reads the date from the CSV (e.g., "2025-09-26 10:10"),
    converts it to a "Month Day" key (e.g., "Sep 26"), and finds the reveal date.
    """
    date_str = debate_row.get('Date and Time', '')
    if not date_str: return None
    
    try:
        # Try to parse the YYYY-MM-DD HH:MM format first
        dt_obj = datetime.strptime(date_str.split()[0], '%Y-%m-%d')
    except ValueError:
        try:
            # Fallback for "Month Day Time" format
            dt_obj = datetime.strptime(" ".join(date_str.split()[:2]), '%b %d')
        except ValueError:
            return None # Return None if format is unrecognized

    # Format the parsed date into the key we use in REVEAL_SCHEDULE
    key = dt_obj.strftime('%b %d')
    return REVEAL_SCHEDULE.get(key)


def load_data_from_csv(filepath, headers=None):
    try:
        with open(filepath, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            return list(reader)
    except FileNotFoundError:
        if headers:
            with open(filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
        return []

def find_debates_for_team(team_name, schedule):
    if not team_name: return []
    found_debates = []
    for debate_row in schedule:
        for i in range(1, 5):
            if debate_row.get(f'Team {i}', '').strip().lower() == team_name.strip().lower():
                stakeholder_role = debate_row.get(f'Stakeholder {i}')
                found_debates.append({'debate_details': debate_row, 'stakeholder_role': stakeholder_role})
    return found_debates

def load_schedule():
    schedule_data = load_data_from_csv(SCHEDULE_FILE)
    if not schedule_data:
        st.error(f"Error: The schedule file '{SCHEDULE_FILE}' was not found.")
        st.stop()
    return schedule_data

def load_submissions():
    with file_lock:
        return load_data_from_csv(SUBMISSIONS_FILE, headers=SUBMISSION_HEADERS)

def save_submission(debate_num, stakeholder, team_name, position):
    with file_lock:
        submissions = load_data_from_csv(SUBMISSIONS_FILE, headers=SUBMISSION_HEADERS)
        record_found = False
        for sub in submissions:
            if int(sub['Debate Number']) == int(debate_num) and sub['Stakeholder'] == stakeholder:
                sub['Team Name'] = team_name
                sub['Position'] = position
                sub['Submission Time'] = datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S %Z')
                record_found = True
                break
        if not record_found:
            submissions.append({
                'Debate Number': debate_num, 'Stakeholder': stakeholder, 'Team Name': team_name,
                'Position': position, 'Submission Time': datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S %Z')
            })
        with open(SUBMISSIONS_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=SUBMISSION_HEADERS)
            writer.writeheader()
            writer.writerows(submissions)
    return True

def generate_html_table(data, headers):
    html_string = "<style> table { width: 100%; border-collapse: collapse; } th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; } </style>"
    html_string += "<table><thead><tr>"
    for header in headers: html_string += f"<th>{html.escape(header)}</th>"
    html_string += "</tr></thead><tbody>"
    for row in data:
        html_string += "<tr>"
        for header in headers:
            html_string += f"<td>{html.escape(str(row.get(header, '')))}</td>"
        html_string += "</tr>"
    html_string += "</tbody></table>"
    return html_string

# --- APP LAYOUT ---
st.set_page_config(layout="wide")
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["View Full Schedule", "Sign Up / Change Position"])
st.sidebar.markdown("---")
st.sidebar.title("Instructor Access")
password = st.sidebar.text_input("Enter password for admin panel:", type="password")

schedule_data = load_schedule()
submissions_data = load_submissions()
now = datetime.now(pytz.timezone(TIMEZONE))

if page == "View Full Schedule":
    st.title("Full Debate Schedule")
    all_teams = sorted(list(set(team for row in schedule_data for i in range(1, 5) if (team := row.get(f'Team {i}')))))
    selected_team = st.selectbox("Filter schedule by team:", ["Show All Teams"] + all_teams)
    st.write("Positions are revealed automatically after the sign-up deadline for each debate day.")
    results_data = [dict(row) for row in schedule_data]
    if selected_team != "Show All Teams":
        results_data = [row for row in results_data if any(row.get(f'Team {i}', '') == selected_team for i in range(1, 5))]

    for debate in results_data:
        reveal_date = get_reveal_date_for_debate(debate)
        for i in range(1, 5):
            team_name, stakeholder_name = debate.get(f'Team {i}'), debate.get(f'Stakeholder {i}')
            position_col = f'Position {i}'
            debate[position_col] = "—"
            if team_name:
                if reveal_date is None:
                    debate[position_col] = "CONFIG ERROR" 
                elif now < reveal_date:
                    debate[position_col] = f"Reveals {reveal_date.strftime('%b %d')}"
                else:
                    submission = next((s for s in submissions_data if int(s['Debate Number']) == int(debate['Debate']) and s['Stakeholder'] == stakeholder_name), None)
                    if submission: debate[position_col] = submission['Position']
                    else: debate[position_col] = "Not Submitted"
    
    display_columns = ['Debate', 'Date and Time', 'Resolution','Stakeholder 1', 'Team 1', 'Position 1','Stakeholder 2', 'Team 2', 'Position 2','Stakeholder 3', 'Team 3', 'Position 3','Stakeholder 4', 'Team 4', 'Position 4']
    html_table = generate_html_table(results_data, display_columns)
    st.markdown(html_table, unsafe_allow_html=True)

elif page == "Sign Up / Change Position":
    st.title("Debate Position Sign-up")
    if 'team_name' not in st.session_state: st.session_state.team_name = ""
    if 'assigned_debates' not in st.session_state: st.session_state.assigned_debates = []

    st.header("Step 1: Find Your Debates")
    team_name_input = st.text_input("Enter your official team name exactly as provided:", value=st.session_state.team_name)

    if st.button("Find My Debates"):
        st.session_state.team_name = team_name_input
        st.session_state.assigned_debates = find_debates_for_team(st.session_state.team_name, schedule_data)
        if not st.session_state.assigned_debates: st.error("Team name not found. Please check the spelling and try again.")
        st.rerun()

    if st.session_state.assigned_debates:
        st.header("Step 2: Select a Debate to Sign Up For or Change Position")
        eligible_debates = [item for item in st.session_state.assigned_debates if not ((reveal_date := get_reveal_date_for_debate(item['debate_details'])) and now >= reveal_date)]
        if not eligible_debates:
            st.info("There are no open debates for your team to sign up for at this time.")
        else:
            debate_options = {f"{item['debate_details']['Debate']}: {item['debate_details']['Resolution'][:70]}...": item for item in eligible_debates}
            selected_debate_str = st.selectbox("Choose a debate:", options=debate_options.keys(), index=None, placeholder="Select your debate...")
            if selected_debate_str:
                selected_item = debate_options[selected_debate_str]
                debate_details, stakeholder_role = selected_item['debate_details'], selected_item['stakeholder_role']
                st.subheader(f"Declare Position for Debate #{debate_details['Debate']}")
                st.write(f"**Your Stakeholder Role:** {stakeholder_role}")
                existing_sub = next((s for s in submissions_data if int(s['Debate Number']) == int(debate_details['Debate']) and s['Stakeholder'] == stakeholder_role), None)
                default_index = 1 if existing_sub and existing_sub['Position'] == "Against" else 0
                with st.form(f"signup_form_{debate_details['Debate']}"):
                    position = st.radio("Choose Your Position:", options=["For", "Against"], horizontal=True, index=default_index, key=f"pos_{debate_details['Debate']}")
                    if st.form_submit_button("Submit and Lock Position"):
                        save_submission(int(debate_details['Debate']), stakeholder_role, st.session_state.team_name, position)
                        st.success("Your position has been locked in successfully!")
                        st.balloons()
                        st.rerun()

if password == INSTRUCTOR_PASSWORD:
    st.sidebar.markdown("---")
    st.sidebar.header("Instructor Panel")
    st.sidebar.success("Access Granted")
    missing_submissions = [{'debate': d, 'team': t, 'stakeholder': s} for d in schedule_data if (rd := get_reveal_date_for_debate(d)) and now >= rd for i in range(1, 5) if (t := d.get(f'Team {i}')) and (s := d.get(f'Stakeholder {i}')) and not any(int(sub['Debate Number']) == int(d['Debate']) and sub['Stakeholder'] == s for sub in submissions_data)]
    if missing_submissions:
        with st.sidebar.expander("Assign Positions for Missing Teams", expanded=True):
            st.warning("Action Required: The following teams missed their deadline.")
            missing_options = {f"D{item['debate']['Debate']}: {item['team']}": item for item in missing_submissions}
            selected_missing_str = st.selectbox("Select a team:", options=missing_options.keys())
            if selected_missing_str:
                selected_item = missing_options[selected_missing_str]
                admin_position = st.radio("Assign Position:", ["For", "Against"], key=f"admin_pos_{selected_item['debate']['Debate']}_{selected_item['stakeholder']}")
                if st.button("Force Submit Position"):
                    save_submission(int(selected_item['debate']['Debate']), selected_item['stakeholder'], selected_item['team'], admin_position)
                    st.success("Position assigned.")
                    st.rerun()
    with st.sidebar.expander("Danger Zone"):
        st.error("This will delete all submissions and cannot be undone.")
        if st.checkbox("I understand this will delete all student submissions."):
            if st.button("Reset All Submissions"):
                with file_lock:
                    if os.path.exists(SUBMISSIONS_FILE): os.remove(SUBMISSIONS_FILE)
                st.success("All submissions have been deleted.")
                st.rerun()
    
    with st.sidebar.expander("System Diagnostics"):
        st.write("**Schedule Sanity Check**")
        st.write("Checks if every debate in the CSV has a matching reveal date in the script.")
        errors_found = False
        
        for row in schedule_data:
            date_str = row.get('Date and Time', '')
            if date_str:
                try:
                    dt_obj = datetime.strptime(date_str.split()[0], '%Y-%m-%d')
                    key = dt_obj.strftime('%b %d')
                    if key not in REVEAL_SCHEDULE:
                        st.error(f"Mismatch Found! The date '{date_str}' from your CSV (key: '{key}') is not in the REVEAL_SCHEDULE dictionary.")
                        errors_found = True
                except ValueError:
                    st.error(f"Could not parse date '{date_str}' from CSV. Please use YYYY-MM-DD format.")
                    errors_found = True
        
        if not errors_found:
            st.success("All debate dates in your CSV have a matching reveal date.")
        
        st.markdown("---")
        st.write("**System Time Debugger**")
        now_for_debug = datetime.now(pytz.timezone(TIMEZONE))
        st.write(f"**Current App Time:** `{now_for_debug.strftime('%Y-%m-%d %H:%M:%S %Z')}`")
        sample_reveal_date = REVEAL_SCHEDULE.get("Sep 26")
        if sample_reveal_date:
            st.write(f"**Sample Reveal Date (Sep 26):** `{sample_reveal_date.strftime('%Y-%m-%d %H:%M:%S %Z')}`")
            comparison_result = now_for_debug < sample_reveal_date
            st.write(f"**Is current time before reveal time?** `{comparison_result}`")
            if not comparison_result:
                st.warning("Comparison is FALSE. This is why positions for this date may be revealing.")
            else:
                st.success("Comparison is TRUE. Reveal logic for this date appears correct.")
        else:
            st.error("Could not find the 'Sep 26' key in REVEAL_SCHEDULE.")