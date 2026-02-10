"""
챌린지 데이터 관리 및 Git 동기화 모듈 (출석 중심)
"""
import json
import os
import subprocess
from datetime import datetime
import streamlit as st

DB_FILE = "challenge_db.json"

def _init_db():
    """DB 파일이 없으면 초기화"""
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({"logs": []}, f, ensure_ascii=False, indent=4)

@st.cache_data
def load_logs():
    """로그 데이터를 불러옵니다."""
    _init_db()
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"logs": []}

def add_log(name: str):
    """
    새로운 출석 기록을 추가하고 GitHub에 동기화합니다.
    """
    if not name:
        return

    # 1. 최신 상태 Pull
    try:
        subprocess.run(["git", "pull", "origin", "master", "--rebase"], check=False)
    except Exception as e:
        print(f"Git pull warning: {e}")

    # 2. 데이터 로드 (캐시되지 않은 원본 읽기)
    _init_db()
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {"logs": []}
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 중복 출석 방지 (하루에 한 번만 기록)
    already_checked = any(log["name"] == name and log["date"] == today for log in data["logs"])
    if already_checked:
        return False # 이미 출석함

    new_entry = {
        "name": name,
        "date": today,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    data["logs"].append(new_entry)

    # 3. 파일 저장
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    # 4. 캐시 초기화
    st.cache_data.clear()

    # 5. GitHub Push
    try:
        subprocess.run(["git", "add", DB_FILE], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: add attendance log for {name}"], check=True)
        subprocess.run(["git", "push", "origin", "master"], check=True)
        return True
    except Exception as e:
        print(f"Git sync failed: {e}")
        return False

@st.cache_data
def get_user_stats(name: str):
    """특정 사용자의 출석 일수를 반환합니다."""
    data = load_logs()
    user_logs = [log for log in data["logs"] if log["name"] == name]
    total_days = len(set(log["date"] for log in user_logs))
    return total_days

@st.cache_data
def get_leaderboard():
    """전체 출석 순위를 반환합니다."""
    data = load_logs()
    stats = {}
    
    for log in data["logs"]:
        name = log["name"]
        if name not in stats:
            stats[name] = set()
        stats[name].add(log["date"])
        
    # 리스트로 변환
    leaderboard = []
    for name, days in stats.items():
        leaderboard.append({
            "이름": name,
            "출석 일수": len(days)
        })
    
    # 출석 일수 순으로 정렬
    return sorted(leaderboard, key=lambda x: x["출석 일수"], reverse=True)