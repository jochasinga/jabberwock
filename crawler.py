from __future__ import print_function

import os
import re
import logging
import requests
import responses
# Python 3 is urllib.parse
from urlparse import urlsplit
from bs4 import BeautifulSoup
import gevent
from gevent import Greenlet
from gevent.queue import Queue, Empty
from gevent.pool import Pool

logger = logging.getLogger('general')

class CrawlBase(object):
    """
    CrawlBase is a singleton Pool which acts like a head quarter spawning crawlers.
    Only one is needed in running a crawl operation.
    """
    silo = Queue()
    spider_count = 0

    def __init__(self, max_pool=100):
        """The contructor create a pool  with the default of
           max_pool = 100 and start it.
           TODO: Write tests
        """
        self.pool = Pool(max_pool)
        #self.pool.start()

    def read_seed(self, file='seeds.txt'):
        """By default, CrawlBase reads seed URLs from a text file

        >>> urls = c.read_seed('seeds.txt')
        >>> urls.next()
        'http://digg.com'
        >>> urls.next()
        'http://www.buzzfeed.com'
        >>> urls.next()
        'http://www.bustle.com'
        >>> urls.next()
        'https://en.wikipedia.org'
        >>> urls.next()
        'https://news.ycombinator.com'
        >>> urls.next()
        Traceback (most recent call last):
        ...
        StopIteration

        """
        with open(file) as f:
            for line in f:
                if len(line) > 0 and line != "\n":
                    yield line.strip()
                else:
                    return

    def dispatch(self):
        """Spawn more spider"""
        if self.pool.full():
            raise Exception("Maximum pool size reached")
        else:
            self.pool.map(Spider, self.read_seed())

    def harvest(self):
        """Harvest from the silo"""
        try:
            while True:
                content = self.silo.get(timeout=2)
                # test printing only
                print(content)
                gevent.sleep(0)
        except Empty:
            logger.info("Silo is empty.")
            self.kill()

    def kill(self):
        self.pool.kill()

class Spider(Greenlet):
    """Crawler is a worker instance which fetch and crawl the web
       and put the soupified content into the CrawlBase's silo.
    """
    #name, email = None

    def __init__(self, url=None, name='Charlotte', depth=1, **kwargs):
        """The contructor has a default name 'Charlotte' and depth = 1.

        >>> s.name
        'Charlotte'
        >>> s.storage != None
        True
        >>> s.depth
        1
        >>> isinstance(sp, Greenlet)
        True
        >>> sp.name
        'Charlotte'
        >>> sp.depth
        3
        >>> sp.org
        'Looqsie'
        >>> sp.website
        'looqsie.com'
        >>> sp.email
        'jo@looqsie.com'
        >>> sp.message
        'Hello! Thank you.'

        """
        self.id      = CrawlBase.spider_count
        self.name    = name
        self.depth   = depth
        self.org     = None
        self.website = None
        self.email   = None
        self.message = None
        self.rules   = None
        self.headers = None
        self.storage = Queue()

        for key, arg in kwargs.iteritems():
            if key == 'org':
                self.org = str(arg)
            elif key == 'website':
                self.website = str(arg)
            elif key == 'email':
                self.email = str(arg)
            elif key == 'message':
                self.message = str(arg)
            else:
                raise TypeError('Wrong keyword for an argument to Spider constructor.')

        self.prepare_headers()

        CrawlBase.spider_count += 1

        Greenlet.__init__(self)

    def prepare_headers(self):
        """Prepare the appropriate headers to send with the requests

        >>> sp.headers['user-agent']['name']
        'Charlotte'
        >>> sp.headers['user-agent']['org']
        'Looqsie'
        >>> sp.headers['user-agent']['website']
        'looqsie.com'
        >>> sp.headers['user-agent']['email']
        'jo@looqsie.com'
        >>> sp.headers['user-agent']['message']
        'Hello! Thank you.'

        """

        if self.headers is None:
            self.headers = {'user-agent': {'name': self.name}}

        if self.org is not None:
            self.headers['user-agent']['org'] = self.org
        if self.website is not None:
            self.headers['user-agent']['website'] = self.website
        if self.email is not None:
            self.headers['user-agent']['email'] = self.email
        if self.message is not None:
            self.headers['user-agent']['message'] = self.message

    def fetch_rules(self, url):
        """
        Fetch the host's robots.txt, break it up into an agent dictionary in this
        structure => agent_dict[u'User-agent'] = {u'Allow': [url1, url2, ...]}
        for read_rules() to match to self.name

        >>> sp.headers is not None
        True
        >>> sp.headers['user-agent']['name']
        'Charlotte'
        >>> agent_dict = sp.fetch_rules('https://en.wikipedia.org')
        >>> agent_dict is not None
        True
        >>> len(agent_dict) > 0
        True
        >>>
        """
        agent_dict = None
        scheme = urlsplit(url).scheme
        hostname = urlsplit(url).hostname
        addr = scheme + '://' + hostname
        robots_dst = os.path.join(addr, 'robots.txt')

        try:
            resp = requests.get(robots_dst, headers=self.headers, timeout=2)
        except requests.exceptions.RequestException as e:
            logger.error(e)
        else:
            pass

        # Presume no robots.txt
        if resp.status_code != 200:
            logger.debug("No robots.txt found.")
            return agent_dict
        else:
            agent_dict = {}
            lines = resp.text.splitlines()
            for l in lines:
                pair = map(lambda s: s.strip(), l.split(':', 1))
                if len(pair) == 2:
                    if pair[0] == 'User-agent'and pair[1] not in agent_dict:
                        key = pair[1]
                        agent_dict[key] = {}
                    else:
                        for agent in agent_dict:
                            if pair[0] not in agent_dict[agent]:
                                agent_dict[agent][pair[0]] = []
                                agent_dict[agent][pair[0]].append(pair[1])
                            else:
                                agent_dict[agent][pair[0]].append(pair[1])

        return agent_dict

    def read_rules(self, agent_dict):
        """
        Take an agent dictionary, investigate the user-agent key,
        and if the key matches the name of this spider's user-agent,
        set self.rules to the dictionary of that matched user-agent.

        >>> for_all = {u'*': {u'Disallow': [u'/', u'/forbidden']}}
        >>> s.read_rules(for_all)
        True
        >>> s.rules
        {u'Disallow': [u'/', u'/forbidden']}
        >>> for_charlotte = {u'Charlotte': {u'Allow': [u'/goahead']}}
        >>> s.read_rules(for_charlotte)
        True
        >>> s.rules
        {u'Allow': [u'/goahead']}
        >>> for_others = {u'Anonymous Spider': {u'Allow': [u'/spiderhere']}}
        >>> s.read_rules(for_others)
        False
        >>> print(s.rules)
        None
        >>> no_rule = None
        >>> s.read_rules(no_rule)
        False
        >>> print(s.rules)
        None

        """
        if agent_dict is not None:
            for agent in agent_dict:
                if agent == '*' or agent == self.name:
                    self.rules = agent_dict[agent]
                    return True
                else:
                    logger.debug("No rules matched for this spider's name.")
                    self.rules = None
                    return False
        else:
            logger.debug("agent_dict is None")
            self.rules = None
            return False

    def fetch(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=2)
        except requests.exceptions.RequestException as e:
            logger.error(e)
            return None
        else:
            return response.content

    def get_url_route(self, url):
        """Return the full route of a URL (path + query + fragment)

        >>> sp.get_url_route('http://dummy.com/path1/path2?q=something#frag')
        '/path1/path2?q=something#frag'

        """
        p = urlsplit(url)
        path = ''
        query = ''
        fragment = ''

        if len(p.path) > 0:
            path = p.path
        if len(p.query) > 0:
            query = '?' + p.query
        if len(p.fragment) > 0:
            fragment = '#' + p.fragment

        route = path + query + fragment
        return route

    def crawl(self, url, level=1):
        """Fetch content from URL and put soup on queue

        >>> s.crawl("https://github.com", 1)
        >>> soup = CrawlerBase.silo.get()
        >>> soup is not None
        True
        >>> isinstance(soup, BeautifulSoup)
        True

        """

        while level >= 0:
            agent_dict = self.fetch_rules(url)
            self.read_rules(agent_dict)
            if self.rules is not None:
                if self.strict:
                    if self.get_url_route(url) not in self.rules['Allow']:
                        return
                elif not self.strict:
                    if self.get_url_route(url) not in self.rules['Disallow']:
                        # start fetching content
                        html = self.fetch(url)
                        soup = BeautifulSoup(html, 'lxml')
                        if soup is not None:
                            # save the first-level soup to base
                            self.stash(soup)
                            # and go on recursing into each link
                            if len(soup.find_all('a')) > 0:
                                for a in soup.find_all('a'):
                                    if len(a['href']) > 0:
                                        level -= 1
                                        self.crawl(a['href'], level)
                    else:
                        return
                else:
                    raise TypeError('Wrong type for self.strict (must be bool).')

    def stash(self, soup):
        CrawlBase.silo.put(soup)
        gevent.sleep(0)

    def _run(self):
        self.running = True

        while self.running:
            self.crawl(CrawlBase.seed_urls, self.depth)

if __name__ == '__main__':
    import doctest
    doctest.testmod(extraglobs={
        'c': CrawlBase(),
        's': Spider(url='http://digg.com'),
        'sp': Spider(url='http://digg.com', depth=3, org='Looqsie',
                     website='looqsie.com', email='jo@looqsie.com',
                     message='Hello! Thank you.')
    })
