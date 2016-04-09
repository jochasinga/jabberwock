from crawler import CrawlBase, Spider
import responses, requests
import unittest

class TestCrawlBase(unittest.TestCase):

    def setUp(self):
        self.cb = CrawlBase()
        [self.cb.silo.put(i) for i in range(10)]

    def test_read_seed_urls_from_file(self):
        urls = self.base.read_seed_urls_from_file('seeds.txt')
        self.assertEqual(urls.next(), 'http://digg.com')
        self.assertEqual(urls.next(), 'http://www.buzzfeed.com')
        self.assertEqual(urls.next(), 'https://en.wikipedia.org')
        self.assertEqual(urls.next(), 'https://news.ycombinator.com')
        with self.assertRaises(StopIteration) as ctx:
            gen.next()
        self.assertTrue(StopIteration)

    def test_harvest_content_from_spider
        
        

