import unittest
from config import AuditConfig
from utils import normalize_url

class CoreTests(unittest.TestCase):
    def test_scope(self):
        c=AuditConfig(start_urls=['http://localhost:8080/section'])
        self.assertTrue(c.in_scope('http://localhost:8080/section/a'))
        self.assertFalse(c.in_scope('http://localhost:8080/section-other'))
        self.assertFalse(c.in_scope('http://localhost:9999/section/a'))
    def test_normalize(self):
        self.assertEqual(normalize_url('http://localhost:8080/section/','a?utm_source=x',{'localhost'},(),(),()),'http://localhost:8080/section/a')
if __name__=='__main__': unittest.main()
