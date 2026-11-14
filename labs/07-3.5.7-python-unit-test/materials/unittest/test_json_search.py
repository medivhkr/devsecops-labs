# Fill the Python code in this file
import unittest
from recursive_json_search import *
from test_data import *


class json_search_test(unittest.TestCase):
    '''unit tests for json_search() defined in `recursive_json_search.py`'''
    def test_search_found(self):
        '''existing key: the returned list must not be empty'''
        self.assertTrue([]!=json_search(key1,data))
    def test_search_not_found(self):
        '''missing key: the returned list must be empty'''
        self.assertTrue([]==json_search(key2,data))
    def test_is_a_list(self):
        '''the return value must always be a list'''
        self.assertIsInstance(json_search(key1,data),list)

if __name__ == '__main__':
    unittest.main()
