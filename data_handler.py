from src.data_handler import ProductionDataHandler

class DataHandler(ProductionDataHandler):
    def __init__(self, config):
        super().__init__(config, config.get('plc_name', 'Unknown'))

    def handle_data(self, main_value, feed_value):
        cup_size = self.get_cup_size(feed_value)
        return self.log_production(main_value, feed_value, cup_size)
