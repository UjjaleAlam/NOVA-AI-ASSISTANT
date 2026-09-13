def ca_debug() -> str:
    conn = get_ca_connection()
    cursor = conn.cursor()
    tables = ["context_snapshots", "activity_events", "presence_periods",
              "proactive_suggestions", "recognized_patterns", "anomalies",
              "inferred_goals", "insights", "awareness_sessions"]
    output = "Continuous Awareness Debug:\n"
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        output += f"  {t}: {count} records\n"
    
    # Snapshot storage info
    snapshot_count = 0
    total_size = 0
    if os.path.exists(SNAPSHOT_DIR):
        for f in os.listdir(SNAPSHOT_DIR):
            if f.endswith('.json'):
                snapshot_count += 1
                total_size += os.path.getsize(os.path.join(SNAPSHOT_DIR, f))
    output += f"\nSnapshot Storage:\n"
    output += f"  JSON files: {snapshot_count}\n"
    output += f"  Total size: {total_size / 1024:.1f} KB\n"
    output += f"  Directory: {SNAPSHOT_DIR}\n"
    
    conn.close()
    return output


def cleanup_old_snapshots(days_to_keep: int = 7) -> Dict:
    """Delete snapshot JSON files older than specified days, keep metadata in DB."""
    cutoff = time.time() - (days_to_keep * 86400)
    deleted = 0
    freed_bytes = 0
    
    conn = get_ca_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, snapshot_file FROM context_snapshots 
        WHERE timestamp < ? AND snapshot_file IS NOT NULL
    """, (cutoff,))
    rows = cursor.fetchall()
    conn.close()
    
    for snap_id, snap_file in rows:
        if snap_file and os.path.exists(snap_file):
            size = os.path.getsize(snap_file)
            os.remove(snap_file)
            deleted += 1
            freed_bytes += size
        
        # Update DB to clear file reference
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE context_snapshots SET snapshot_file = NULL, file_size_bytes = 0 WHERE id = ?", (snap_id,))
        conn.commit()
        conn.close()
    
    return {"deleted": deleted, "freed_mb": freed_bytes / (1024*1024)}


def get_snapshot_data(snapshot_id: str) -> Optional[Dict]:
    """Load full snapshot data from JSON file."""
    conn = get_ca_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT snapshot_file FROM context_snapshots WHERE id = ?", (snapshot_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0] and os.path.exists(row[0]):
        with open(row[0], 'r') as f:
            return json.load(f)
    return None


def get_snapshots_for_session(session_id: str, limit: int = 100) -> List[Dict]:
    """Get snapshot metadata for a session."""
    conn = get_ca_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, active_window, active_app, user_presence, snapshot_file, file_size_bytes
        FROM context_snapshots WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "timestamp": r[1], "active_window": r[2], "active_app": r[3],
         "user_presence": r[4], "snapshot_file": r[5], "file_size_bytes": r[6]}
        for r in rows
    ]


# Global instances
activity_monitor = ActivityMonitor()
pattern_recognizer = PatternRecognizer()
anomaly_detector = AnomalyDetector()
suggestion_engine = ProactiveSuggestionEngine()
insight_generator = InsightGenerator()
session_manager = AwarenessSessionManager()


def start_awareness(session_id: str = None) -> str:
    activity_monitor.start(session_id)
    session_manager.start_session(session_id)
    return f"Continuous awareness started (session: {session_id or 'auto'})"


def stop_awareness() -> Dict:
    activity_monitor.stop()
    return session_manager.end_session()


def get_awareness_status() -> Dict:
    return {
        "monitor": activity_monitor.get_session_stats(),
        "session": session_manager.current_session,
        "pending_suggestions": len(suggestion_engine.get_pending_suggestions()),
        "unacknowledged_anomalies": len([a for a in anomaly_detector.check_system_anomalies()]),
        "new_insights": len(insight_generator.get_insights(status='new'))
    }


def get_proactive_suggestions() -> List[Dict]:
    return suggestion_engine.generate_suggestions()


def get_insights(insight_type: str = None) -> List[Dict]:
    return insight_generator.get_insights(insight_type)


def get_anomalies() -> List[Dict]:
    sys_anoms = anomaly_detector.check_system_anomalies()
    behav_anoms = anomaly_detector.check_behavioral_anomalies()
    return sys_anoms + behav_anoms


def get_patterns(pattern_type: str = None) -> List[Dict]:
    return pattern_recognizer.get_patterns(pattern_type)


def get_daily_summary(date: float = None) -> Dict:
    return session_manager.get_daily_summary(date)


def get_recent_sessions(limit: int = 10) -> List[Dict]:
    return session_manager.get_recent_sessions(limit)


def dismiss_suggestion(suggestion_id: str):
    suggestion_engine.dismiss_suggestion(suggestion_id)
    return f"Dismissed suggestion {suggestion_id}"


def accept_suggestion(suggestion_id: str):
    suggestion_engine.accept_suggestion(suggestion_id)
    session_manager.record_suggestion(accepted=True)
    return f"Accepted suggestion {suggestion_id}"


def record_activity(event_type: str, details: Dict):
    event_id = f"evt_{int(time.time() * 1000) % 100000000:08d}"
    conn = get_ca_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO activity_events (id, event_type, timestamp, details, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (event_id, event_type, time.time(), json.dumps(details),
          session_manager.current_session["id"] if session_manager.current_session else "",
          time.time()))
    conn.commit()
    conn.close()


def record_window_switch():
    session_manager.record_window_switch()
    record_activity("window_switch", {"timestamp": time.time()})


def record_app_launch(app_name: str):
    session_manager.record_app_use(app_name)
    record_activity("app_launch", {"app": app_name, "timestamp": time.time()})


def record_file_open(file_path: str):
    session_manager.record_file_access(file_path)
    record_activity("file_open", {"path": file_path, "timestamp": time.time()})