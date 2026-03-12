import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Approve all pending resources
cursor.execute("UPDATE resources SET approval_status = 'approved' WHERE approval_status = 'pending'")
conn.commit()

print(f"✓ Approved {cursor.rowcount} resource(s)")

# Show all resources
cursor.execute('SELECT id, title, approval_status, privacy FROM resources')
resources = cursor.fetchall()

print('\nAll Resources:')
print('=' * 80)
for row in resources:
    print(f'ID: {row[0]} | Title: {row[1]} | Status: {row[2]} | Privacy: {row[3]}')

conn.close()
