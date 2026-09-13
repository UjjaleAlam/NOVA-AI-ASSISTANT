import ast

code = """    def end_session(self, session_id: str, **kwargs) -> bool:
        conn = get_ea_connection()
        cursor = conn.cursor()
        sql = (
            "UPDATE ea_focus_sessions SET end_time = ?, actual_duration = ?, "
            "interruptions = ?, notes = ?, productivity_score = ? "
            "WHERE id = ?"
        )
        cursor.execute(sql, (time.time(), kwargs.get("actual_duration"),
              kwargs.get("interruptions", 0), kwargs.get("notes", ""),
              kwargs.get("productivity_score"), session_id)
        conn.commit()
        conn.close()
        return True
"""

try:
    ast.parse(code)
    print('Parse OK')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()