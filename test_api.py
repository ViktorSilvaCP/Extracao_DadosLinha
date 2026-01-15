import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from src.api_routes import get_lot_production  # Import the function directly for testing

# Mock shared_data_manager and plc_configs (required by init_api)
mock_shared_data_manager = MagicMock()
mock_plc_configs = {"Cupper_22": {}, "Cupper_23": {}}

# Initialize the API with mocks (do this once)
from src.api_routes import init_api
init_api(mock_shared_data_manager, mock_plc_configs)

# Sample data for mocking database response
sample_lot_data = [
    {
        "machine_name": "Cupper_22",
        "coil_number": "LOT123",
        "shift": "DIA",
        "total": 1000,
        "start_time": "2023-01-13 08:00:00",
        "end_time": "2023-01-13 18:00:00",
        "consumption_type": "Completa"
    }
]

class TestAPIRoutes(unittest.TestCase):
    def setUp(self):
        """Set up mocks for each test."""
        self.mock_get_production = patch('src.api_routes.DatabaseHandler.get_production_by_lot').start()
        self.mock_time = patch('src.api_routes.get_current_sao_paulo_time').start()
        self.addCleanup(patch.stopall)  # Clean up patches after each test

    def test_get_lot_production_default_date(self):
        """Test get_lot_production with default date (yesterday)."""
        # Mock yesterday's date
        yesterday = datetime(2023, 1, 13)
        self.mock_time.return_value = yesterday + timedelta(days=1)  # Today is 2023-01-14
        self.mock_get_production.return_value = sample_lot_data
        
        # Call the function directly (simulating API call)
        result = get_lot_production()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["coil_number"], "LOT123")
        self.assertEqual(result[0]["total"], 1000)
        self.assertEqual(result[0]["consumption_type"], "Completa")
        # Verify get_production_by_lot was called with yesterday's date
        self.mock_get_production.assert_called_once_with(None, "2023-01-13")

    def test_get_lot_production_custom_date(self):
        """Test get_lot_production with custom date."""
        self.mock_get_production.return_value = sample_lot_data
        
        result = get_lot_production(date="2023-01-12")
        
        self.assertEqual(len(result), 1)
        self.mock_get_production.assert_called_once_with(None, "2023-01-12")

    def test_get_lot_production_with_machine_filter(self):
        """Test get_lot_production with machine name filter."""
        self.mock_get_production.return_value = sample_lot_data
        
        result = get_lot_production(machine_name="Cupper_22", date="2023-01-13")
        
        self.assertEqual(len(result), 1)
        self.mock_get_production.assert_called_once_with("Cupper_22", "2023-01-13")

    def test_get_lot_production_empty_result(self):
        """Test get_lot_production with no data."""
        self.mock_get_production.return_value = []
        
        result = get_lot_production(date="2023-01-13")
        
        self.assertEqual(result, [])
        self.mock_get_production.assert_called_once_with(None, "2023-01-13")

    def test_get_lot_production_invalid_date_handling(self):
        """Test get_lot_production handles invalid date gracefully."""
        self.mock_time.return_value = datetime(2023, 1, 14)
        self.mock_get_production.return_value = sample_lot_data
        
        # Pass invalid date; function should handle it as string
        result = get_lot_production(date="invalid-date")
        
        self.assertEqual(len(result), 1)
        self.mock_get_production.assert_called_once_with(None, "invalid-date")

if __name__ == '__main__':
    unittest.main()
