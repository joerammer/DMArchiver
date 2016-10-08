﻿# -*- coding: utf-8 -*-

"""
    Direct Messages Archiver
    
    Usage:
 
    >>> from dmarchiver import Crawler
    >>> crawler = Crawler('CONVERSATION_ID', 'AUTH_TOKEN')
    >>> crawler.crawl()
"""
 
import argparse
import collections
import datetime
from enum import Enum
import lxml.html
from lxml.cssselect import CSSSelector
import os
import re
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import shutil

__all__ = ['Crawler']

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class Conversation(object):
    conversation_id = None
    tweets = collections.OrderedDict()
   
    def __init__(self, conversation_id):
        self.tweets = collections.OrderedDict()
        self.conversation_id = conversation_id
        
    def print_conversation(self):
        items = list(self.tweets.items())
        items.reverse()
        
        for tweet in items:
            if type(tweet[1]).__name__ == 'DirectMessage':
                irc_formatted_date = datetime.datetime.utcfromtimestamp(
                    int(tweet[1].timestamp)).strftime('%Y-%m-%d %H:%M:%S')
                print('[{0}] <{1}> '.format(irc_formatted_date, tweet[1].author), end='')
                for element in tweet[1].elements:
                    print('{0} '.format(element), end='')
                print('\r')
            elif type(tweet[1]).__name__ == 'DMConversationEntry':
                print('[DMConversationEntry] {0}\r'.format(tweet[1]))
    
    def write_conversation(self, filename):
        file_buffer = ''
        
        items = list(self.tweets.items())
        items.reverse()
        
        for tweet in items:
            if type(tweet[1]).__name__ == 'DirectMessage':
                irc_formatted_date = datetime.datetime.utcfromtimestamp(
                    int(tweet[1].timestamp)).strftime('%Y-%m-%d %H:%M:%S')
                file_buffer += '[{0}] <{1}> '.format(irc_formatted_date, tweet[1].author)
                for element in tweet[1].elements:
                    file_buffer += '{0} '.format(element)
                file_buffer += '{0}'.format(os.linesep)
            elif type(tweet[1]).__name__ == 'DMConversationEntry':
                file_buffer += '[DMConversationEntry] {0}\r'.format(tweet[1])
        
        # Convert all '\n' of the buffer to os.linesep
        file_buffer = file_buffer.replace('\n', os.linesep)
        
        with open(filename, "wb") as myfile:
            myfile.write(file_buffer.encode('UTF-8'))

class DMConversationEntry(object):
    tweet_id = ''
    _text = ''
    
    def __init__(self, tweet_id, text):
        self.tweet_id = tweet_id
        self._text = text.strip()
    
    def __str__(self):
        return self._text
         
class DirectMessage(object):

    tweet_id = ''
    timestamp = ''
    author = ''
    elements = []
    
    def __init__(self, tweet_id, timestamp, author):
        self.tweet_id = tweet_id
        self.timestamp = timestamp
        self.author = author

class DirectMessageText(object):
    _text = ''
    
    def __init__(self, text):
        self._text = text
    
    def __str__(self):
        return self._text

class DirectMessageTweet(object):
    _tweet_url = ''
    
    def __init__(self, tweet_url):
        self._tweet_url = tweet_url
    
    def __str__(self):
        return self._tweet_url
        
class DirectMessageCard(object):
    _card_url = ''
    
    def __init__(self, card_url):
        self._card_url = card_url
    
    def __str__(self):
        return self._card_url        

class MediaType(Enum):
    image = 1
    gif = 2
    video = 3
    unknown = 4
        
class DirectMessageMedia(object):
    _media_preview_url = ''
    _media_url = ''
    _media_type = ''

    def __init__(self, media_url, media_preview_url, MediaType):
        self._media_url = media_url
        self._media_preview_url = media_preview_url
        self._media_type = MediaType

    def __repr__(self):
        # Todo
        return "{0}('{1}','{2}')".format(
            self.__class__.__name__,
            self._media_url,
            self._media_preview_url)

    def __str__(self):
        if self._media_preview_url != '':
            return '[Media-{0}] {1} [Media-preview] {2}'.format(self._media_type.name, self._media_url, self._media_preview_url)
        else:
            return '[Media-{0}] {1}'.format(self._media_type.name, self._media_url)


class Crawler(object):
    _twitter_base_url = 'https://twitter.com'
    _url = 'https://twitter.com/messages/with/conversation'
    _headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:47.0) Gecko/20100101 Firefox/47.0',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'}
    
    def __init__(self, conversation_id, auth_token):      
        self.conversation_id = conversation_id
        self._auth_token = auth_token
        self._payload = {'id': self.conversation_id}
        self._cookies = {
            'auth_token': self._auth_token}

    def _extract_dm_text_url(self, element, expanding_mode='only_expanded'):
        raw_url = ''
        if expanding_mode == 'only_expanded':
            raw_url = element.get('data-expanded-url')
        elif expanding_mode == 'only_short':
            raw_url = element.get('href')
        elif expanding_mode == 'short_and_expanded':
            raw_url = '{0} [{1}]'.format(element.get(
                'href'), element.get('data-expanded-url'))
        return raw_url

    def _extract_dm_text_hashtag(self, element):
        raw_hashtag = element.text_content()
        if element.tail is not None:
            raw_hashtag += element.tail
        return raw_hashtag

    def _extract_dm_text_atreply(self, element):
        raw_atreply = element.text_content()
        if element.tail is not None:
            raw_atreply += element.tail
        return raw_atreply

    # Todo: Implement parsing options
    def _extract_dm_text_emoji(self, element):
        raw_emoji = '[{0}]'.format(element.get('title'))
        if element.tail is not None:
            raw_emoji += element.tail
        return raw_emoji
        
    def _parse_dm_text(self, element):
        dm_text = ''
        text_tweet = element.cssselect("p.tweet-text")[0]
        for text in text_tweet.iter('p', 'a','img'):
            if text.tag == 'a':
                # External link
                if 'twitter-timeline-link' in text.classes:
                    dm_text += self._extract_dm_text_url(text)
                # #hashtag
                elif 'twitter-hashtag' in text.classes:
                    dm_text += self._extract_dm_text_hashtag(text)
                # @identifier
                elif 'twitter-atreply' in text.classes:
                    dm_text += self._extract_dm_text_atreply(text)                 
                else:
                    # Unable to identify the link type, raw HTML output
                    dm_text += lxml.html.tostring(text).decode('UTF-8')
            # Emoji
            elif text.tag == 'img' and 'Emoji' in text.classes:
                    dm_text += self._extract_dm_text_emoji(text)  
            else:
                if text.text is not None:
                    #print('++ Text: ' + text.text)
                    dm_text += text.text
        return DirectMessageText(dm_text)

    def _parse_dm_media(self, element, tweet_id, session, auth_token, download_images, download_gif):
        media_url = ''
        media_preview_url = ''
        media_type = MediaType.unknown
        
        img_url = element.find('.//img')
        gif_url = element.cssselect('div.PlayableMedia--gif')
        video_url = element.cssselect('div.PlayableMedia--video')
        if img_url is not None:
            media_type = MediaType.image
            media_url = img_url.get('data-full-img')
            media_filename_re = re.findall(tweet_id + '/(.+)/(.+)$', media_url)
            media_filename = tweet_id + '-' + \
                media_filename_re[0][0] + '-' + media_filename_re[0][1]
            #print('++ Media: ' + media_url)
            
            if download_images:
                cookies = {'auth_token': auth_token}
                r = session.get(media_url, cookies=cookies, verify=False, stream=True)
                if r.status_code == 200:
                    os.makedirs('images', exist_ok=True)
                    with open('images/' + media_filename, 'wb') as f:
                        r.raw.decode_content = True
                        shutil.copyfileobj(r.raw, f)
        elif len(gif_url) > 0:
            media_type = MediaType.gif
            media_style = gif_url[0].find('div').get('style')
            media_preview_url = re.findall('url\(\'(.*?)\'\)', media_style)[0]
            media_url = media_preview_url.replace(
                'dm_gif_preview', 'dm_gif').replace('.jpg', '.mp4')
            media_filename_re = re.findall('dm_gif/(.+)/(.+)$', media_url)
            media_filename = media_filename_re[0][
                0] + '-' + media_filename_re[0][1]

            if download_gif:
                r = session.get(media_url, verify=False, stream=True)
                if r.status_code == 200:
                    os.makedirs('mp4', exist_ok=True)
                    with open('mp4/' + media_filename, 'wb') as f:
                        r.raw.decode_content = True
                        shutil.copyfileobj(r.raw, f)
        elif len(video_url) > 0:
            media_type = MediaType.video
            media_style = video_url[0].find('div').get('style')
            media_preview_url = re.findall('url\(\'(.*?)\'\)', media_style)[0]
            media_url = 'https://twitter.com/i/videos/dm/' + tweet_id
        else:
            print('Unknown media')

        return DirectMessageMedia(media_url, media_preview_url, media_type)

    def _parse_dm_tweet(self, element):
        tweet_url = ''
        tweet_url = element.cssselect('a.QuoteTweet-link')[0]
        tweet_url = '{0}{1}'.format(
            self._twitter_base_url, tweet_url.get('href'))
        #print('++ Tweet link: ' + self.twitter_base_url + tweet_url.get('href'))
        return DirectMessageTweet(tweet_url)

    def _parse_dm_card(self, element):
        card_url = ''
        card = element.cssselect(
            'div[class^=" card-type-"], div[class*=" card-type-"]')[0]
        card_url = '{0} - Type: {1}'.format(
            card.get('data-card-url'), card.get('data-card-name'))
        #print('++ Card URL: ' + card.get('data-card-url') + ' ' + card.get('data-card-name'))
        return DirectMessageCard(card_url)

    def _process_tweets(self, session, auth_token, tweets, download_images, download_gif):
        conversation_set = collections.OrderedDict()
        
        orderedTweets = sorted(tweets, reverse=True)

        # DirectMessage-message
        # -- DirectMessage-text
        # -- DirectMessage-media
        # -- DirectMessage-tweet
        # -- DirectMessage-card
        
        for tweet_id in orderedTweets:
            dm_author = ''
            irc_formatted_date = ''
            dm_element_text = ''
            value = tweets[tweet_id]
            document = lxml.html.fragment_fromstring(value)
            
            #print('------------------')
            #print('#' + tweet_id)

            dm_container = document.cssselect('div.DirectMessage-container')

            # Generic messages such as "X has join the group" or "The group has
            # been renamed"
            dm_conversation_entry = document.cssselect(
                'div.DMConversationEntry')

            if len(dm_container) > 0:
                dm_avatar = dm_container[0].cssselect('img.DMAvatar-image')[0]
                dm_author = dm_avatar.get('alt')

                #print(dm_author)

                dm_footer = document.cssselect('div.DirectMessage-footer')
                time_stamp = dm_footer[0].cssselect('span._timestamp')[
                    0].get('data-time')

                # DirectMessage-text, div.DirectMessage-media,
                # div.DirectMessage-tweet_id, div.DirectMessage-card...
                dm_elements = document.cssselect(
                    'div.DirectMessage-message > div[class^="DirectMessage-"], div.DirectMessage-message > div[class*=" DirectMessage-"]')

                message = DirectMessage(tweet_id, time_stamp, dm_author)
                
                # Required array cleanup
                message.elements = []

                for dm_element in dm_elements:
                    dm_element_type = dm_element.get('class')
                    if 'DirectMessage-text' in dm_element_type:
                        element_object = self._parse_dm_text(dm_element)
                        message.elements.append(element_object)
                        #print(element_object)
                    elif dm_element_type == 'DirectMessage-media':
                        element_object = self._parse_dm_media(dm_element, tweet_id, session, auth_token, download_images, download_gif)
                        message.elements.append(element_object)
                        #print(element_object)
                    elif dm_element_type == 'DirectMessage-tweet':
                        element_object = self._parse_dm_tweet(dm_element)
                        message.elements.append(element_object)
                        #print(element_object)
                    elif dm_element_type == 'DirectMessage-card':
                        element_object = self._parse_dm_card(dm_element)
                        message.elements.append(element_object)
                        #print(element_object)
                    else:
                        print('Unknown element type')

            elif len(dm_conversation_entry) > 0:
                #print(dm_conversation_entry[0].text)
                dm_element_text = dm_conversation_entry[0].text.strip()
                message = DMConversationEntry(tweet_id, dm_element_text)
                        
            if message is not None:
                conversation_set[tweet_id]  = message
        return conversation_set
    
    def crawl(self, download_images=False, download_gif=False):
        session = requests.Session()
        conversation = Conversation(self.conversation_id)
        processed_tweet_counter = 0
        
        while True:
            r = session.get(
                self._url,
                headers = self._headers,
                cookies = self._cookies,
                params = self._payload,
                verify = False)

            #print(r.text)
            json = r.json()

            if 'max_entry_id' not in json:
                # End of thread
                print('Begin of thread reached')
                break

            #print('max_entry_id: ' + json['max_entry_id'])

            # To call back to make the loop
            #print('min_entry_id: ' + json['min_entry_id'])

            self._payload = {'id': self.conversation_id,
                            'max_entry_id': json['min_entry_id']}

            tweets = json['items']
            
            # Get tweets for the current request
            conversation_set = self._process_tweets(session, self._auth_token, tweets, download_images, download_gif)
                       
            # Append to the whole conversation
            for tweet_id in conversation_set:
                processed_tweet_counter += 1 
                conversation.tweets[tweet_id] = conversation_set[tweet_id]
                print('Processed tweets: {0}\r'.format(processed_tweet_counter), end='')

        print('Total processed tweets: {0}'.format(processed_tweet_counter))
        
        #print('Printing conversation')
        #conversation.print_conversation()
        
        print('Writing conversation')
        conversation.write_conversation('tweets.txt')