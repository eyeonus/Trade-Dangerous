import unittest

from tradedangerous import transfers

from . import helpers

BASE_URL = "http://elite.ripz.org/files/"
COMMODITIES = "commodities.json"

class TransfersTest(unittest.TestCase):
    def test_makeUnit(self):
        result = transfers.makeUnit(1024)
        self.assertEqual(result, '  1.0KB')

    def test_download(self):
        transfers.download(helpers.tdenv,
            BASE_URL + COMMODITIES,
            'tmp/' + COMMODITIES)
        self.assertTrue(helpers.file_exists('tmp/' + COMMODITIES))

    def test_get_json_data(self):
        data = transfers.get_json_data(BASE_URL + COMMODITIES)
        self.assertIsInstance(data, list)