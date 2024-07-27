import sqlite3

# def update_subscription(user_id, subscribed):
#     conn = sqlite3.connect('users.db')
#     c = conn.cursor()
#     c.execute("UPDATE users SET subscribed = ? WHERE user_id = ?", (subscribed, user_id))
#     conn.commit()
#     conn.close()
#
# # Update user 1 to be subscribed
# update_subscription( 6859433960, False)


import sqlite3

#
# def delete_users(user_ids):
#     conn = sqlite3.connect('users.db')
#     c = conn.cursor()
#
#     # Execute the DELETE statement for each user_id
#     for user_id in user_ids:
#         c.execute("DELETE FROM users WHERE user_id=?", (user_id,))
#
#         # Check if any row was deleted
#         if c.rowcount == 0:
#             print(f"No user found with user_id: {user_id}")
#         else:
#             print(f"User with user_id: {user_id} has been deleted.")
#
#     # Commit the transaction
#     conn.commit()
#
#     # Close the connection
#     conn.close()
#
#
# # Example usage
# delete_users([6859433960])



import sqlite3

# from main import logger
#
#
# def check_db():
#     conn = sqlite3.connect('users.db')
#     c = conn.cursor()
#
#     try:
#         # Execute the query to get user IDs and subscription end dates
#         c.execute("SELECT user_id, subscription_end FROM users WHERE subscribed = 1")
#         rows = c.fetchall()
#
#         # Log the results for debugging
#         if rows:
#             for user_id, subscription_end in rows:
#                 logger.info(f"User ID: {user_id}, Subscription End: {subscription_end}")
#         else:
#             logger.info("No active subscriptions found.")
#
#     except sqlite3.Error as e:
#         logger.error(f"Database error: {e}")
#
#     finally:
#         conn.close()
#
#
# # Call the function to test
# check_db()
#

def check_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    rows = c.fetchall()
    conn.close()
    for row in rows:
        print(row)

check_db()


