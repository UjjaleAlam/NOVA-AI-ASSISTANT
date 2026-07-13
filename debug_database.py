import sqlite3

conn = sqlite3.connect("database/file_index.db")
cursor = conn.cursor()

print("document_contents:")
cursor.execute("SELECT COUNT(*) FROM document_contents")
print(cursor.fetchone())

print()

print("document_contents_fts:")
cursor.execute("SELECT COUNT(*) FROM document_contents_fts")
print(cursor.fetchone())

print()

cursor.execute("""
SELECT path
FROM document_contents
ORDER BY rowid DESC
LIMIT 5
""")

print("Latest documents:")

for row in cursor.fetchall():
    print(row)

conn.close()