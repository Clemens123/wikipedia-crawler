#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import argparse
import re
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup


DEFAULT_OUTPUT = 'wikipedia_articles/output.txt'
DEFAULT_INTERVAL = 5.0  # interval between requests (seconds)
DEFAULT_ARTICLES_LIMIT = 1  # total number articles to be extrated
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36'

visited_urls = set()  # all urls already visited, to not visit twice
pending_urls = []  # queue


def load_urls(session_file):
    """Resume previous session if any, load visited URLs"""

    try:
        with open(session_file) as fin:
            for line in fin:
                visited_urls.add(line.strip())
    except FileNotFoundError:
        pass


def scrap(base_url, article, output_file, session_file):
    """Represents one request per article"""

    full_url = base_url + article
    try:
        r = requests.get(full_url, headers={'User-Agent': USER_AGENT})
    except requests.exceptions.ConnectionError:
        print("Check your Internet connection")
        input("Press [ENTER] to continue to the next request.")
        return
    if r.status_code not in (200, 404):
        print("Failed to request page (code {})".format(r.status_code))
        input("Press [ENTER] to continue to the next request.")
        return

    soup = BeautifulSoup(r.text, 'html.parser')
    content = soup.find('div', {'id':'mw-content-text'})

    # add new related articles to queue
    # check if are actual articles URL
    for a in content.find_all('a'):
        href = a.get('href')
        if not href:
            continue
        if href[0:6] != '/wiki/':  # allow only article pages
            continue
        elif ':' in href:  # ignore special articles e.g. 'Special:'
            continue
        elif href[-4:] in ".png .jpg .jpeg .svg":  # ignore image files inside articles
            continue
        elif base_url + href in visited_urls:  # already visited
            continue
        if href in pending_urls:  # already added to queue
            continue
        pending_urls.append(href)

    # skip if already added text from this article, as continuing session
    if full_url in visited_urls:
        return

    with open(session_file, 'a') as fout:
        fout.write(full_url + '\n')  # log URL to session file

    visited_urls.add(full_url)

    parenthesis_regex = re.compile('\(.+?\)')  # to remove parenthesis content
    citations_regex = re.compile('\[.+?\]')  # to remove citations, e.g. [1]

    # get plain text from each <p>
    p_list = content.find_all('p')
    with open(output_file, 'a', encoding='utf-8') as fout:
        for p in p_list:
            text = p.get_text().strip()
            text = parenthesis_regex.sub('', text)
            text = citations_regex.sub('', text)
            if text:
                fout.write(text + '\n\n')  # extra line between paragraphs


def main(initial_url, articles_limit, interval, output_file):
    """ Main loop, single thread """

    minutes_estimate = interval * articles_limit / 60
    print("This session will take {:.1f} minute(s) to download {} article(s):".format(minutes_estimate, articles_limit))
    print("\t(Press CTRL+C to pause)\n")
    session_file = "session.txt" # "session_" + output_file
    load_urls(session_file)  # load previous session (if any)
    base_url = '{uri.scheme}://{uri.netloc}'.format(uri=urlparse(initial_url))
    initial_url = initial_url[len(base_url):]
    pending_urls.append(initial_url)

    counter = 0
    while len(pending_urls) > 0:
        try:
            counter += 1
            if counter > articles_limit:
                break
            try:
                next_url = pending_urls.pop(0)
            except IndexError:
                break

            time.sleep(interval)
            article_name = unquote(next_url.replace('/wiki/', '')[:35])
            for c in '\/:*?"<>|':
                article_name = article_name.replace(c, '')
            print("{:<7} {}".format(counter, article_name))
            output_file = "wikipedia_articles/{}.txt".format(article_name)
            scrap(base_url, next_url, output_file, session_file)
        except KeyboardInterrupt:
            input("\n> PAUSED. Press [ENTER] to continue...\n")
            counter -= 1

    print("Finished!")
    sys.exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("initial_url", help="Initial Wikipedia article, e.g. https://en.wikipedia.org/wiki/Biology")
    parser.add_argument("-a", "--articles", nargs='?', default=DEFAULT_ARTICLES_LIMIT, type=int, help="Total number of articles")
    parser.add_argument("-i", "--interval", nargs='?', default=DEFAULT_INTERVAL, type=float, help="Interval between requests")
    parser.add_argument("-o", "--output", nargs='?', default=DEFAULT_OUTPUT, help="File output")
    args = parser.parse_args()
    main(args.initial_url, args.articles, args.interval, args.output)
