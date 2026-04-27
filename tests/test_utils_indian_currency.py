"""Tests for Indian currency formatting."""

from utils import format_indian_currency, format_rupee_short


class TestFormatIndianCurrency:
    """Test Indian number formatting (1,30,235 format)."""

    def test_simple_hundreds(self):
        """Test amounts under 1000."""
        assert format_indian_currency(500) == "₹500"
        assert format_indian_currency(999) == "₹999"

    def test_thousands(self):
        """Test amounts in thousands."""
        assert format_indian_currency(1000) == "₹1,000"
        assert format_indian_currency(12345) == "₹12,345"

    def test_lakhs(self):
        """Test amounts in lakhs (100,000s)."""
        assert format_indian_currency(100000) == "₹1,00,000"
        assert format_indian_currency(130235) == "₹1,30,235"
        assert format_indian_currency(999999) == "₹9,99,999"

    def test_crores(self):
        """Test amounts in crores (10,000,000s)."""
        assert format_indian_currency(1000000) == "₹10,00,000"
        assert format_indian_currency(12345678) == "₹1,23,45,678"

    def test_zero(self):
        """Test zero amount."""
        assert format_indian_currency(0) == "₹0"

    def test_negative_amounts(self):
        """Test negative amounts."""
        assert format_indian_currency(-1000) == "-₹1,000"
        assert format_indian_currency(-130235) == "-₹1,30,235"

    def test_decimal_amounts(self):
        """Test amounts with decimals (paise)."""
        assert format_indian_currency(1000.50) == "₹1,000.50"
        assert format_indian_currency(130235.75) == "₹1,30,235.75"

    def test_very_large_amounts(self):
        """Test very large amounts."""
        assert format_indian_currency(123456789) == "₹12,34,56,789"
        assert format_indian_currency(1234567890) == "₹1,23,45,67,890"


class TestFormatRupeeShort:
    """Test rupee short format (k/L notation)."""

    def test_hundreds(self):
        """Test amounts under 1000."""
        assert format_rupee_short(500) == "₹500"
        assert format_rupee_short(999) == "₹999"

    def test_thousands(self):
        """Test amounts in thousands (k notation)."""
        assert format_rupee_short(1000) == "₹1.0k"
        assert format_rupee_short(13000) == "₹13.0k"
        assert format_rupee_short(99999) == "₹100.0k"

    def test_lakhs(self):
        """Test amounts in lakhs (L notation)."""
        assert format_rupee_short(100000) == "₹1.0L"
        assert format_rupee_short(130235) == "₹1.3L"
        assert format_rupee_short(1500000) == "₹15.0L"

    def test_zero(self):
        """Test zero amount."""
        assert format_rupee_short(0) == "₹0"

    def test_negative_amounts(self):
        """Test negative amounts."""
        assert format_rupee_short(-1000) == "-₹1.0k"
        assert format_rupee_short(-130235) == "-₹1.3L"
