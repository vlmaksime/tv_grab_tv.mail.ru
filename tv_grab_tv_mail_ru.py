#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import xmltv
import argparse
import requests
import os
import configparser

from datetime import datetime, timedelta
from time import sleep

parser = argparse.ArgumentParser(description='XMLTV Grabber for tv.mail.ru')

#grabber description
group = parser.add_mutually_exclusive_group()
group.add_argument('-c', '--capabilities', action='store_true', help='List the capabilities that a grabber supports')
group.add_argument('-d', '--description', action='store_true', help='Print description')
group.add_argument('-v', '--version', action='store_true', help='Print version')

#baseline
parser.add_argument('--quiet', action='store_true', help='Suppress all progress information')
parser.add_argument('--output', metavar='FILENAME', nargs='?', type=argparse.FileType('w'), default=sys.stdout, help='Redirect the xmltv output to the specified file. Otherwise output goes to stdout')
parser.add_argument('--days', metavar='X', type=int, default=0, help='Supply data for X days')
#parser.add_argument('--offset', metavar='X', type=int, default=0, help='Start with data for day today plus X days')
parser.add_argument('--config-file', metavar='FILENAME', default='tv_mail_ru.conf', help='The grabber shall read all configuration data from the specified file')
#manualconfig
parser.add_argument('--configure', action='store_true', help='Allow the user to answer questions regarding the operation of the grabber')

args = parser.parse_args()

def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.
    
    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    """
    valid = {"yes":"yes",   "y":"yes",  "ye":"yes",
             "no":"no",     "n":"no"}
    if default == None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while 1:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return default
        elif choice in valid.keys():
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "\
                             "(or 'y' or 'n').\n")

def log(message):
    if not args.quiet:
        # print(message)
        pass
        
class tv_mail_ru():
    def __init__( self ):

        self._version = '0.1.1'
        self._description = 'tv.mail.ru xmltv grabber'
        self._capabilities = ['baseline', 'manualconfig']

        self.base_url = 'https://tv.mail.ru/'

    def capabilities( self ):
        firts = True
        for capabiliti in self._capabilities:
            if not firts: sys.stdout.write('\n')
            if firts: firts = False
            sys.stdout.write(capabiliti)
        sys.exit(0)

    def description( self ):
        sys.stdout.write(self._description)
        sys.exit(0)

    def version( self ):
        sys.stdout.write(self._version)
        sys.exit(0)

    def configure( self ):
        parser = configparser.SafeConfigParser()
        config_file = open(self.__get_config_path(), "w")

        parser.add_section('general')
        parser.set('general', 'conf_ver', '1')

        parser.add_section('account')

        email = raw_input('Enter e-mail: ')
        parser.set('account', 'email', email)

        password = raw_input('Enter password: ')
        parser.set('account', 'password', password)

        if query_yes_no('Do you want to configure the list of regions manually?') == 'yes':
            region_ids = self.__select_regions()
        else:
            region_ids = ''
            
        if region_ids:
            print('Selected regions: %s' % region_ids)
        else:
            print('The default region will be used')

        parser.add_section('settings')
        parser.set('settings', 'date_delay', '0')
        parser.set('settings', 'event_delay', '0.1')
        parser.set('settings', 'region_ids', region_ids)

        parser.set('settings', 'des_week', '0')
        parser.set('settings', 'des_today', '0')
        parser.set('settings', 'des_tommorow', '0')
        if query_yes_no('Get the description of the program for a week?') == 'yes':
            parser.set('settings', 'des_week', '1')
        else:
            if query_yes_no('Get the program description for today?') == 'yes':
                parser.set('settings', 'des_today', '1')
            if query_yes_no('Get the description of the program for tomorrow?') == 'yes':
                parser.set('settings', 'des_tommorow', '1')
        
        parser.write(config_file)
        sys.exit(0)

    def __get_config_path( self ):
        config_dir = os.path.join(os.path.expanduser( '~'), '.xmltv')

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        config_file = (os.path.join(config_dir, args.config_file))
        
        return config_file

    def __select_regions(self):
        url = 'https://portal.mail.ru/RegionSuggest'
        self.__init_session()

        enter_region = True
        regions = ''
        
        while enter_region:
            query = raw_input('Enter region name: ')
            if query:
                r = self.__get_url_data(url, {'q': query})
                if r.status_code == requests.codes.ok:
                    j = r.json()
                    if int(j['regionsCount']) > 0:
                        self.__show_region_list(j['russia'], j['regions'], u'Россия:')
                        self.__show_region_list(j['other'], j['regions'], u'Другие города:')
                        region_id = raw_input('Enter region id: ')
                        if region_id:
                            regions += ', ' + region_id
                    else:
                        print('Region not fount')
            enter_region = (query_yes_no('Do you want to add another region?') == 'yes')
        return regions[2:]
            
    def __show_region_list(self, region_list, regions, title):
        if len(region_list) > 0:
            print(title)
            for region_id in region_list:
                region_name = self.__get_region_name(region_id, regions)
                print('id: %s , name: %s' % (region_id, region_name) ) 
        
    def __get_region_name( self, region_id, regions ):
        region_info = regions.get(region_id)
        region_name = region_info.get('cityName')
        
        parents_name = ''
        
        parent_info = regions.get(region_info['parentId'])
        while parent_info:
            if parent_info['regionName']:
                parents_name += ', ' + parent_info['regionName']
            parent_info = regions.get(parent_info['parentId'])
        parents_name = parents_name[2:]
        
        if parents_name:
            region_name = '%s (%s)' %(region_name, parents_name)

        return region_name
    
    def get_category( self, genre ):

        if genre == u'драма':
            result = "Drama"
        elif genre == u'приключения':
            result = "Adventure"
        elif genre == u'мелодрама':
            result = "Melodrama"
        elif genre == u'триллер':
            result = "Thriller"
        elif genre == u'детективный':
            result = "Detective"
        elif genre == u'семейный':
            result = "Movie"
        elif genre == u'комедия':
            result = "Comedy"
        elif genre == u'военный':
            result = "War"
        elif genre == u'детский':
            result = "Children's / Youth programs"
        elif genre == u'документальное':
            result = "Documentary"
        elif genre == u'фантастика':
            result = "Science fiction"
        elif genre == u'фэнтези':
            result = "Fantasy"

        # elif genre == u'':
            # result = "News / Current affairs"
        # elif genre == u'':
            # result = "Show / Games"
        # elif genre == u'':
            # result = "Sports"
        # elif genre == u'':
            # result = "Music"
        # elif genre == u'':
            # result = "Art / Culture"
        # elif genre == u'':
            # result = "Social / Political issues / Economics"
        # elif genre == u'':
            # result = "Leisure hobbies"
        # elif genre == u'':
            # result = "Special characteristics"
        else:
            result = genre
            log('uncnown genre %s ' % genre)
        return result

    def __get_channels( self, region_id ):
        url = 'https://tv.mail.ru/ajax/index/'
        params = 'appearance=list&channel_type=favorite&period=now'

        ex_channels = ''
        region_info = '&region_id=%s' % region_id

        log('Read channels')

        read_channels = True
        while read_channels:
            r = self.__get_url_data(url, params=params+region_info+ex_channels)

            if r.status_code != requests.codes.ok:
                read_channels = False
                sys.exit(1)
                continue

            j = r.json()
            channel_prefix = self.get_channel_prefix(j)

            if not self.dates:
                self.dates = j['form']['date']['values']

            for schedule in j['schedule']:
                channel = schedule['channel']

                ex_channels = ex_channels + '&ex=%s' % channel['id']
                log('chanel_id = %5s, name = %s' % (channel['id'], channel['name']))

                channel_data = {'display-name': [(channel['name'], 'ru')],
                                'id': channel_prefix + channel['id'],
                                'url': [self.base_url + channel['url']],
                               }
                if channel['pic_url']:
                    channel_data['icon'] = [{'src': self.base_url + channel['pic_url']}]

                yield channel_data

            if not j['pager']['next']['url']:
                read_channels = False

    def get_channel_prefix(self, j):
        prefix = ''
        for value in j['form']['channel_type']['values']:
            if value['value'] == 'all':
                prefix = '%s-' % (value['url'].replace('/',''))
        return prefix

    def __get_url_data( self, url, params='' ):
        count = 0
        max_count = 10
        read_delay = 1.5
        while count < max_count:
            r = self.s.get(url, params=params)
            if r.status_code == requests.codes.ok:
                return r

            count += 1
            sleep(read_delay)
        return r

    def __get_events( self, region_id ):
        url = 'https://tv.mail.ru/ajax/index/'
        params = 'appearance=list&channel_type=favorite&period=all'
        ex_channels = ''

        region_info = '&region_id=%s' % region_id
        #channel_prefix = '%s-' % region['title']

        log('Read events')

        read_channels = True
        while read_channels:
            first_date = True
            new_ex_channels = ''

            last_evets = {}
            date_count = 0
            for date in self.dates:
                cur_date = date['value']

                sleep(self.conf['date_delay'])

                today = (date.get('today') == 1)
                tomorrow = (date.get('tomorrow') == 1)

                if date.get('passed') or (date_count >= args.days and args.days != 0):
                    continue

                date_count += 1

                r = self.__get_url_data(url, params=params+region_info+ex_channels+'&date=%s' % (cur_date))
                if r.status_code != requests.codes.ok:
                    read_channels = False
                    continue

                j = r.json()
                channel_prefix = self.get_channel_prefix(j)

                if first_date and not j['pager']['next']['url']:
                    read_channels = False

                cur_offset = j['current_offset'] / 60
                sign = '+'
                if cur_offset < 0:
                    sign = '-'
                    cur_offset = -cur_offset
                offset = '%s%02d%02d' %(sign, cur_offset//60, cur_offset%60)

                for schedule in j['schedule']:
                    events  = schedule['event']

                    channel_id = schedule['channel']['id']

                    log('chanel_id = %5s, name = %s' % (schedule['channel']['id'], schedule['channel']['name']))

                    if first_date:
                        new_ex_channels = new_ex_channels + '&ex=%s' % channel_id

                    prev_time = datetime.strptime(cur_date, '%Y-%m-%d')
                    next_day = prev_time + timedelta(days=1)
                    for event in events:
                        start_time = datetime.strptime(cur_date + ' ' + event['start'], '%Y-%m-%d %H:%M')
                        if start_time > prev_time:
                            prev_time = start_time
                        else:
                            start_time = start_time + timedelta(days=1)

                        last_evet = last_evets.get(channel_id)
                        if last_evet:
                            last_evet['stop'] = start_time.strftime("%Y%m%d%H%M%S ") + offset
                            yield last_evet

                        log('event_id = %s, name = %s' % (event['id'], event['name']))
                        
                        event_data = {'channel'   : channel_prefix + event['channel_id'],
                                      'title'     : [(event['name'], 'ru')],
                                      'start'     : start_time.strftime("%Y%m%d%H%M%S ") + offset,
                                      'stop'      : next_day.strftime("%Y%m%d%H%M%S ") + offset
                                      }
                        #episode
                        episode_num = event.get('episode_num')
                        if episode_num and episode_num != '0':
                            event_data['episode-num'] = [(episode_num, 'onscreen')]

                        #sub-title
                        episode_title = event.get('episode_title')
                        if episode_title:
                            event_data['sub-title'] = [(event['episode_title'], 'ru')]


                        if self.conf['des_week'] or today and self.conf['des_today'] or tomorrow and self.conf['des_tomorrow']:
                            sleep(self.conf['event_delay'])
                            self.add_event_description(event_data, event['id'], region_id)
                        last_evets[channel_id] = event_data

                first_date = False

            ex_channels = ex_channels + new_ex_channels
            for key in last_evets.keys():
                last_evet = last_evets.get(key)
                if last_evet:
                    yield last_evet

    def __init_session(self):
        self.s = requests.Session()

        self.s.headers.update({'Host': 'tv.mail.ru',
                          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0',
                          'Connection': 'keep-alive',
                          })

    def __web_login( self ):
        url  = 'https://auth.mail.ru/cgi-bin/auth'
        data = {'Login':         self.conf['email'],
                'Password':      self.conf['password'],
                'new_auth_form': '1',
                'saveauth':      '0',
                }


        self.s.post(url, data = data)
        
        url = 'https://portal.mail.ru/NaviData'
        r = self.s.get(url)
        j = r.json()
        return (j['status'] == 'ok')
    
    def __web_read_region_cookies( self, region_id ):
        url  = self.base_url
        cookies = {'s':'geo=%s' % region_id}

        r = self.s.get(url, cookies = cookies)
    
    def main( self ):
    
        self.conf = self.__read_config(args.config_file)
        self.__init_session()
 
        self.dates = []
        self.str_director = u'Режиссеры'
        self.str_actors = u'В ролях'
        self.str_guest  = u'Участники'
        
        if self .__web_login():
            log('Login failure')
        else:
            sys.stderr.write('Login failure')
            sys.exit(1)
        
        writer = xmltv.Writer()
        for region_id in self.conf['regions']:
            log('Read region_id = %s' % region_id)

            self.__web_read_region_cookies(region_id)
            
            for channel in self.__get_channels(region_id):
                writer.addChannel(channel)
            for program in self.__get_events(region_id):
                writer.addProgramme(program)
            
        writer.write(args.output, pretty_print=True)

    def get_event_info( self, event_id, region_id ):
        url = 'https://tv.mail.ru/ajax/event/'
        params = {'id': event_id,
                  'region_id': region_id}
        r = self.__get_url_data(url, params=params)
        if r.status_code == requests.codes.ok:
            return r.json()
        else:
            return None

    def add_event_description( self, event_data, event_id, region_id ):
        event_info = self.get_event_info( event_id, region_id )
        if event_info:

            tv_event = event_info.get('tv_event')
            if not tv_event:
                return

            #icon
            tv_gallery = tv_event.get('tv_gallery')
            if tv_gallery:
                items = tv_gallery.get('items')
                if items:
                    event_data['icon'] = [{'src': items[0]['original']['src']}]

            # if layout:
                # image = layout['og']['image']
                # event_data['icon'] = [{'src': str(image['src'])}]

            #country
            country_list = tv_event.get('country')
            if country_list:
                event_data['country'] = []
                for country in country_list:
                    event_data['country'].append((country['title'], 'ru'))

            #credits
            participants = tv_event.get('participants')
            if participants:
                event_data['credits'] = {}
                for participant in tv_event['participants']:
                    if participant['title'] == self.str_director:
                        credits_title = 'director'
                    elif participant['title'] == self.str_actors:
                        credits_title = 'actor'
                    elif participant['title'] == self.str_guest:
                        credits_title = 'guest'
                    else:
                        continue
                    event_data['credits'][credits_title] = []
                    for person in participant['persons']:
                        event_data['credits'][credits_title].append(person['name'])

            #category
            genres = tv_event.get('genre')
            if genres:
                event_data['category'] = []
                for genre in genres:
                    #event_data['category'].append((genre['title'], 'ru'))
                    event_data['category'].append((self.get_category( genre['title'] ), ''))

            #desc
            descr = tv_event.get('descr')
            if descr:
                #descr = self.h.handle(descr)
                event_data['desc'] = [(descr,'ru')]

            #date
            years = tv_event.get('year')
            if years and len(years):
                event_data['date'] = str(years['title'])


            afisha_event = tv_event.get('afisha_event')
            if afisha_event:
                #url
                event_data['url'] = [afisha_event['url']]

                #star-rating
                rate = afisha_event.get('rate')
                if rate:
                    event_data['star-rating'] = [{'value': '%s / 10' % (rate['val']) }]

    def __read_config( self, config_file ):
        parser = configparser.SafeConfigParser()
        parser.read(self.__get_config_path())
         
        conf = {}
        conf['email'] = parser.get('account', 'email')
        conf['password'] = parser.get('account', 'password')

        conf['date_delay'] = parser.getfloat('settings', 'date_delay')
        conf['event_delay'] = parser.getfloat('settings', 'event_delay')

        region_ids = parser.get('settings', 'region_ids').split(', ')
        if len(region_ids) == 0:
            region_ids.append('')
        conf['regions'] = region_ids

        conf['des_week'] = parser.getboolean('settings', 'des_week')
        conf['des_today'] = parser.getboolean('settings', 'des_today')
        conf['des_tomorrow'] = parser.getboolean('settings', 'des_tommorow')
   
        return conf

if __name__ == "__main__":
    tv_grab = tv_mail_ru()

    if args.capabilities:
        tv_grab.capabilities()
    elif args.description:
        tv_grab.description()
    elif args.version:
        tv_grab.version()
    elif args.configure:
        tv_grab.configure()
    else:
        tv_grab.main()
