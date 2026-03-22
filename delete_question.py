from database.connection import get_conn

QUESTION_ID = 377 

with get_conn() as conn:
    cur = conn.cursor()

    cur.execute("SELECT id, question_text FROM questions WHERE id = ?", (QUESTION_ID,))
    row = cur.fetchone()
    print("FOUND:", row)

    if row:
        cur.execute("DELETE FROM questions WHERE id = ?", (QUESTION_ID,))
        conn.commit()
        print("DELETED")
    else:
        print("Question not found")