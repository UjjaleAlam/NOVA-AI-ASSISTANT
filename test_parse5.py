import ast

# Test with the tuple assigned to a variable first
code = """def end_session(self, session_id: str, **kwargs) -> bool:
        conn = get_ea_connection()
        cursor = conn.cursor()
        sql = (
            "UPDATE ea_focus_sessions SET end_time = ?, actual_duration = ?, "
            "interruptions = ?, notes = ?, productivity_score = ? "
            "WHERE id = ?"
        )
        params = (time.time(), kwargs.get("actual_duration"),
              kwargs.get("interruptions", 0), kwargs.get("notes", ""),
              kwargs.get("productivity_score"), session_id)
        cursor.execute(sql, params)
        conn.commit()
        conn.close()
        return True
"""

try:
    ast.parse(code)
    print('Parse OK')
except Exception as e:
    print(f'Error: {e}')