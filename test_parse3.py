import ast

code = "def end_session(self, session_id: str, **kwargs) -> bool:\n    conn = get_ea_connection()\n    cursor = conn.cursor()\n    sql = (\n        \"UPDATE ea_focus_sessions SET end_time = ?, actual_duration = ?, \"\n        \"interruptions = ?, notes = ?, productivity_score = ? \"\n        \"WHERE id = ?\"\n    )\n    cursor.execute(sql, (time.time(), kwargs.get(\"actual_duration\"),\n          kwargs.get(\"interruptions\", 0), kwargs.get(\"notes\", \"\"),\n          kwargs.get(\"productivity_score\"), session_id))\n    conn.commit()\n    conn.close()\n    return True"

try:
    ast.parse(code)
    print('Parse OK')
except Exception as e:
    print(f'Error: {e}')