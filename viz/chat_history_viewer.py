import streamlit as st
import json
from pathlib import Path

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
    json_path = st.text_input(
        "Enter JSON file path:",
        placeholder="examples/jobs/cobol-modernization/.../chat_history.json",
        key="single_path"
    )

    chat_history, error = load_chat_history(json_path)

    if error:
        st.error(error)
    elif chat_history:
        st.success(f"Loaded {len(chat_history)} messages")

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
        st.info("Enter a path to a chat history JSON file to visualize it.")
        st.markdown("""
        ### Expected JSON Format

        The JSON file should be an array of message objects:

        ```json
        [
          {
            "role": "user" | "agent" | "environment",
            "visible_to": ["user", "agent"],
            "reasoning": "Internal thoughts (optional)",
            "action": "Command executed (optional)",
            "response": "Message content or output"
          }
        ]
        ```

        ### Example path:
        ```
        examples/jobs/cobol-modernization/01-16-10:27:56/chat_history.json
        ```
        """)

else:
    # ─────────────────────────────────────────────────────────
    # Side-by-Side Comparison Mode
    # ─────────────────────────────────────────────────────────
    st.markdown("### Load Trajectories")
    input_col1, input_col2 = st.columns(2)

    with input_col1:
        json_path_1 = st.text_input(
            "Trajectory 1 - JSON path:",
            placeholder="examples/jobs/cobol-modernization/.../chat_history.json",
            key="path_1"
        )

    with input_col2:
        json_path_2 = st.text_input(
            "Trajectory 2 - JSON path:",
            placeholder="examples/jobs/cobol-modernization/.../chat_history.json",
            key="path_2"
        )

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

            with st.expander("🔧 Filters", expanded=True):
                filters_1 = render_filters(chat_history_1, "traj1")

            render_stats(chat_history_1, "traj1")
            st.markdown("---")
            render_messages(chat_history_1, filters_1)
        elif not json_path_1:
            st.info("Enter a JSON path above to load trajectory 1")
        else:
            st.warning("No data loaded")

    # Right Trajectory
    with right_col:
        st.markdown("## Trajectory 2")

        if error_2:
            st.error(error_2)
        elif chat_history_2:
            st.success(f"Loaded {len(chat_history_2)} messages")

            with st.expander("🔧 Filters", expanded=True):
                filters_2 = render_filters(chat_history_2, "traj2")

            render_stats(chat_history_2, "traj2")
            st.markdown("---")
            render_messages(chat_history_2, filters_2)
        elif not json_path_2:
            st.info("Enter a JSON path above to load trajectory 2")
        else:
            st.warning("No data loaded")

    # Help section at bottom
    if not json_path_1 and not json_path_2:
        st.markdown("---")
        st.markdown("""
        ### Expected JSON Format

        The JSON file should be an array of message objects:

        ```json
        [
          {
            "role": "user" | "agent" | "environment",
            "visible_to": ["user", "agent"],
            "reasoning": "Internal thoughts (optional)",
            "action": "Command executed (optional)",
            "response": "Message content or output"
          }
        ]
        ```

        ### Usage
        - Enter paths to two different chat history JSON files to compare them side by side
        - Each trajectory has independent filters for roles, visibility, and message range
        - You can also load just one trajectory if you only want to view a single file
        """)
