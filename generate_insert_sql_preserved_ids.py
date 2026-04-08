import json
import sqlite3

with open("migration_data.json", "r") as f:
    data = json.load(f)

conn = sqlite3.connect("data/boteco.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()


def format_value(v):
    if v is None:
        return "NULL"
    elif isinstance(v, str):
        return f"'{v.replace("'", "''")}'"
    else:
        return str(v)


# Build INSERT for locations
locations = data["locations"]
print(f"Locations: {len(locations)}")
loc_values = []
for loc in locations:
    v = f"({format_value(loc['id'])}, {format_value(loc['name'])}, {format_value(loc['target_monthly_sales'])}, {format_value(loc['target_daily_sales'])}, {format_value(loc['seat_count'])}, {format_value(loc['created_at'])})"
    loc_values.append(v)
print(
    "INSERT INTO public.locations (id, name, target_monthly_sales, target_daily_sales, seat_count, created_at) VALUES"
)
print(",\n".join(loc_values))
print(";")

# Build INSERT for users
users = data["users"]
print(f"\nUsers: {len(users)}")
user_values = []
for u in users:
    v = f"({format_value(u['id'])}, {format_value(u['username'])}, {format_value(u['password_hash'])}, {format_value(u['email'])}, {format_value(u['role'])}, {format_value(u['location_id'])}, {format_value(u['created_at'])})"
    user_values.append(v)
print(
    "INSERT INTO public.users (id, username, password_hash, email, role, location_id, created_at) VALUES"
)
print(",\n".join(user_values))
print(";")

# Build INSERT for daily_summaries - need to preserve old ID for mapping
summaries = data["daily_summaries"]
print(f"\nDaily summaries: {len(summaries)}")
sum_values = []
for s in summaries:
    v = f"({format_value(s['id'])}, {format_value(s['location_id'])}, {format_value(s['date'])}, {format_value(s['covers'])}, {format_value(s['turns'])}, {format_value(s['gross_total'])}, {format_value(s['net_total'])}, {format_value(s['cash_sales'])}, {format_value(s['card_sales'])}, {format_value(s['gpay_sales'])}, {format_value(s['zomato_sales'])}, {format_value(s['other_sales'])}, {format_value(s['service_charge'])}, {format_value(s['cgst'])}, {format_value(s['sgst'])}, {format_value(s['discount'])}, {format_value(s['complimentary'])}, {format_value(s['apc'])}, {format_value(s['target'])}, {format_value(s['pct_target'])}, {format_value(s['mtd_total_covers'])}, {format_value(s['mtd_net_sales'])}, {format_value(s['mtd_discount'])}, {format_value(s['mtd_avg_daily'])}, {format_value(s['mtd_target'])}, {format_value(s['mtd_pct_target'])}, {format_value(s['lunch_covers'])}, {format_value(s['dinner_covers'])}, {format_value(s['order_count'])}, {format_value(s['created_at'])})"
    sum_values.append(v)
print(
    "INSERT INTO public.daily_summaries (id, location_id, date, covers, turns, gross_total, net_total, cash_sales, card_sales, gpay_sales, zomato_sales, other_sales, service_charge, cgst, sgst, discount, complimentary, apc, target, pct_target, mtd_total_covers, mtd_net_sales, mtd_discount, mtd_avg_daily, mtd_target, mtd_pct_target, lunch_covers, dinner_covers, order_count, created_at) VALUES"
)
print(",\n".join(sum_values))
print(";")

# Build INSERT for category_sales using old summary_id
category_sales = data["category_sales"]
print(f"\nCategory sales: {len(category_sales)}")
cat_values = []
for c in category_sales:
    v = f"({format_value(c['id'])}, {format_value(c['summary_id'])}, {format_value(c['category'])}, {format_value(c['qty'])}, {format_value(c['amount'])})"
    cat_values.append(v)
print(
    "INSERT INTO public.category_sales (id, summary_id, category, qty, amount) VALUES"
)
print(",\n".join(cat_values))
print(";")

# Build INSERT for service_sales
service_sales = data["service_sales"]
print(f"\nService sales: {len(service_sales)}")
srv_values = []
for s in service_sales:
    v = f"({format_value(s['id'])}, {format_value(s['summary_id'])}, {format_value(s['service_type'])}, {format_value(s['amount'])})"
    srv_values.append(v)
print("INSERT INTO public.service_sales (id, summary_id, service_type, amount) VALUES")
print(",\n".join(srv_values))
print(";")

# Build INSERT for upload_history
upload_history = data["upload_history"]
print(f"\nUpload history: {len(upload_history)}")
up_values = []
for u in upload_history:
    v = f"({format_value(u['id'])}, {format_value(u['location_id'])}, {format_value(u['date'])}, {format_value(u['filename'])}, {format_value(u['file_type'])}, {format_value(u['uploaded_by'])}, {format_value(u['uploaded_at'])})"
    up_values.append(v)
print(
    "INSERT INTO public.upload_history (id, location_id, date, filename, file_type, uploaded_by, uploaded_at) VALUES"
)
print(",\n".join(up_values))
print(";")

# Build INSERT for user_sessions
user_sessions = data["user_sessions"]
print(f"\nUser sessions: {len(user_sessions)}")
sess_values = []
for u in user_sessions:
    v = f"({format_value(u['token'])}, {format_value(u['user_id'])}, {format_value(u['expires_at'])}, {format_value(u['created_at'])})"
    sess_values.append(v)
print(
    "INSERT INTO public.user_sessions (token, user_id, expires_at, created_at) VALUES"
)
print(",\n".join(sess_values))
print(";")

# Build INSERT for app_meta
app_meta = data["app_meta"]
print(f"\nApp meta: {len(app_meta)}")
meta_values = []
for a in app_meta:
    v = f"({format_value(a['k'])}, {format_value(a['v'])})"
    meta_values.append(v)
print("INSERT INTO public.app_meta (k, v) VALUES")
print(",\n".join(meta_values))
print(";")

conn.close()
