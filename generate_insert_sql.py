import json

with open("migration_data.json", "r") as f:
    data = json.load(f)


def format_value(v):
    if v is None:
        return "NULL"
    elif isinstance(v, str):
        return f"'{v.replace("'", "''")}'"
    else:
        return str(v)


# Insert daily_summaries (without id - it will be auto-generated)
summaries = data["daily_summaries"]
values = []
for s in summaries:
    v = f"({format_value(s['location_id'])}, {format_value(s['date'])}, {format_value(s['covers'])}, {format_value(s['turns'])}, {format_value(s['gross_total'])}, {format_value(s['net_total'])}, {format_value(s['cash_sales'])}, {format_value(s['card_sales'])}, {format_value(s['gpay_sales'])}, {format_value(s['zomato_sales'])}, {format_value(s['other_sales'])}, {format_value(s['service_charge'])}, {format_value(s['cgst'])}, {format_value(s['sgst'])}, {format_value(s['discount'])}, {format_value(s['complimentary'])}, {format_value(s['apc'])}, {format_value(s['target'])}, {format_value(s['pct_target'])}, {format_value(s['mtd_total_covers'])}, {format_value(s['mtd_net_sales'])}, {format_value(s['mtd_discount'])}, {format_value(s['mtd_avg_daily'])}, {format_value(s['mtd_target'])}, {format_value(s['mtd_pct_target'])}, {format_value(s['lunch_covers'])}, {format_value(s['dinner_covers'])}, {format_value(s['order_count'])}, {format_value(s['created_at'])})"
    values.append(v)

sql = (
    "INSERT INTO public.daily_summaries (location_id, date, covers, turns, gross_total, net_total, cash_sales, card_sales, gpay_sales, zomato_sales, other_sales, service_charge, cgst, sgst, discount, complimentary, apc, target, pct_target, mtd_total_covers, mtd_net_sales, mtd_discount, mtd_avg_daily, mtd_target, mtd_pct_target, lunch_covers, dinner_covers, order_count, created_at) VALUES\n"
    + ",\n".join(values)
    + ";"
)

with open("insert_daily_summaries.sql", "w") as f:
    f.write(sql)
print(f"Generated insert_daily_summaries.sql with {len(values)} records")

# Insert category_sales
category_sales = data["category_sales"]
values = []
for c in category_sales:
    v = f"({format_value(c['summary_id'])}, {format_value(c['category'])}, {format_value(c['qty'])}, {format_value(c['amount'])})"
    values.append(v)

sql = (
    "INSERT INTO public.category_sales (summary_id, category, qty, amount) VALUES\n"
    + ",\n".join(values)
    + ";"
)
with open("insert_category_sales.sql", "w") as f:
    f.write(sql)
print(f"Generated insert_category_sales.sql with {len(values)} records")

# Insert service_sales
service_sales = data["service_sales"]
values = []
for s in service_sales:
    v = f"({format_value(s['summary_id'])}, {format_value(s['service_type'])}, {format_value(s['amount'])})"
    values.append(v)

sql = (
    "INSERT INTO public.service_sales (summary_id, service_type, amount) VALUES\n"
    + ",\n".join(values)
    + ";"
)
with open("insert_service_sales.sql", "w") as f:
    f.write(sql)
print(f"Generated insert_service_sales.sql with {len(values)} records")

# Insert upload_history
upload_history = data["upload_history"]
values = []
for u in upload_history:
    v = f"({format_value(u['location_id'])}, {format_value(u['date'])}, {format_value(u['filename'])}, {format_value(u['file_type'])}, {format_value(u['uploaded_by'])}, {format_value(u['uploaded_at'])})"
    values.append(v)

sql = (
    "INSERT INTO public.upload_history (location_id, date, filename, file_type, uploaded_by, uploaded_at) VALUES\n"
    + ",\n".join(values)
    + ";"
)
with open("insert_upload_history.sql", "w") as f:
    f.write(sql)
print(f"Generated insert_upload_history.sql with {len(values)} records")

# Insert user_sessions
user_sessions = data["user_sessions"]
values = []
for u in user_sessions:
    v = f"({format_value(u['token'])}, {format_value(u['user_id'])}, {format_value(u['expires_at'])}, {format_value(u['created_at'])})"
    values.append(v)

sql = (
    "INSERT INTO public.user_sessions (token, user_id, expires_at, created_at) VALUES\n"
    + ",\n".join(values)
    + ";"
)
with open("insert_user_sessions.sql", "w") as f:
    f.write(sql)
print(f"Generated insert_user_sessions.sql with {len(values)} records")

# Insert app_meta
app_meta = data["app_meta"]
values = []
for a in app_meta:
    v = f"({format_value(a['k'])}, {format_value(a['v'])})"
    values.append(v)

sql = "INSERT INTO public.app_meta (k, v) VALUES\n" + ",\n".join(values) + ";"
with open("insert_app_meta.sql", "w") as f:
    f.write(sql)
print(f"Generated insert_app_meta.sql with {len(values)} records")

print("All INSERT statements generated!")
