"""
챌린지 데이터 관리 및 Git 동기화 모듈
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

def add_log(name: str, passage_count: int):
    """
    새로운 챌린지 기록을 추가하고 GitHub에 동기화합니다.
    """
    if not name:
        return

    # 1. 최신 상태 Pull (충돌 방지)
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
    
    new_entry = {
        "name": name,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": passage_count
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
        subprocess.run(["git", "commit", "-m", f"chore: update challenge log for {name}"], check=True)
        subprocess.run(["git", "push", "origin", "master"], check=True)
        return True
    except Exception as e:
        print(f"Git sync failed: {e}")
        return False

@st.cache_data
def get_user_stats(name: str):
    """특정 사용자의 통계를 반환합니다."""
    data = load_logs()
    user_logs = [log for log in data["logs"] if log["name"] == name]
    
    total_passages = sum(log["count"] for log in user_logs)
    total_days = len(set(log["date"] for log in user_logs))
    
    return total_passages, total_days

@st.cache_data
def get_leaderboard():
    """전체 순위를 반환합니다."""
    data = load_logs()
    stats = {}
    
    for log in data["logs"]:
        name = log["name"]
        if name not in stats:
            stats[name] = {"total_passages": 0, "days": set()}
        stats[name]["total_passages"] += log["count"]
        stats[name]["days"].add(log["date"])
        
    # 리스트로 변환
    leaderboard = []
    for name, stat in stats.items():
        leaderboard.append({
            "이름": name,
            "출석 일수": len(stat["days"]),
            "누적 구절": stat["total_passages"]
        })
    
    # 출석 일수 순으로 정렬 (일수가 같으면 누적 구절 순)
    return sorted(leaderboard, key=lambda x: (x["출석 일수"], x["누적 구절"]), reverse=True)
