from __future__ import print_function

import os
import re
import logging

# Python 3 is urllib.parse
from urlparse import urlsplit
from bs4 import BeautifulSoup

import gevent
from gevent import Greenlet
from gevent.queue import Queue, Empty
from gevent.pool import Group
from gevent import monkey
monkey.patch_all()

import requests
import responses

logger = logging.getLogger('general')

class CrawlBase(object):
    spider_count = 0

    def __init__(self):
        self.group = Group()
        self.queue = Queue()

    def read_seed(self, file='seeds.txt'):
        with open(file) as f:
            for line in f:
                if len(line) > 0 and line != "\n":
                    yield line.strip()
                else:
                    return

    def dispatch(self):
        for url in self.read_seed():
            g = gevent.spawn(Spider, self, url)
            self.group.add(g)

        self.group.join()

    def harvest(self):
        try:
            while True:
                content = self.queue.get(timeout=2)
                print(content)
        except Empty:
            pass

#class Spider(Greenlet):
class Spider(object):
    """Crawler is a worker instance which fetch and crawl the web
       and put the soupified content into the CrawlBase's silo.
    """

    name = 'Charlotte'
    email = None

    def __init__(self, base, url=None, name=name, depth=1, **kwargs):
        """The contructor has a default name 'Charlotte' and depth = 1"""

        self.base     = base
        self._id      = self.base.spider_count
        self.name     = name
        self.seed_url = url
        self.depth    = depth
        self.org      = None
        self.website  = None
        self.email    = None
        self.message  = None
        self.rules    = None
        self.headers  = None

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

        base.spider_count += 1

        #Greenlet.__init__(self)

        self.prepare_headers()
        self.run()

    def prepare_headers(self):
        """Prepare the appropriate headers to send with the requests"""

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

    def crawl(self, url, level=1):
        while level > 0:
            try:
                resp = requests.get(url, timeout=4, headers=self.headers)
            except requests.exceptions.RequestException as e:
                print(e.message)
                continue
            else:
                if resp is not None and resp.status_code == 200:
                    level -= 1
                    soup = BeautifulSoup(resp.content, "lxml")
                    self.stash(soup)

    def stash(self, soup):
        self.base.queue.put(soup)

    def run(self):
        #self.running = True

        while True:
            self.crawl(self.seed_url, self.depth)

if __name__ == '__main__':
    """
    import doctest
    doctest.testmod(extraglobs={
        'c': CrawlBase(),
        's': Spider(url='http://digg.com', base=c),
        'sp': Spider(url='http://digg.com', depth=3, org='Looqsie',
                     website='looqsie.com', email='jo@looqsie.com',
                     message='Hello! Thank you.')
    })
    """
    cb = CrawlBase()
    cb.dispatch()
    cb.harvest()
