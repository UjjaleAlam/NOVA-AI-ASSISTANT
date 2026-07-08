import sqlite3
import os
from pathlib import Path

DATABASE_FOLDER = "database"
DATABASE_NAME = "file_index.db"

os.makedirs(DATABASE_FOLDER, exist_ok=True)

DATABASE_PATH = os.path.join(
    DATABASE_FOLDER,
    DATABASE_NAME
)


def get_connection():

    conn = sqlite3.connect(DATABASE_PATH)

    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("PRAGMA synchronous=NORMAL")

    conn.execute("PRAGMA cache_size=-32000")

    return conn


def initialize_database():
    conn = get_connection()

    cursor = conn.cursor()

    # ============================================
    # Files Table
    # ============================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files(
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            path TEXT UNIQUE NOT NULL,

            extension TEXT,

            size INTEGER,

            modified REAL              
        )
    """)

    # ============================================
    # Folders Table
    # ============================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS folders(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            path TEXT UNIQUE NOT NULL,

            modified REAL
        )
    """)

    # ============================================
    # Full Text Search
    # ============================================
     
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS files_fts
        USING fts5(
                   
            name,
                   
            content='files',
                   
            content_rowid='id',
                   
            tokenize='unicode61'
        )  
    """)

    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS folders_fts
        USING fts5(
           name,
           content='folders',
           content_rowid='id',
           tokenize='unicode61'
        )
    """)

    # ==========================================
    # DOCUMENT CONTENTS
    # (moved above the document_* triggers below --
    #  the table must exist BEFORE a trigger can
    #  target it, or CREATE TRIGGER fails with
    #  "no such table: main.document_contents")
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_contents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            extension TEXT,
            content TEXT NOT NULL,
            indexed REAL
            )
        """)

    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS document_contents_fts
        USING fts5(
            content,
            content='document_contents',
            content_rowid='id',
            tokenize='unicode61'
        )
    """)

    # ============================================
    # Triggers
    # ============================================

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS files_ai
        AFTER INSERT ON files
        BEGIN
                   
            INSERT INTO files_fts(rowid, name)
            VALUES (new.id, new.name);
                   
        END;
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS files_ad
        AFTER DELETE ON files
        BEGIN
            INSERT INTO files_fts(files_fts,rowid,name)
            VALUES('delete',old.id,old.name);
        END;   
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS files_au
        AFTER UPDATE ON files
        BEGIN

            INSERT INTO files_fts(files_fts,rowid, name)
            VALUES ('delete',old.id, old.name);
                   
            INSERT INTO files_fts(rowid,name)
            VALUES(new.id,new.name);

        END;
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS folders_ai
        AFTER INSERT ON folders
        BEGIN
            INSERT INTO folders_fts(rowid,name)
            VALUES(new.id,new.name);
        END; 
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS folders_ad
        AFTER DELETE ON folders
        BEGIN
            INSERT INTO folders_fts(folders_fts,rowid,name)
            VALUES('delete',old.id,old.name);
        END;
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS folders_au
        AFTER UPDATE ON folders
        BEGIN
            INSERT INTO folders_fts(folders_fts, rowid, name)
            VALUES('delete',old.id,old.name);
                   
            INSERT INTO folders_fts(rowid, name)
            VALUES(new.id,new.name);
        END;
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS document_ai
        AFTER INSERT ON document_contents
        BEGIN
                   
            INSERT INTO document_contents_fts(
                rowid,
                content
            )
            VALUES(
                new.id,
                new.content
            );
                   
        END;
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS document_ad
        AFTER DELETE ON document_contents
        BEGIN
        
            INSERT INTO document_contents_fts(
                document_contents_fts,
                rowid, content
            )
            VALUES(
                'delete',
                old.id, 
                old.content
            );
        END;
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS document_au
        AFTER UPDATE ON document_contents
        BEGIN

            INSERT INTO document_contents_fts(
                document_contents_fts,
                rowid,
                content
            )
            VALUES(
                'delete',
                old.id,
                old.content
            );

            INSERT INTO document_contents_fts(
                rowid,
                content
            )
            VALUES(
                new.id,
                new.content
            );

        END;
    """)

    # ===========================================
    # Indexes
    # ===========================================

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_name
        ON files(name COLLATE NOCASE)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_extension
        ON files(extension) 
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_modified
        ON files(modified DESC) 
    """)

    # ===========================================
    # Folder indexes
    # ===========================================

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_folder_name
        ON folders(name COLLATE NOCASE)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_folder_modified
        ON folders(modified DESC)
    """)
    
    # ===========================================
    # Recent Files
    # ===========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recent_files(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            path TEXT UNIQUE NOT NULL,

            name TEXT NOT NULL,

            extension TEXT,

            accessed REAL NOT NULL,

            open_count INTEGER DEFAULT 1      
        )
    """)

    conn.commit()

    conn.close()

# ==========================================
# DATABASE HELPERS
# ==========================================

def file_exists(path):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM files WHERE path=?",
        (path,)
    )

    exists = cursor.fetchone() is not None

    conn.close()

    return exists

def folder_exits(path):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM folders WHERE path=?",
        (path,)
    )

    exists = cursor.fetchone() is not None

    conn.close()

    return exists


def insert_file(path):

    if not os.path.isfile(path):
        return
    
    try:

        stat = os.stat(path)

        name = os.path.basename(path)

        extension = Path(path).suffix.lower()

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO files
            (
                name,
                path,
                extension,
                size,
                modified
            )
            VALUES (?, ?, ?, ?, ?)
                       
            ON CONFLICT(path)
            DO UPDATE SET
                       
                name=excluded.name,
                extension=excluded.extension,
                size=excluded.size,
                modified=excluded.modified
        """,
        (
            name,
            path,
            extension,
            stat.st_size,
            stat.st_mtime
        ))
        
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[DB] insert_file error: {e}")

def insert_folder(path):

    if not os.path.isdir(path):
        return
    
    try:

        stat = os.stat(path)

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute("""

            INSERT INTO folders
            (
                name,
                path,
                modified
            )
                       
            VALUES (?, ?, ?)
            ON CONFLICT(path)
            DO UPDATE SET
                    
                name=excluded.name,
                modified=excluded.modified
        """,
        (
            os.path.basename(path),
            path,
            stat.st_mtime
        ))

        conn.commit()

        conn.close()
    
    except Exception as e:

        print(f"[DB] insert_folder error: {e}")

       
def update_file(path):

    if not os.path.isfile(path):
        return
    
    try:

        stat = os.stat(path)

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute("""
            UPDATE files 
            SET 

               size=?,
               modified=?,
               extension=?,
               name=?

            WHERE path=?
        """,
        (
            stat.st_size,
            stat.st_mtime,
            Path(path).suffix.lower(),
            os.path.basename(path),
            path
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[DB] update_file error: {e}")

def save_document(
        cursor,
        path,
        extension,
        content
):
    import time

    try:

        cursor.execute("""
            INSERT INTO document_contents(
                path,
                extension,
                content,
                indexed
            )

            VALUES (?, ?, ?, ?)
                    
            ON CONFLICT(path)
            DO UPDATE SET
                extension=excluded.extension,
                content=excluded.content,
                indexed=excluded.indexed
        """,
        (
            path,
            extension,
            content,
            time.time()
        ))

    except Exception as e:

        print(f"[DB] save_document error: {e}")

def search_document_contents(
        query,
        limit=20
):
    
    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute("""

            SELECT
                document_contents.path,
                document_contents.extension,

                snippet(
                    document_contents_fts,
                    0,
                    "[",
                    "]",
                    "...",
                    20
                )

            FROM document_contents_fts

            JOIN document_contents

            ON document_contents.id =
               document_contents_fts.rowid

            WHERE document_contents_fts MATCH ?

            LIMIT ?
        """,
        (
            query,
            limit
        ))

        rows = cursor.fetchall()

        conn.close()

        return [
            {
                "path": row[0],
                "extension": row[1],
                "snippet": row[2]
            }
            for row in rows
        ]
    
    except Exception as e:

        print(f"[DB] search_document_contents error: {e}")

        return []


def delete_file(path):

    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM files WHERE path=?",

            (path,)
        )

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[DB] delete_file error: {e}")

def delete_folder(path):

    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM folders WHERE path=?",

            (path,)

        )

        conn.commit()
        conn.close()

    except Exception as e:

        print(f"[DB] delete_folder error: {e}")


# ==========================================
# REBUILD FULL TEXT SEARCH
# ==========================================

def rebuild_fts():

    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO files_fts(files_fts) VALUES('rebuild')"
        )

        conn.commit()

        conn.close()

        print("[DB] FTS rebuilt.")

    except Exception as e:

        print(f"[DB] rebuild_fts error: {e}")


# ==========================================
# RECENT FILES
# ==========================================

def record_open(path):

    if not os.path.isfile(path):
        return

    import time

    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute("""

            INSERT INTO recent_files
            (

                path,

                name,

                extension,

                accessed,

                open_count

            )

            VALUES (?, ?, ?, ?, 1)

            ON CONFLICT(path)

            DO UPDATE SET

                accessed=excluded.accessed,

                open_count=open_count+1

        """,
        (

            path,

            os.path.basename(path),

            Path(path).suffix.lower(),

            time.time()

        ))

        conn.commit()

        conn.close()

    except Exception as e:

        print(f"[DB] record_open error: {e}")


# ==========================================
# GET RECENT FILES
# ==========================================

def get_recent_files(limit=20):

    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute("""

            SELECT

                name,

                path,

                extension,

                accessed,

                open_count

            FROM recent_files

            ORDER BY accessed DESC

            LIMIT ?

        """, (limit,))

        rows = cursor.fetchall()

        conn.close()

        return [

            {

                "name": row[0],

                "path": row[1],

                "extension": row[2],

                "stem": os.path.splitext(row[0])[0],

                "accessed": row[3],

                "open_count": row[4]

            }

            for row in rows

        ]

    except Exception as e:

        print(f"[DB] get_recent_files error: {e}")

        return []
    

# ==========================================
# DATABASE STATS
# ==========================================

def get_stats():

    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(

            "SELECT COUNT(*) FROM files"

        )

        total_files = cursor.fetchone()[0]

        cursor.execute("""

            SELECT

                extension,

                COUNT(*)

            FROM files

            GROUP BY extension

            ORDER BY COUNT(*) DESC

            LIMIT 10

        """)

        top_extensions = cursor.fetchall()

        conn.close()

        return {

            "total": total_files,

            "top_extensions": top_extensions

        }

    except Exception as e:

        print(f"[DB] get_stats error: {e}")

        return {

            "total": 0,

            "top_extensions": []

        }

if __name__ == "__main__":

    initialize_database()

    print("Database ready.")