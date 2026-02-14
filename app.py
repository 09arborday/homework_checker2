# app.py
# 실행: streamlit run app.py

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, Optional, List, Tuple

import streamlit as st

STATE_FILE = "math_homework_state.json"
BAK_FILE = "math_homework_state.json.bak"

STATUSES = ["완료", "틀림", "틀렸지만 고침", "질문"]


# -----------------------------
# Data model
# -----------------------------
@dataclass
class Problem:
    status: str = "완료"
    memo: str = ""


@dataclass
class PageUnit:
    # 문제집의 "쪽(페이지)" 하나를 하나의 단위로 관리
    done: bool = False
    start_problem: Optional[int] = None
    end_problem: Optional[int] = None
    problems: Dict[str, Problem] = field(default_factory=dict)  # "1","2",...


@dataclass
class AppState:
    book_name: str = ""
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    pages: Dict[str, PageUnit] = field(default_factory=dict)  # key: "12" -> p.12


# -----------------------------
# Persistence
# -----------------------------
def save_state(state: AppState) -> None:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                old = f.read()
            with open(BAK_FILE, "w", encoding="utf-8") as f:
                f.write(old)
        except Exception:
            pass

    raw = {
        "book_name": state.book_name,
        "start_page": state.start_page,
        "end_page": state.end_page,
        "pages": {},
    }
    for pk, pu in state.pages.items():
        raw["pages"][pk] = {
            "done": pu.done,
            "start_problem": pu.start_problem,
            "end_problem": pu.end_problem,
            "problems": {k: asdict(v) for k, v in pu.problems.items()},
        }

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)


def load_state() -> Optional[AppState]:
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        stt = AppState(
            book_name=str(raw.get("book_name", "")),
            start_page=raw.get("start_page"),
            end_page=raw.get("end_page"),
            pages={},
        )
        for pk, pu in (raw.get("pages", {}) or {}).items():
            unit = PageUnit(
                done=bool(pu.get("done", False)),
                start_problem=pu.get("start_problem"),
                end_problem=pu.get("end_problem"),
                problems={},
            )
            for k, v in (pu.get("problems", {}) or {}).items():
                unit.problems[str(k)] = Problem(
                    status=str(v.get("status", "완료")),
                    memo=str(v.get("memo", "")),
                )
            stt.pages[str(pk)] = unit

        return stt
    except Exception:
        return None


def reset_disk() -> None:
    for fp in [STATE_FILE, BAK_FILE]:
        if os.path.exists(fp):
            os.remove(fp)


# -----------------------------
# UI helpers
# -----------------------------
def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
          background: linear-gradient(180deg, #fde8ef 0%, #fff6f9 65%, #ffffff 100%);
        }
        .pink-card {
          background: rgba(255,255,255,0.80);
          border: 1px solid rgba(241,183,198,0.55);
          border-radius: 18px;
          padding: 14px 14px 10px 14px;
          box-shadow: 0 10px 24px rgba(0,0,0,0.06);
        }
        .title {
          font-size: 28px;
          font-weight: 900;
          color: #3a2a2f;
          margin: 6px 0 2px 0;
        }
        .subtitle {
          color: #5b3f49;
          margin: 0 0 12px 0;
        }
        div.stButton > button {
          border-radius: 14px !important;
          border: 0px !important;
          padding: 10px 14px !important;
          font-weight: 800 !important;
          background: #f1b7c6 !important;
          color: #3a2a2f !important;
          box-shadow: 0 8px 18px rgba(0,0,0,0.08) !important;
        }
        div.stButton > button:hover {
          filter: brightness(0.985);
          transform: translateY(-1px);
        }
        .small {
          color:#6b4a55;
          font-size:13px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def copy_button_html(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("`", "\\`")
    return f"""
    <div style="display:flex; gap:10px; align-items:center; margin:6px 0 14px 0;">
      <button id="copyBtn"
        style="
          border:none; border-radius:14px; padding:10px 14px;
          background:#f1b7c6; color:#3a2a2f; font-weight:800; cursor:pointer;
          box-shadow: 0 6px 16px rgba(0,0,0,0.08);
        ">
        📋 한 번에 복사
      </button>
      <span id="copyMsg" style="color:#5b3f49; font-size:14px;"></span>
    </div>
    <script>
      const text = `{escaped}`;
      const btn = document.getElementById("copyBtn");
      const msg = document.getElementById("copyMsg");
      btn.addEventListener("click", async () => {{
        try {{
          await navigator.clipboard.writeText(text);
          msg.textContent = "복사 완료!";
          setTimeout(()=>msg.textContent="", 1400);
        }} catch (e) {{
          msg.textContent = "복사 실패(브라우저 권한 확인)";
          setTimeout(()=>msg.textContent="", 2200);
        }}
      }});
    </script>
    """


def goto(view: str, page: Optional[str] = None, problem: Optional[str] = None) -> None:
    st.session_state.view = view
    if page is not None:
        st.session_state.active_page = page
    if problem is not None:
        st.session_state.active_problem = problem
    st.rerun()


def clamp_pages(sp: int, ep: int) -> Tuple[int, int]:
    return (sp, ep) if sp <= ep else (ep, sp)


def ensure_pages_initialized(state: AppState) -> None:
    if state.start_page is None or state.end_page is None:
        return
    sp, ep = clamp_pages(int(state.start_page), int(state.end_page))
    state.start_page, state.end_page = sp, ep
    for p in range(sp, ep + 1):
        k = str(p)
        if k not in state.pages:
            state.pages[k] = PageUnit()


def apply_problem_range(unit: PageUnit, start_n: int, end_n: int) -> None:
    if start_n <= 0 or end_n <= 0:
        raise ValueError("문항 번호는 1 이상이어야 합니다.")
    if start_n > end_n:
        start_n, end_n = end_n, start_n
    if (end_n - start_n) > 500:
        raise ValueError("범위가 너무 큽니다(500개 초과).")

    unit.start_problem = start_n
    unit.end_problem = end_n

    keep = set(str(i) for i in range(start_n, end_n + 1))
    for i in range(start_n, end_n + 1):
        pk = str(i)
        if pk not in unit.problems:
            unit.problems[pk] = Problem(status="완료", memo="")

    for pk in list(unit.problems.keys()):
        if pk not in keep:
            unit.problems.pop(pk, None)


def build_summary(state: AppState) -> str:
    wrong: List[str] = []
    fixed: List[str] = []
    ques: List[str] = []

    if state.start_page is None or state.end_page is None:
        return "숙제 범위가 설정되지 않았습니다."

    sp, ep = clamp_pages(state.start_page, state.end_page)
    for p in range(sp, ep + 1):
        pk = str(p)
        unit = state.pages.get(pk)
        if not unit or not unit.problems:
            continue

        for num, pr in sorted(unit.problems.items(), key=lambda kv: int(kv[0])):
            tag = f"[p.{p} {num}번]"
            if pr.status == "틀림":
                wrong.append(tag)
            elif pr.status == "틀렸지만 고침":
                fixed.append(tag)
            elif pr.status == "질문":
                memo = (pr.memo or "").strip()
                ques.append(f"{tag} {memo}" if memo else f"{tag} (메모 없음)")

    lines: List[str] = []
    lines.append("✅ 오늘 숙제 정리")
    lines.append(f"- 문제집: {state.book_name or '(미입력)'}")
    lines.append(f"- 범위: p.{sp} ~ p.{ep}")
    lines.append(f"- 날짜: {dt.datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("❌ 틀림")
    lines.append(", ".join(wrong) if wrong else "없음")
    lines.append("")
    lines.append("🛠️ 틀렸지만 고침")
    lines.append(", ".join(fixed) if fixed else "없음")
    lines.append("")
    lines.append("❓ 질문 + 메모")
    lines.append("\n".join(ques) if ques else "없음")
    return "\n".join(lines)


# -----------------------------
# App init
# -----------------------------
st.set_page_config(page_title="수학 숙제 체킹", page_icon="🧸", layout="centered")
inject_css()

if "state" not in st.session_state:
    disk = load_state()
    st.session_state.state = disk if disk else AppState()
    st.session_state.ask_reset = bool(disk)

if "view" not in st.session_state:
    st.session_state.view = "home"  # home | page | problem | summary
if "active_page" not in st.session_state:
    st.session_state.active_page = None
if "active_problem" not in st.session_state:
    st.session_state.active_problem = None

state: AppState = st.session_state.state

# 새로고침 시 초기화 여부
if st.session_state.get("ask_reset", False):
    st.markdown('<div class="pink-card">', unsafe_allow_html=True)
    st.write("이전에 저장된 기록이 있어요. 기록을 초기화할까요?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("예(초기화)"):
            reset_disk()
            st.session_state.state = AppState()
            st.session_state.ask_reset = False
            st.session_state.view = "home"
            st.rerun()
    with c2:
        if st.button("아니오(유지)"):
            st.session_state.ask_reset = False
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="title">🧸 수학 과외 숙제 체킹</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">문제집 쪽(p) → 문항 → 메모로 바로 이동</div>', unsafe_allow_html=True)

top1, top2, top3 = st.columns([1, 1, 1])
with top1:
    if st.button("🏠 홈"):
        goto("home")
with top2:
    if st.button("🧾 숙제 정리"):
        goto("summary")
with top3:
    if st.button("🗑️ 전체 초기화"):
        st.session_state.confirm_reset = True

if st.session_state.get("confirm_reset", False):
    st.markdown('<div class="pink-card">', unsafe_allow_html=True)
    st.write("정말 전체 초기화할까요? (복구 어려움)")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("초기화 실행"):
            reset_disk()
            st.session_state.state = AppState()
            st.session_state.confirm_reset = False
            goto("home")
    with c2:
        if st.button("취소"):
            st.session_state.confirm_reset = False
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

ensure_pages_initialized(state)

# -----------------------------
# Views
# -----------------------------
view = st.session_state.view

# HOME
if view == "home":
    st.markdown('<div class="pink-card">', unsafe_allow_html=True)
    st.subheader("1) 문제집 정보 & 숙제 쪽 범위 입력")

    with st.form("setup_form", clear_on_submit=False):
        book = st.text_input("문제집 이름(선택)", value=state.book_name, placeholder="예: RPM 수학(상)")
        c1, c2 = st.columns(2)
        with c1:
            sp = st.number_input("시작 쪽", min_value=1, step=1, value=state.start_page or 1)
        with c2:
            ep = st.number_input("끝 쪽", min_value=1, step=1, value=state.end_page or (state.start_page or 1))
        saved = st.form_submit_button("저장")

    if saved:
        state.book_name = book.strip()
        state.start_page, state.end_page = clamp_pages(int(sp), int(ep))
        ensure_pages_initialized(state)
        save_state(state)
        st.success("저장 완료! 아래에서 쪽(p)을 눌러서 들어가면 돼.")

    st.divider()
    st.subheader("2) 쪽 목록(체크 + 클릭해서 들어가기)")

    if state.start_page is None or state.end_page is None:
        st.info("위에서 숙제 쪽 범위를 먼저 입력해줘.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    sp2, ep2 = clamp_pages(state.start_page, state.end_page)
    total = ep2 - sp2 + 1
    done_cnt = sum(1 for p in range(sp2, ep2 + 1) if state.pages.get(str(p), PageUnit()).done)
    st.caption(f"진행: {done_cnt}/{total} 쪽 완료")

    for p in range(sp2, ep2 + 1):
        pk = str(p)
        unit = state.pages[pk]

        c1, c2, c3 = st.columns([1, 2, 2])
        with c1:
            new_done = st.checkbox("완료", value=unit.done, key=f"done_p_{pk}")
            if new_done != unit.done:
                unit.done = new_done
                save_state(state)
        with c2:
            st.markdown(f"**p.{p}**")
            if unit.start_problem and unit.end_problem:
                st.markdown(f"<div class='small'>문항: {unit.start_problem}~{unit.end_problem}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='small'>문항 범위 미설정</div>", unsafe_allow_html=True)
        with c3:
            if st.button("들어가기", key=f"enter_p_{pk}"):
                save_state(state)
                goto("page", page=pk)

    st.markdown("</div>", unsafe_allow_html=True)

# PAGE DETAIL
elif view == "page":
    pk = st.session_state.active_page
    if not pk or pk not in state.pages:
        goto("home")

    unit = state.pages[pk]
    page_num = int(pk)

    st.markdown('<div class="pink-card">', unsafe_allow_html=True)
    st.subheader(f"p.{page_num} · 문항 체크")

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("← 쪽 목록"):
            save_state(state)
            goto("home")
    with c2:
        done = st.checkbox("이 쪽 전체 완료", value=unit.done, key=f"page_done_{pk}")
        if done != unit.done:
            unit.done = done
            save_state(state)

    st.divider()
    st.write("### 문항 범위 입력(첫 문항 / 끝 문항)")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        sp = st.number_input("첫 문항", min_value=1, step=1, value=unit.start_problem or 1, key=f"sp_{pk}")
    with col2:
        ep = st.number_input("끝 문항", min_value=1, step=1, value=unit.end_problem or (unit.start_problem or 1), key=f"ep_{pk}")
    with col3:
        if st.button("적용", key=f"apply_{pk}"):
            try:
                apply_problem_range(unit, int(sp), int(ep))
                save_state(state)
                st.success("문항 리스트 생성 완료!")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.divider()
    st.write("### 문항 (문항 번호를 누르면 메모로 이동)")

    if not unit.problems:
        st.info("문항 범위를 적용하면 문항들이 생성돼.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    show_only = st.selectbox("보기", ["전체", "틀림", "틀렸지만 고침", "질문"], index=0, key=f"filter_{pk}")
    search = st.text_input("메모 검색(질문 메모에서)", value="", placeholder="예: 부호, 확률", key=f"search_{pk}")

    for num in sorted(unit.problems.keys(), key=lambda x: int(x)):
        pr = unit.problems[num]

        if show_only != "전체" and pr.status != show_only:
            continue
        if search.strip():
            if pr.status == "질문":
                if search.strip() not in (pr.memo or ""):
                    continue
            else:
                continue

        icon = {"완료": "✅", "틀림": "❌", "틀렸지만 고침": "🛠️", "질문": "❓"}.get(pr.status, "•")
        has_memo = "📝" if (pr.memo or "").strip() else ""

        c1, c2, c3 = st.columns([1.2, 2.2, 1.2])
        with c1:
            if st.button(f"{num}번", key=f"probbtn_{pk}_{num}"):
                save_state(state)
                goto("problem", page=pk, problem=num)
        with c2:
            st.markdown(f"<div class='small'>{icon} {pr.status} {has_memo}</div>", unsafe_allow_html=True)
        with c3:
            new_status = st.selectbox(
                "상태",
                STATUSES,
                index=STATUSES.index(pr.status) if pr.status in STATUSES else 0,
                key=f"status_{pk}_{num}",
                label_visibility="collapsed"
            )
            if new_status != pr.status:
                pr.status = new_status
                save_state(state)

    st.markdown("</div>", unsafe_allow_html=True)

# PROBLEM MEMO
elif view == "problem":
    pk = st.session_state.active_page
    num = st.session_state.active_problem
    if not pk or pk not in state.pages:
        goto("home")
    unit = state.pages[pk]
    if not num or num not in unit.problems:
        goto("page", page=pk)

    pr = unit.problems[num]
    page_num = int(pk)

    st.markdown('<div class="pink-card">', unsafe_allow_html=True)
    st.subheader(f"p.{page_num} / {num}번")

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("← p로"):
            save_state(state)
            goto("page", page=pk)
    with c2:
        new_status = st.selectbox(
            "상태",
            STATUSES,
            index=STATUSES.index(pr.status) if pr.status in STATUSES else 0,
            key=f"status_detail_{pk}_{num}"
        )
        if new_status != pr.status:
            pr.status = new_status
            save_state(state)

    st.divider()
    st.write("### 메모")
    memo = st.text_area(
        "질문/풀이/실수 포인트 등 자유롭게",
        value=pr.memo,
        height=220,
        placeholder="예: 3번에서 왜 부등호 방향이 바뀌는지 모르겠음"
    )
    if memo != pr.memo:
        pr.memo = memo
        save_state(state)

    st.caption("메모는 자동 저장돼.")
    st.markdown("</div>", unsafe_allow_html=True)

# SUMMARY
elif view == "summary":
    st.markdown('<div class="pink-card">', unsafe_allow_html=True)
    st.subheader("오늘 숙제 정리")

    summary = build_summary(state)
    st.markdown(copy_button_html(summary), unsafe_allow_html=True)
    st.text_area("정리 결과", value=summary, height=320)

    st.divider()
    if st.button("← 홈으로"):
        goto("home")
    st.markdown("</div>", unsafe_allow_html=True)

else:
    goto("home")
