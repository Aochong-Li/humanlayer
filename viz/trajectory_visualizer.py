import streamlit as st
import json
from pathlib import Path

# Example:streamlit run viz/trajectory_visualizer.py --server.port 8095

st.set_page_config(
    page_title="Chat History Viewer",
    page_icon="💬",
    layout="wide"
)

st.title("Chat History Viewer")

# Mode selection
view_mode = st.radio(
    "View mode:",
    options=["Single Trajectory", "Side-by-Side Comparison"],
    horizontal=True
)

# Jobs and Tasks directories
JOBS_DIR = Path(__file__).parent.parent / "examples" / "jobs"
TASKS_DIR = Path(__file__).parent.parent / "examples" / "tasks"


def load_task_instruction(task_name: str):
    """Load task instruction markdown if it exists."""
    if not task_name:
        return None
    instruction_path = TASKS_DIR / task_name / "instruction.md"
    if instruction_path.exists():
        return instruction_path.read_text()
    return None


def get_available_tasks():
    """Get list of available task directories."""
    if not JOBS_DIR.exists():
        return []
    return sorted([d.name for d in JOBS_DIR.iterdir() if d.is_dir()])


def get_run_types(task_name: str):
    """Get available run types (useragent/agentonly) for a task."""
    task_path = JOBS_DIR / task_name
    if not task_path.exists():
        return []
    return sorted([d.name for d in task_path.iterdir() if d.is_dir()])


def get_runs(task_name: str, run_type: str):
    """Get available runs for a task and run type."""
    runs_path = JOBS_DIR / task_name / run_type
    if not runs_path.exists():
        return []
    return sorted([d.name for d in runs_path.iterdir() if d.is_dir()], reverse=True)


def build_job_selector(key_prefix: str):
    """Build a hierarchical job selector UI. Returns (chat_history_path, task_name) tuple."""
    tasks = get_available_tasks()
    if not tasks:
        st.warning("No tasks found in examples/jobs/")
        return None, None

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_task = st.selectbox(
            "Task:",
            options=[""] + tasks,
            key=f"{key_prefix}_task",
            format_func=lambda x: "Select a task..." if x == "" else x
        )

    if not selected_task:
        return None, None

    run_types = get_run_types(selected_task)
    with col2:
        selected_type = st.selectbox(
            "Run Type:",
            options=[""] + run_types,
            key=f"{key_prefix}_type",
            format_func=lambda x: "Select type..." if x == "" else x
        )

    if not selected_type:
        return None, selected_task

    runs = get_runs(selected_task, selected_type)
    with col3:
        selected_run = st.selectbox(
            "Run:",
            options=[""] + runs,
            key=f"{key_prefix}_run",
            format_func=lambda x: "Select run..." if x == "" else x
        )

    if not selected_run:
        return None, selected_task

    # Build and return the full path
    # Try history.json first (for orchestrated runs), then chat_history.json
    history_path = JOBS_DIR / selected_task / selected_type / selected_run / "history.json"
    chat_path = JOBS_DIR / selected_task / selected_type / selected_run / "chat_history.json"

    if history_path.exists():
        st.caption(f"`{history_path.relative_to(JOBS_DIR.parent.parent)}`")
        return str(history_path), selected_task
    elif chat_path.exists():
        st.caption(f"`{chat_path.relative_to(JOBS_DIR.parent.parent)}`")
        return str(chat_path), selected_task
    else:
        st.error(f"history.json or chat_history.json not found in selected run")
        return None, selected_task


def load_chat_history(json_path: str):
    """Load chat history from a JSON file."""
    if not json_path:
        return None, None
    try:
        with open(json_path, 'r') as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, f"File not found: {json_path}"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def load_run_log(history_path: str):
    """Load run log from config.json (or fallback to run_log.json) in the same directory."""
    if not history_path:
        return None

    # Try config.json first (new format)
    log_path = Path(history_path).parent / "config.json"
    if not log_path.exists():
        # Fallback to run_log.json (old format)
        log_path = Path(history_path).parent / "run_log.json"
        
    if not log_path.exists():
        return None

    try:
        with open(log_path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def render_verification_result(result_data, run_log=None):
    """Render verification result with success/failure badge."""
    if not result_data:
        if run_log:
            model_name = run_log.get("model_name", "unknown")
            st.info(f"🤖 Model: **{model_name}**")
        return

    success = result_data.get("success", 0)
    returncode = result_data.get("returncode", -1)
    test_output = result_data.get("test_output", "")
    verify = result_data.get("verify", "")

    # Display success/failure badge and model name
    col1, col2 = st.columns([1, 1])
    with col1:
        if success == 1:
            st.success("✅ Verification: PASSED")
        else:
            st.error("❌ Verification: FAILED")
    
    with col2:
        if run_log:
            model_name = run_log.get("model_name", "unknown")
            st.info(f"🤖 Model: **{model_name}**")

    # Show return code
    st.caption(f"Return code: `{returncode}`")

    # Show test output and verification details in expandable sections
    if test_output or verify:
        with st.expander("🔍 Test Output & Verification Details", expanded=False):
            if test_output:
                st.markdown("**Test Output:**")
                st.code(test_output, language="text")

            if verify and verify != test_output:  # Only show if different
                st.markdown("**Verification:**")
                st.code(verify, language="text")


def render_filters(chat_history, key_prefix: str):
    """Render filter controls and return filter settings."""
    if not chat_history:
        return None

    # Get unique roles
    roles = list(set(msg.get("role", "unknown") for msg in chat_history))
    selected_roles = st.multiselect(
        "Show roles:",
        options=roles,
        default=roles,
        key=f"{key_prefix}_roles"
    )

    # Visibility filter
    all_visibility = set()
    for msg in chat_history:
        all_visibility.update(msg.get("visible_to", []))
    visibility_filter = st.multiselect(
        "Visible to:",
        options=list(all_visibility),
        default=list(all_visibility),
        key=f"{key_prefix}_visibility"
    )

    # Range slider for messages
    max_msgs = len(chat_history)
    msg_range = st.slider(
        "Message range:",
        min_value=1,
        max_value=max_msgs,
        value=(1, min(50, max_msgs)),
        key=f"{key_prefix}_range"
    )

    return {
        "selected_roles": selected_roles,
        "visibility_filter": visibility_filter,
        "msg_range": msg_range
    }


def render_message(msg, index: int):
    """Render a single message."""
    role = msg.get("role", "unknown")
    visible_to = msg.get("visible_to", [])

    # Style based on role
    if role == "user":
        icon = "👤"
        color = "#1E88E5"
        bg_color = "#E3F2FD"
    elif role == "agent":
        icon = "🤖"
        color = "#43A047"
        bg_color = "#E8F5E9"
    elif role == "environment":
        icon = "💻"
        color = "#757575"
        bg_color = "#F5F5F5"
    elif role == "system":
        icon = "⚙️"
        color = "#F57C00"
        bg_color = "#FFF3E0"
    else:
        icon = "❓"
        color = "#9E9E9E"
        bg_color = "#FAFAFA"

    with st.container():
        col1, col2 = st.columns([1, 11])

        with col1:
            st.markdown(f"<h2 style='margin:0;'>{icon}</h2>", unsafe_allow_html=True)

        with col2:
            visibility_str = ", ".join(visible_to) if visible_to else "none"
            st.markdown(
                f"<div style='background-color:{bg_color}; padding:10px; border-radius:8px; border-left:4px solid {color};'>"
                f"<strong style='color:{color};'>#{index} {role.upper()}</strong> "
                f"<small style='color:#888;'>(visible to: {visibility_str})</small>",
                unsafe_allow_html=True
            )

            # Reasoning
            reasoning = msg.get("reasoning", "").strip()
            if reasoning:
                with st.expander("💭 Reasoning", expanded=False):
                    st.markdown(f"*{reasoning}*")

            # Action
            action = msg.get("action", "").strip()
            if action:
                st.markdown("**Action:**")
                st.code(action, language="bash")

            # Response
            response = msg.get("response", "").strip()
            if response:
                if role == "environment":
                    st.markdown("**Output:**")
                    st.code(response, language="text")
                elif role == "agent":
                    st.markdown("**Response:**")
                    st.markdown(response)
                elif role == "system":
                    st.markdown("**System:**")
                    st.markdown(f"*{response}*")
                else:
                    st.markdown("**Message:**")
                    st.markdown(response)

            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("")


def render_messages(chat_history, filters):
    """Render filtered messages."""
    if not chat_history or not filters:
        return

    msg_range = filters["msg_range"]
    selected_roles = filters["selected_roles"]
    visibility_filter = filters["visibility_filter"]

    for i, msg in enumerate(chat_history[msg_range[0]-1:msg_range[1]], start=msg_range[0]):
        role = msg.get("role", "unknown")
        visible_to = msg.get("visible_to", [])

        # Apply filters
        if role not in selected_roles:
            continue
        if not any(v in visibility_filter for v in visible_to):
            continue

        render_message(msg, i)


def render_stats(chat_history, key_prefix: str):
    """Render statistics for a chat history."""
    if not chat_history:
        return

    st.markdown("**Statistics:**")
    role_counts = {}
    for msg in chat_history:
        r = msg.get("role", "unknown")
        role_counts[r] = role_counts.get(r, 0) + 1

    cols = st.columns(len(role_counts))
    for col, (role, count) in zip(cols, sorted(role_counts.items())):
        col.metric(f"{role.capitalize()}", count)


# ─────────────────────────────────────────────────────────────
# Main Layout
# ─────────────────────────────────────────────────────────────

if view_mode == "Single Trajectory":
    # ─────────────────────────────────────────────────────────
    # Single Trajectory Mode
    # ─────────────────────────────────────────────────────────
    st.markdown("### Select Job")
    json_path, selected_task = build_job_selector("single")

    # Fallback to manual path entry
    with st.expander("Or enter path manually"):
        manual_path = st.text_input(
            "JSON file path:",
            placeholder="examples/jobs/.../history.json or .../chat_history.json",
            key="single_path_manual"
        )
        if manual_path:
            json_path = manual_path
            selected_task = None  # Can't determine task from manual path

    # Show task instruction if available
    if selected_task:
        instruction = load_task_instruction(selected_task)
        if instruction:
            with st.expander("Task Instruction", expanded=False):
                st.markdown(instruction)
        else:
            st.caption(f"No instruction.md found for task: {selected_task}")

    chat_history, error = load_chat_history(json_path)

    if error:
        st.error(error)
    elif chat_history:
        st.success(f"Loaded {len(chat_history)} messages")

        # Load and display verification results
        verification_result = load_verification_result(json_path)
        run_log = load_run_log(json_path)
        if verification_result or run_log:
            st.markdown("---")
            render_verification_result(verification_result, run_log)
            st.markdown("---")

        # Sidebar filters
        st.sidebar.header("Filters")

        # Get unique roles
        roles = list(set(msg.get("role", "unknown") for msg in chat_history))
        selected_roles = st.sidebar.multiselect(
            "Show roles:",
            options=roles,
            default=roles,
            key="single_roles"
        )

        # Visibility filter
        all_visibility = set()
        for msg in chat_history:
            all_visibility.update(msg.get("visible_to", []))
        visibility_filter = st.sidebar.multiselect(
            "Visible to:",
            options=list(all_visibility),
            default=list(all_visibility),
            key="single_visibility"
        )

        # Range slider for messages
        max_msgs = len(chat_history)
        msg_range = st.sidebar.slider(
            "Message range:",
            min_value=1,
            max_value=max_msgs,
            value=(1, min(50, max_msgs)),
            key="single_range"
        )

        st.markdown("---")

        # Display messages
        for i, msg in enumerate(chat_history[msg_range[0]-1:msg_range[1]], start=msg_range[0]):
            role = msg.get("role", "unknown")
            visible_to = msg.get("visible_to", [])

            # Apply filters
            if role not in selected_roles:
                continue
            if not any(v in visibility_filter for v in visible_to):
                continue

            render_message(msg, i)

        # Stats in sidebar
        st.sidebar.markdown("---")
        st.sidebar.header("Statistics")
        role_counts = {}
        for msg in chat_history:
            r = msg.get("role", "unknown")
            role_counts[r] = role_counts.get(r, 0) + 1

        for role, count in sorted(role_counts.items()):
            st.sidebar.metric(f"{role.capitalize()} messages", count)

    elif not json_path:
        st.info("Select a task, run type, and run from the dropdowns above to view chat history.")

else:
    # ─────────────────────────────────────────────────────────
    # Side-by-Side Comparison Mode
    # ─────────────────────────────────────────────────────────
    st.markdown("### Select Trajectories to Compare")

    traj_col1, traj_col2 = st.columns(2)

    with traj_col1:
        st.markdown("**Trajectory 1**")
        json_path_1, selected_task_1 = build_job_selector("compare1")
        with st.expander("Or enter path manually"):
            manual_path_1 = st.text_input(
                "JSON path:",
                placeholder="examples/jobs/.../history.json or .../chat_history.json",
                key="path_1_manual"
            )
            if manual_path_1:
                json_path_1 = manual_path_1
                selected_task_1 = None

    with traj_col2:
        st.markdown("**Trajectory 2**")
        json_path_2, selected_task_2 = build_job_selector("compare2")
        with st.expander("Or enter path manually"):
            manual_path_2 = st.text_input(
                "JSON path:",
                placeholder="examples/jobs/.../history.json or .../chat_history.json",
                key="path_2_manual"
            )
            if manual_path_2:
                json_path_2 = manual_path_2
                selected_task_2 = None

    # Show task instruction (use task from trajectory 1, or 2 if 1 not selected)
    display_task = selected_task_1 or selected_task_2
    if display_task:
        instruction = load_task_instruction(display_task)
        if instruction:
            with st.expander(f"Task Instruction: {display_task}", expanded=False):
                st.markdown(instruction)
        else:
            st.caption(f"No instruction.md found for task: {display_task}")

    # Load both trajectories
    chat_history_1, error_1 = load_chat_history(json_path_1)
    chat_history_2, error_2 = load_chat_history(json_path_2)

    st.markdown("---")

    # Main comparison view
    left_col, right_col = st.columns(2)

    # Left Trajectory
    with left_col:
        st.markdown("## Trajectory 1")

        if error_1:
            st.error(error_1)
        elif chat_history_1:
            st.success(f"Loaded {len(chat_history_1)} messages")

            # Load and display verification results
            verification_result_1 = load_verification_result(json_path_1)
            run_log_1 = load_run_log(json_path_1)
            if verification_result_1 or run_log_1:
                render_verification_result(verification_result_1, run_log_1)
                st.markdown("---")

            with st.expander("🔧 Filters", expanded=True):
                filters_1 = render_filters(chat_history_1, "traj1")

            render_stats(chat_history_1, "traj1")
            st.markdown("---")
            render_messages(chat_history_1, filters_1)
        elif not json_path_1:
            st.info("Select a job above to load trajectory 1")
        else:
            st.warning("No data loaded")

    # Right Trajectory
    with right_col:
        st.markdown("## Trajectory 2")

        if error_2:
            st.error(error_2)
        elif chat_history_2:
            st.success(f"Loaded {len(chat_history_2)} messages")

            # Load and display verification results
            verification_result_2 = load_verification_result(json_path_2)
            run_log_2 = load_run_log(json_path_2)
            if verification_result_2 or run_log_2:
                render_verification_result(verification_result_2, run_log_2)
                st.markdown("---")

            with st.expander("🔧 Filters", expanded=True):
                filters_2 = render_filters(chat_history_2, "traj2")

            render_stats(chat_history_2, "traj2")
            st.markdown("---")
            render_messages(chat_history_2, filters_2)
        elif not json_path_2:
            st.info("Select a job above to load trajectory 2")
        else:
            st.warning("No data loaded")

    # Help section at bottom
    if not json_path_1 and not json_path_2:
        st.markdown("---")
        st.markdown("""
        ### Usage
        - Select tasks from the dropdowns above to compare different run types side by side
        - Run types: `useragent`, `agentonly`, `orchestrated`, `orchestrated_simple`
        - Each trajectory has independent filters for roles, visibility, and message range
        """)
