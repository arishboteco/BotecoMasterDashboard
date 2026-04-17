"""Tests for dynamic_report_parser helper functions and service data extraction."""

import pytest
from dynamic_report_parser import _meal_from_time


class TestMealFromTime:
    def test_before_6pm_is_lunch(self):
        assert _meal_from_time("2024-03-15 14:30:00") == "Lunch"

    def test_at_6pm_is_dinner(self):
        assert _meal_from_time("2024-03-15 18:00:00") == "Dinner"

    def test_after_6pm_is_dinner(self):
        assert _meal_from_time("2024-03-15 21:15:00") == "Dinner"

    def test_morning_is_lunch(self):
        assert _meal_from_time("2024-03-15 09:00:00") == "Lunch"

    def test_none_returns_none(self):
        assert _meal_from_time(None) is None

    def test_empty_string_returns_none(self):
        assert _meal_from_time("") is None

    def test_nan_returns_none(self):
        assert _meal_from_time("nan") is None

    def test_invalid_string_returns_none(self):
        assert _meal_from_time("not-a-time") is None


class TestDynamicReportServiceData:
    def test_parser_produces_services_key(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = (
            "Bill Date,Bill No,Pax,Net Amount,Gross Sale,Created Date Time\n"
            "2024-03-15,B001,2,500.0,550.0,2024-03-15 12:30:00\n"
            "2024-03-15,B002,4,800.0,880.0,2024-03-15 19:00:00\n"
        )
        records, notes = parse_dynamic_report(csv_content.encode("utf-8"), "test.csv")
        assert records is not None
        assert len(records) == 1
        assert "services" in records[0]
        svc_types = [s["type"] for s in records[0]["services"]]
        assert "Lunch" in svc_types
        assert "Dinner" in svc_types

    def test_service_amounts_match_net_total(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = (
            "Bill Date,Bill No,Pax,Net Amount,Gross Sale,Created Date Time\n"
            "2024-03-15,B001,2,500.0,550.0,2024-03-15 12:30:00\n"
            "2024-03-15,B002,4,300.0,330.0,2024-03-15 12:45:00\n"
        )
        records, _ = parse_dynamic_report(csv_content.encode("utf-8"), "test.csv")
        lunch = next(s for s in records[0]["services"] if s["type"] == "Lunch")
        assert lunch["amount"] == 800.0

    def test_no_created_datetime_column_no_services(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = (
            "Bill Date,Bill No,Pax,Net Amount,Gross Sale\n"
            "2024-03-15,B001,2,500.0,550.0\n"
        )
        records, _ = parse_dynamic_report(csv_content.encode("utf-8"), "test.csv")
        assert records is not None
        assert records[0].get("services") == []


class TestDynamicReportV2Format:
    """Tests for the new line-item Dynamic Report format."""

    def _make_v2_csv(self, rows_text):
        header = (
            "Restaurant,Bill Date,Created Date Time,Bill No,Server Name,Table No,"
            "Bill Status,Payment Type,Discount Reason,Category Name,Item Name,Item Qty,"
            "Pax,Amount,Discount,Net Amount,RoundOff,CGST (2.5),SGST (2.5),"
            "Service Charge (10),Gst On Service Charge (5),Gross Sale,NotPaid,"
            "Cash,Card,Credit,Other Pmt,Wallet,Online,UPI,"
            "Cancelled Amount,Complementary Amount\n"
        )
        return (header + rows_text).encode("utf-8")

    def _make_v2_csv_with_total_col(self, rows_text):
        header = (
            "Restaurant,Bill Date,Created Date Time,Bill No,Server Name,Table No,"
            "Bill Status,Payment Type,Discount Reason,Category Name,Item Name,Item Qty,"
            "Pax,Total,Discount,Net Amount,RoundOff,CGST (2.5),SGST (2.5),"
            "Service Charge (10),Gst On Service Charge (5),Gross Sale,NotPaid,"
            "Cash,Card,Credit,Other Pmt,Wallet,Online,UPI,"
            "Cancelled Amount,Complementary Amount\n"
        )
        return (header + rows_text).encode("utf-8")

    def test_v2_parses_single_bill(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:59:29,8875,Lalan,3,SuccessOrder,Card,-,"
            "Tira Gosto,Chicken Coxinha,1,2,870,0,870,0.15,21.75,21.75,87,4.35,"
            "1005,-,-,1005,-,-,-,-,-,-\n"
        )
        records, notes = parse_dynamic_report(csv_content, "test.csv")
        assert records is not None
        assert len(records) == 1
        r = records[0]
        assert r["date"] == "2026-04-08"
        assert r["covers"] == 2
        assert r["net_total"] == 870.0
        assert r["gross_total"] == 1005.0
        assert r["card_sales"] == 1005.0
        assert r["cash_sales"] == 0.0
        assert r["order_count"] == 1
        assert r["cgst"] == pytest.approx(23.93, abs=0.01)
        assert r["sgst"] == pytest.approx(23.93, abs=0.01)
        assert r["service_charge"] == 87.0

    def test_v2_parses_categories_and_items(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:59:29,8875,Lalan,3,SuccessOrder,Card,-,"
            "Brazilian Bowls,Brazilian Power Bowl,1,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-\n"
            "Boteco,2026-04-08,2026-04-8 12:59:29,8875,Lalan,3,SuccessOrder,Card,-,"
            "Tira Gosto,Chicken Coxinha,2,2,870,0,870,0.15,21.75,21.75,0,0,913,-,"
            "-,913,-,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        assert records is not None
        r = records[0]
        cats = {c["category"]: c for c in r["categories"]}
        assert "Brazilian Bowls" in cats
        assert cats["Brazilian Bowls"]["qty"] == 1
        assert cats["Brazilian Bowls"]["amount"] == 0.0
        assert "Tira Gosto" in cats
        assert cats["Tira Gosto"]["qty"] == 2
        assert cats["Tira Gosto"]["amount"] == 870.0
        items = {i["item_name"]: i for i in r["top_items"]}
        assert "Brazilian Power Bowl" in items
        assert items["Brazilian Power Bowl"]["qty"] == 1
        assert items["Brazilian Power Bowl"]["amount"] == 0.0
        assert "Chicken Coxinha" in items
        assert items["Chicken Coxinha"]["qty"] == 2
        assert items["Chicken Coxinha"]["amount"] == 870.0

    def test_v2_uses_total_column_as_item_amount(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv_with_total_col(
            "Boteco,2026-04-08,2026-04-8 12:59:29,8875,Lalan,3,SuccessOrder,Card,-,"
            "Tira Gosto,Chicken Coxinha,2,2,870,0,870,0.15,21.75,21.75,0,0,913,-,"
            "-,913,-,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        assert records is not None
        r = records[0]
        cats = {c["category"]: c for c in r["categories"]}
        assert cats["Tira Gosto"]["amount"] == 870.0

    def test_v2_super_category_mapping(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:59:29,8875,Lalan,3,SuccessOrder,Card,-,"
            "Brazilian Bowls,Brazilian Power Bowl,1,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-\n"
            "Boteco,2026-04-08,2026-04-8 12:59:29,8875,Lalan,3,SuccessOrder,Card,-,"
            "Hot Beverages,Cappuccino,1,2,500,0,500,0,12.5,12.5,0,0,525,-,-,525,-,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        super_cats = {c["category"]: c for c in r["super_categories"]}
        assert "Food" in super_cats
        assert super_cats["Food"]["qty"] == 1
        assert "Coffee" in super_cats
        assert super_cats["Coffee"]["qty"] == 1

    def test_v2_payment_type_gpay(self):
        from dynamic_report_parser import parse_dynamic_report

        # Payment Type "Other (G Pay)" → gpay_sales
        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:59:29,8875,Lalan,3,SuccessOrder"
            ",Other (G  Pay),-,Tira Gosto,Chicken Coxinha,1,2,870,0,870,0,21.75,21.75,"
            "0,0,913,-,-,-,-,4432,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        assert r["gpay_sales"] == 913.0
        assert r["card_sales"] == 0.0
        assert r["cash_sales"] == 0.0

    def test_v2_payment_type_card(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:59:29,8875,Lalan,3,SuccessOrder,Card,-,"
            "Tira Gosto,Chicken Coxinha,1,2,870,0,870,0.15,21.75,21.75,87,4.35,"
            "1005,-,-,1005,-,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        assert r["card_sales"] == 1005.0
        assert r["cash_sales"] == 0.0

    def test_v2_payment_type_upi(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:59:29,8875,Lalan,3,SuccessOrder"
            ",UPI,-,Tira Gosto,Chicken Coxinha,1,2,870,0,870,0,21.75,21.75,"
            "0,0,913,-,-,-,-,-,-,913,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        assert r["gpay_sales"] == 913.0

    def test_v2_multi_item_bill_groups_correctly(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 1:00:00,8876,Server1,5,SuccessOrder,Card,-,"
            "Brazilian Bowls,Brazilian Power Bowl,1,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-\n"
            "Boteco,2026-04-08,2026-04-8 1:00:00,8876,Server1,5,SuccessOrder,Card,-,"
            "Tira Gosto,Chicken Coxinha,2,3,1500,0,1500,0,37.5,37.5,150,7.5,"
            "1732,-,1732,-,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        assert r["order_count"] == 1
        assert r["covers"] == 3
        assert r["net_total"] == 1500.0
        cats = {c["category"]: c for c in r["categories"]}
        assert "Brazilian Bowls" in cats
        assert cats["Brazilian Bowls"]["qty"] == 1
        assert "Tira Gosto" in cats
        assert cats["Tira Gosto"]["qty"] == 2

    def test_v2_detects_format(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 1:00:00,8876,Server1,5,SuccessOrder,Card,-,"
            "Tira Gosto,Chicken Coxinha,1,2,500,0,500,0,12.5,12.5,0,0,525,-,"
            "-,525,-,-,-,-,-,-\n"
        )
        records, notes = parse_dynamic_report(csv_content, "test.csv")
        assert any("v2" in n.lower() or "line-item" in n.lower() for n in notes)

    def test_v2_qty_weighted_when_line_amounts_missing(self):
        from dynamic_report_parser import parse_dynamic_report

        # Two item lines with no Amount; summary row has net 200 (qty weights 1+1+1).
        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:00:00,9000,S,1,SuccessOrder,Cash,-,"
            "Cat A,Item One,1,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-\n"
            "Boteco,2026-04-08,2026-04-8 12:00:00,9000,S,1,SuccessOrder,Cash,-,"
            "Cat A,Item Two,1,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-,-\n"
            "Boteco,2026-04-08,2026-04-8 12:00:00,9000,S,1,SuccessOrder,Cash,-,"
            "Cat A,Item Two,1,2,-,0,200,0,0,0,0,0,220,-,220,-,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        assert records is not None
        r = records[0]
        cats = {c["category"]: c for c in r["categories"]}
        assert cats["Cat A"]["amount"] == pytest.approx(200.0)
        assert r["cash_sales"] == 220.0

    def test_v2_part_payment_splits_across_buckets(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:00:00,9001,S,1,SuccessOrder,Part Payment,-,"
            "Tira Gosto,Chicken,1,2,500,0,500,0,12.5,12.5,0,0,525,-,"
            "200,200,100,0,0,25,0,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        assert records is not None
        r = records[0]
        # Columns: Cash=200, Card=200, Credit=100, Online=25 (total=525)
        # Credit maps to card_sales -> card=300, Online maps to gpay_sales.
        assert r["cash_sales"] == pytest.approx(200.0)
        assert r["card_sales"] == pytest.approx(300.0)
        assert r["gpay_sales"] == pytest.approx(25.0)
        assert r["other_sales"] == 0.0

    def test_v2_multi_outlet_one_file_same_date(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Indiqube,2026-04-08,2026-04-8 12:00:00,100,S,1,SuccessOrder,Cash,-,"
            "Cat A,Item A,1,1,100,0,100,0,0,0,0,0,110,-,110,-,-,-,-,-,-\n"
            "Bagmane,2026-04-08,2026-04-8 19:00:00,200,S,2,SuccessOrder,Card,-,"
            "Cat B,Item B,1,2,200,0,200,0,0,0,0,0,220,-,220,-,-,-,-,-,-\n"
        )
        records, notes = parse_dynamic_report(csv_content, "test.csv")
        assert records is not None
        assert len(records) == 2
        by_rest = {r["restaurant"]: r for r in records}
        assert "Indiqube" in by_rest
        assert "Bagmane" in by_rest
        assert by_rest["Indiqube"]["net_total"] == 100.0
        assert by_rest["Indiqube"]["cash_sales"] == 110.0
        assert by_rest["Bagmane"]["net_total"] == 200.0
        assert by_rest["Bagmane"]["card_sales"] == 220.0
        assert any("outlet" in n.lower() for n in notes)

    def test_v2_complimentary_bill(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 1:00:00,8876,Server1,5,Complimentary,Card,-,"
            "Tira Gosto,Chicken Coxinha,1,2,500,0,500,0,12.5,12.5,0,0,525,-,"
            "-,525,-,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        assert records is not None
        r = records[0]
        assert r["complimentary"] == 525.0
        assert r["net_total"] == 0

    def test_v2_fallback_when_payment_type_blank(self):
        from dynamic_report_parser import parse_dynamic_report

        # Payment Type empty; Cash column carries the full amount.
        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:00:00,9100,S,1,SuccessOrder,,-,"
            "Tira Gosto,Chicken,1,2,500,0,500,0,12.5,12.5,0,0,525,-,"
            "525,-,-,-,-,-,-,-,-\n"
        )
        records, notes = parse_dynamic_report(csv_content, "test.csv")
        assert records is not None
        r = records[0]
        assert r["cash_sales"] == pytest.approx(525.0)
        assert r["other_sales"] == 0.0
        assert any("fallback applied to 1" in n for n in notes)

    def test_v2_fallback_when_payment_type_unknown(self):
        from dynamic_report_parser import parse_dynamic_report

        # Payment Type text that classifier cannot map; Wallet column carries amount.
        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:00:00,9101,S,1,SuccessOrder,CustomTender,-,"
            "Tira Gosto,Chicken,1,2,500,0,500,0,12.5,12.5,0,0,525,-,"
            "-,-,-,-,525,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        assert r["gpay_sales"] == pytest.approx(525.0)
        assert r["other_sales"] == 0.0

    def test_v2_explicit_zomato_not_overridden(self):
        from dynamic_report_parser import parse_dynamic_report

        # Payment Type "Zomato" classifies cleanly; Online column should not override.
        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:00:00,9102,S,1,SuccessOrder,Zomato,-,"
            "Tira Gosto,Chicken,1,2,500,0,500,0,12.5,12.5,0,0,525,-,"
            "-,-,-,-,-,525,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        assert r["zomato_sales"] == pytest.approx(525.0)
        assert r["gpay_sales"] == 0.0
        assert r["other_sales"] == 0.0

    def test_v2_notpaid_column_ignored(self):
        from dynamic_report_parser import parse_dynamic_report

        # Payment Type empty; only NotPaid has a value. NotPaid is not revenue —
        # no mapped column carries a positive amount, so falls through to other_sales.
        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:00:00,9103,S,1,SuccessOrder,,-,"
            "Tira Gosto,Chicken,1,2,500,0,500,0,12.5,12.5,0,0,525,525,"
            "-,-,-,-,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        assert r["other_sales"] == pytest.approx(525.0)
        assert r["cash_sales"] == 0.0
        assert r["gpay_sales"] == 0.0

    def test_v2_other_pmt_stays_other(self):
        from dynamic_report_parser import parse_dynamic_report

        # Payment Type blank; Other Pmt column is mapped to other_sales so the
        # value is preserved in the Others bucket (explicit Other stays Other).
        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:00:00,9104,S,1,SuccessOrder,,-,"
            "Tira Gosto,Chicken,1,2,500,0,500,0,12.5,12.5,0,0,525,-,"
            "-,-,-,525,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        assert r["other_sales"] == pytest.approx(525.0)
        assert r["cash_sales"] == 0.0

    def test_v2_totally_unclassifiable_bill_lands_in_other(self):
        from dynamic_report_parser import parse_dynamic_report

        # Payment Type empty AND no per-column payment amount at all —
        # last-resort fallback sends gross to other_sales.
        csv_content = self._make_v2_csv(
            "Boteco,2026-04-08,2026-04-8 12:00:00,9105,S,1,SuccessOrder,,-,"
            "Tira Gosto,Chicken,1,2,500,0,500,0,12.5,12.5,0,0,525,-,"
            "-,-,-,-,-,-,-,-,-\n"
        )
        records, _ = parse_dynamic_report(csv_content, "test.csv")
        r = records[0]
        assert r["other_sales"] == pytest.approx(525.0)
