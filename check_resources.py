import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

cursor.execute('SELECT id, title, approval_status, privacy, user_id FROM resources')
resources = cursor.fetchall()

print('All Resources in Database:')
print('=' * 80)
for row in resources:
    print(f'ID: {row[0]}')
    print(f'Title: {row[1]}')
    print(f'Approval Status: {row[2]}')
    print(f'Privacy: {row[3]}')
    print(f'User ID: {row[4]}')
    print('-' * 80)

conn.close()
