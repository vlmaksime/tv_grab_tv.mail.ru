#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import xmltv
import argparse
import requests
import os
import re
import configparser

from datetime import datetime, timedelta, date
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
parser.add_argument('--offset', metavar='X', type=int, default=0, help='Start with data for day today plus X days')
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

def log( message, force_quiet=False ):
    if not (args.quiet or force_quiet):
        sys.stdout.write(message.encode('utf-8') + '\n')
        pass

def error(message):
    sys.stderr.write(message.encode('utf-8') + '\n')

class tv_mail_ru():
    def __init__( self ):

        self._version = '0.2.6'
        self._description = 'XMLTV Grabber for tv.mail.ru'
        self._capabilities = ['baseline', 'manualconfig']

        self.base_url = 'https://tv.mail.ru'

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
        config_file = open(self.__get_config_path(args.config_file), "w")

        parser.add_section('general')
        parser.set('general', 'conf_ver', '2')

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
             log('Selected regions: %s' % region_ids)
        else:
            log('The default region will be used')

        parser.add_section('settings')
        parser.set('settings', 'date_delay', '0.3')
        parser.set('settings', 'event_delay', '0.3')
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

        parser.set('settings', 'force_quiet', '0')
        if query_yes_no('Always enable quiet argument? Need for TVHeadend 4.0', 'no') == 'yes':
            parser.set('settings', 'force_quiet', '1')

        parser.write(config_file)
        sys.exit(0)

    def __get_config_path( self, config_file ):
        config_dir = os.path.join(os.path.expanduser('~'), '.xmltv')

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        return os.path.join(config_dir, config_file)

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
                        self.__show_region_list(j['russia'], j['regions'],  u'Россия:')
                        self.__show_region_list(j['other'], j['regions'],   u'Другие города:')
                        region_id = raw_input('Enter region id: ')
                        if region_id:
                            regions += ', ' + region_id
                    else:
                        log('Region not fount')
            enter_region = (query_yes_no('Do you want to add another region?') == 'yes')
        return regions[2:]

    def __show_region_list(self, region_list, regions, title):
        if len(region_list) > 0:
            log(title)
            for region_id in region_list:
                region_name = self.__get_region_name(region_id, regions)
                log('id: %s , name: %s' % (region_id, region_name) )

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

    def get_category( self, genre, title ):

        #01 Movie / Drama
        if genre in [u'криминал',   u'мистика']:
            result = 'Movie'
        elif genre in [u'драма']:
            result = 'Drama'
        elif genre in [u'детективный',  u'детектив',    u'детектив']:
            result = 'Detective'
        elif genre in [u'триллер',  u'боевик']:
            result = 'Thriller'
        elif genre in [u'приключения']:
            result = 'Adventure'
        elif genre in [u'вестерн']:
            result = 'Western'
        elif genre in [u'военный']:
            result = 'War'
        elif genre in [u'фантастика']:
            result = 'Science fiction'
        elif genre in [u'фэнтези']:
            result = 'Fantasy'
        elif genre in [u'ужасы']:
            result = 'Horror'
        elif genre in [u'комедия']:
            result = 'Comedy'
        # elif genre in [u'']:
            # result = 'Soap'
        elif genre in [u'мелодрама']:
            result = 'Melodrama'
        # elif genre in [u'']:
            # result = 'Folkloric'
        # elif genre in [u'']:
            # result = 'Romance'
        # elif genre in [u'']:
            # result = 'Serious'
        # elif genre in [u'']:
            # result = 'Classical'
        # elif genre in [u'']:
            # result = 'Religious'
        elif genre in [u'исторический']:
            result = 'Historical movie'
        elif genre in [u'эротика']:
            result = 'Adult movie'

        #02 News / Current affairs
        elif genre in [u'новостное']:
            result = 'News'
        # elif genre in [u'']:
            # result = 'Current affairs'
        # elif genre in [u'']:
            # result = 'Weather report'
        # elif genre in [u'']:
            # result = 'News magazine'
        elif genre in [u'документальное',   u'документальный']:
            result = 'Documentary'
        # elif genre in [u'']:
            # result = 'Discussion'
        # elif genre in [u'']:
            # result = 'Interview'
        # elif genre in [u'']:
            # result = 'Debate'
        # elif genre in [u'']:
            # result = 'News / Current Affairs'

        #03 Show / Game show
        elif genre in [u'реалити-шоу',  u'юмористическое',  u'скетч-шоу',   u'развлекательное', u'шоу талантов']:
            result = 'Show'
        elif genre in [u'игровое',  u'интеллектуальное']:
            result = 'Game show'
        # elif genre in [u'']:
            # result = 'Quiz'
        # elif genre in [u'']:
            # result = 'Contest'
        # elif genre in [u'']:
            # result = 'Variety show'
        elif genre in [u'ток-шоу']:
            result = 'Talk show'
        # elif genre in [u'']:
            # result = 'Show / Game show'

        #04 Sports
        elif genre in [u'спорт',    u'спортивное']:
            result = 'Sports'
        # elif genre in [u'']:
            # result = 'Special events (Olympic Games, World Cup, etc.)'
        # elif genre in [u'']:
            # result = 'Sports magazines'
        # elif genre in [u'']:
            # result = 'Football'
        # elif genre in [u'']:
            # result = 'Soccer'
        # elif genre in [u'']:
            # result = 'Tennis'
        # elif genre in [u'']:
            # result = 'Squash'
        # elif genre in [u'']:
            # result = 'Team sports (excluding football)'
        # elif genre in [u'']:
            # result = 'Athletics'
        # elif genre in [u'']:
            # result = 'Motor sport'
        # elif genre in [u'']:
            # result = 'Water sport'
        # elif genre in [u'']:
            # result = 'Winter sports'
        # elif genre in [u'']:
            # result = 'Equestrian'
        # elif genre in [u'']:
            # result = 'Martial sports'

        #05 Children's / Youth programs
        elif genre in [u'детское',  u'детский']:
            result = 'Children\'s / Youth programs'
        # elif genre in [u'']:
            # result = 'Pre-school children's programs'
        # elif genre in [u'']:
            # result = 'Entertainment programs for 6 to 14'
        # elif genre in [u'']:
            # result = 'Entertainment programs for 10 to 16'
        # elif genre in [u'']:
            # result = 'Informational'
        # elif genre in [u'']:
            # result = 'Educational'
        # elif genre in [u'']:
            # result = 'School programs'
        elif genre in [u'мультфильмы',  u'аниме']:
            result = 'Cartoons'
        # elif genre in [u'']:
            # result = 'Puppets'

        #06 Music / Ballet / Dance
        elif genre in [u'музыкальный']:
            result = 'Music'
        # elif genre in [u'']:
            # result = 'Ballet'
        # elif genre in [u'']:
            # result = 'Dance'
        # elif genre in [u'']:
            # result = 'Rock'
        # elif genre in [u'']:
            # result = 'Pop'
        # elif genre in [u'']:
            # result = 'Serious music'
        # elif genre in [u'']:
            # result = 'Classical music'
        # elif genre in [u'']:
            # result = 'Folk'
        # elif genre in [u'']:
            # result = 'Traditional music'
        # elif genre in [u'']:
            # result = 'Jazz'
        elif genre in [u'мюзикл',   u'музыкальные']:
            result = 'Musical'
        # elif genre in [u'']:
            # result = 'Opera'
        # elif genre in [u'']:
            # result = 'Ballet'
        # elif genre in [u'']:
            # result = 'Music / Ballet / Dance'

        #07 Arts / Culture (without music)
        # elif genre in [u'']:
            # result = 'Arts'
        # elif genre in [u'']:
            # result = 'Culture (without music)'
        # elif genre in [u'']:
            # result = 'Performing arts'
        # elif genre in [u'']:
            # result = 'Fine arts'
        # elif genre in [u'']:
            # result = 'Religion'
        # elif genre in [u'']:
            # result = 'Popular culture'
        # elif genre in [u'']:
            # result = 'Traditional arts'
        # elif genre in [u'']:
            # result = 'Literature'
        # elif genre in [u'']:
            # result = 'Film'
        # elif genre in [u'']:
            # result = 'Cinema'
        # elif genre in [u'']:
            # result = 'Experimental film'
        # elif genre in [u'']:
            # result = 'Video'
        # elif genre in [u'']:
            # result = 'Broadcasting'
        # elif genre in [u'']:
            # result = 'Press'
        # elif genre in [u'']:
            # result = 'New media'
        # elif genre in [u'']:
            # result = 'Arts magazines'
        # elif genre in [u'']:
            # result = 'Culture magazines'
        elif genre in [u'шоу о моде и красоте']:
            result = 'Fashion'
        # elif genre in [u'']:
            # result = 'Arts / Culture (without music)'

        #08 Social / Political issues / Economics
        elif genre in [u'аналитическое']:
            result = 'Social'
        # elif genre in [u'']:
            # result = 'Political issues'
        # elif genre in [u'']:
            # result = 'Economics'
        # elif genre in [u'']:
            # result = 'Magazines'
        # elif genre in [u'']:
            # result = 'Reports'
        # elif genre in [u'']:
            # result = 'Documentary'
        # elif genre in [u'']:
            # result = 'Economics'
        # elif genre in [u'']:
            # result = 'Social advisory'
        # elif genre in [u'']:
            # result = 'Remarkable people'
        # elif genre in [u'']:
            # result = 'Social / Political issues / Economics'

        #09 Education / Science / Factual topics
        # elif genre in [u'']:
            # result = 'Education'
        elif genre in [u'научно-познавательное']:
            result = 'Science'
        # elif genre in [u'']:
            # result = 'Factual topics'
        # elif genre in [u'']:
            # result = 'Nature'
        # elif genre in [u'']:
            # result = 'Animals'
        # elif genre in [u'']:
            # result = 'Environment'
        # elif genre in [u'']:
            # result = 'Technology'
        # elif genre in [u'']:
            # result = 'Natural sciences'
        # elif genre in [u'']:
            # result = 'Medicine'
        # elif genre in [u'']:
            # result = 'Physiology'
        # elif genre in [u'']:
            # result = 'Psychology'
        # elif genre in [u'']:
            # result = 'Foreign countries'
        # elif genre in [u'']:
            # result = 'Expeditions'
        # elif genre in [u'']:
            # result = 'Social'
        # elif genre in [u'']:
            # result = 'Spiritual sciences'
        # elif genre in [u'']:
            # result = 'Further education'
        # elif genre in [u'']:
            # result = 'Languages'
        # elif genre in [u'']:
            # result = 'Education / Science / Factual topics'

        #10 Leisure hobbies
        # elif genre in [u'']:
            # result = 'Leisure hobbies'
        elif genre in [u'шоу о путешествиях',   u'приключенческое']:
            result = 'Tourism / Travel'
        # elif genre in [u'']:
            # result = 'Handicraft'
        # elif genre in [u'']:
            # result = 'Motoring'
        elif genre in [u'шоу о здоровье']:
            result = 'Fitness and health'
        elif genre in [u'кулинарное']:
            result = 'Cooking'
        # elif genre in [u'']:
            # result = 'Advertisement / Shopping'
        # elif genre in [u'']:
            # result = 'Gardening'
        # elif genre in [u'']:
            # result = 'Leisure hobbies'

        elif genre in [u'семейный', u'короткометражный',    u'биография']:
            result = ''
        else:
            result = ''
            error('unknown genre "%s" at "%s" ' % (genre, title) )
        return result

    def get_channel_prefix(self, j):
        prefix = ''
        for value in j['form']['channel_type']['values']:
            if value['value'] == 'all':
                prefix = '%s-' % (value['url'].replace('/',''))
        return prefix

    def __get_url_data( self, url, params='' ):
        count = 0
        max_count = 5
        read_delay = 0.5
        while count < max_count:
            r = self.s.get(url, params=params)
            # error('Read code %s, url: %s' % (r.status_code, r.url))
            if r.status_code == requests.codes.ok:
                return r

            count += 1
            sleep(read_delay * count)
        return r

    def __init_session(self):
        self.s = requests.Session()

        self.s.headers.update({'Host': 'tv.mail.ru',
                          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0',
                          'Connection': 'keep-alive',
                          })

    def __web_login( self ):
        url  = 'https://auth.mail.ru/cgi-bin/auth'
        email_parts = self.conf['email'].split('@')
        data = {'Login':         email_parts[0],
                'Domain':        email_parts[1],
                'Password':      self.conf['password'],
                'new_auth_form': '1',
                'saveauth':      '0',
                }
        headers = {'Host': 'auth.mail.ru',
                   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:61.0) Gecko/20100101 Firefox/61.0',
                   }
        r = self.s.post(url, data = data, headers=headers)

        url = 'https://portal.mail.ru/NaviData'
        r = self.s.get(url)
        j = r.json()
        return (j['status'] == 'ok')

    def __web_read_region_cookies( self, region_id ):
        url  = self.base_url
        cookies = {'s':'geo=%s' % region_id}

        r = self.s.get(url, cookies = cookies)

    def main( self ):
        config_file = self.__get_config_path(args.config_file)
        if not os.path.exists(config_file):
            error('Configuration file "%s" not fount' % (config_file))
            sys.exit(1)

        self.conf = self.__read_config(args.config_file)
        self.__init_session()

        self.dates = []
        self.str_director = u'Режиссеры'
        self.str_actors = u'В ролях'
        self.str_guest  = u'Участники'

        if self .__web_login():
            log('Login success', self.conf['force_quiet'])
        else:
            error('Login failure')
            sys.exit(1)

        self.data = {}

        writer = xmltv.Writer()
        for region_id in self.conf['regions']:
            log('Read region_id = %s' % region_id, self.conf['force_quiet'])
            self.__web_read_region_cookies(region_id)
            self.__load_program(region_id)

        for key in self.data.keys():
            channel_info = self.data[key]
            writer.addChannel(channel_info['data'])
        for key in self.data.keys():
            # self.__init_session()
            channel_info = self.data[key]
            region_id = channel_info['data']['region_id']
            for event in channel_info['events']:
                event_id = event.get('event_id')
                if event_id:
                    sleep(self.conf['event_delay'])
                    self.add_event_description(event, event_id, region_id)

                writer.addProgramme(event)

        writer.write(args.output, pretty_print=True)

    def __load_program( self, region_id ):
        url = 'https://tv.mail.ru/ajax/index/'
        params = 'appearance=list&channel_type=favorite&period=all'

        region_info = '&region_id=%s' % region_id

        log('Read channels', self.conf['force_quiet'])

        read_dates = True

        program_date = date.today() + timedelta(days=args.offset)

        days_count = 0
        while read_dates and (args.days == 0 or days_count < args.days):
            # read_dates = False

            ex_channels = []
            read_channels = True
            while read_channels:
                sleep(self.conf['date_delay'])

                cur_date = program_date.strftime('%Y-%m-%d')
                r = self.__get_url_data(url, params = params + region_info + self.__ex_channels(ex_channels) + '&date=%s' % (cur_date))

                if r.status_code != requests.codes.ok:
                    read_channels = False
                    # sys.exit(1)
                    continue

                j = r.json()

                for value in j['form']['channel_type']['values']:
                    if (value['value'] == 'favorite') and (value['count'] < 1):
                        read_channels = False
                        read_dates = False
                        break

                cur_date_info = self.__get_date_info(cur_date, j['form']['date']['values'])

                if not cur_date_info or cur_date_info.get('checked') != 1:
                    read_channels = False
                    read_dates = False
                    break

                today    = (cur_date_info.get('today') == 1)
                tomorrow = (cur_date_info.get('tomorrow') == 1)

                cur_offset = j['current_offset'] / 60
                sign = '+'
                if cur_offset < 0:
                    sign = '-'
                    cur_offset = -cur_offset
                offset = '%s%02d%02d' %(sign, cur_offset//60, cur_offset%60)
#                if cur_date_info.get('passed') or (date_count >= args.days and args.days != 0):
#                    continue

                channel_prefix = self.get_channel_prefix(j)

                for schedule in j['schedule']:
                    channel = schedule['channel']

                    if not channel['id'] in ex_channels:
                        ex_channels.append(channel['id'])

                    log('date = %s, chanel_id = %4s, name = %s' % (cur_date, channel['id'], channel['name']), self.conf['force_quiet'])

                    channel_id = channel_prefix + channel['id']

                    channel_info = self.data.get(channel_id)
                    if not channel_info:
                        channel_data = {'display-name': [(channel['name'], 'ru')],
                                        'id': channel_id,
                                        'url': [self.base_url + channel['url']],
                                        'region_id': region_id,
                                        }
                        if channel['pic_url']:
                            channel_data['icon'] = [{'src': self.base_url + channel['pic_url']}]

                        channel_info = {'data': channel_data,
                                        'events': []
                                        }

                    if not j['pager']['next']['url']:
                        read_channels = False

                    events  = schedule['event']

                    if not events:
                        continue

                    prev_time = datetime.strptime(cur_date, '%Y-%m-%d')
                    next_day = prev_time + timedelta(days=1)
                    for event in events:
                        start_time = datetime.strptime(cur_date + ' ' + event['start'], '%Y-%m-%d %H:%M')
                        if start_time > prev_time:
                            prev_time = start_time
                        else:
                            start_time = start_time + timedelta(days=1)

                        if channel_info['events']:
                            channel_info['events'][-1]['stop'] = start_time.strftime("%Y%m%d%H%M%S ") + offset

                        log('event_id = %s, name = %s' % (event['id'], event['name']), self.conf['force_quiet'])

                        event_data = {'channel'   : channel_prefix + event['channel_id'],
                                      'title'     : [(event['name'], 'ru')],
                                      'start'     : start_time.strftime("%Y%m%d%H%M%S ") + offset,
                                      'stop'      : next_day.strftime("%Y%m%d%H%M%S ") + offset
                                      }
                        #episode
                        episode_num = '{}'.format(event.get('episode_num'))
                        if episode_num and episode_num != '0':
                            event_data['episode-num'] = [(episode_num, 'onscreen')]

                        #sub-title
                        episode_title = event.get('episode_title')
                        if episode_title:
                            event_data['sub-title'] = [(event['episode_title'], 'ru')]

                        if self.conf['des_week'] or today and self.conf['des_today'] or tomorrow and self.conf['des_tomorrow']:
                            event_data['event_id'] = event['id']
                        channel_info['events'].append(event_data)

                    self.data[channel_id] = channel_info

            days_count += 1
            program_date = program_date + timedelta(days=1)


    def __get_date_info( self, cur_date, dates):
        for date in dates:
            if date['value'] == cur_date:
                return date

    def __ex_channels( self, ex_channels):
        return ''.join(['&ex=%s' % channel_id for channel_id in ex_channels])

    def get_event_info( self, event_id, region_id ):
        url = 'https://tv.mail.ru/ajax/event/'
        params = {'id': event_id,
                  'region_id': region_id}
        r = self.__get_url_data(url, params=params)
       # r = requests.get(url, params=params)
       # error('Read code %s, url: %s' % (r.status_code, r.url))
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
                categories = []
                for genre in genres:
                    #event_data['category'].append((genre['title'], 'ru'))
                    category = self.get_category( genre['title'], tv_event['name'])
                    if category and not category in categories:
                        categories.append(category)
                for category in categories:
                    event_data['category'].append((category, ''))

            #rating
            age_restrict = '{}'.format(tv_event.get('age_restrict'))
            if age_restrict:
                event_data['rating'] = [{ 'system': u'MPAA', 'value': self.MPAA(age_restrict)},
                                        { 'system': u'RARS', 'value': self.RARS(age_restrict)}]

            #desc
            descr = tv_event.get('descr')
            if descr:
                #descr = self.h.handle(descr)
                descr = self.__remove_html(descr)
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

# {age_restrict:{1:0,2:0,3:6,4:12,5:16,6:18},mpaa:{13:"PG-13",17:"NC-17",G:"G",PG:"PG",R:"R"}}
    def RARS( self, age_restrict ):
        if age_restrict in ['1, 2'] :
            return '0+'
        elif age_restrict == '3':
            return '6+'
        elif age_restrict == '4':
            return '12+'
        elif age_restrict == '5':
            return '16+'
        elif age_restrict == '6':
            return '18+'
        else:
            return ''

    def MPAA( self, age_restrict ):
        if age_restrict in ['1, 2'] :
            return 'G'
        elif age_restrict == '3':
            return 'PG'
        elif age_restrict == '4':
            return 'PG-13'
        elif age_restrict == '5':
            return 'R'
        elif age_restrict == '6':
            return 'NC-17'
        else:
            return ''

    def __read_config( self, config_file ):
        parser = configparser.SafeConfigParser()
        parser.read(self.__get_config_path(config_file))

        conf = {}
        conf_ver = parser.getint('general', 'conf_ver')

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

        if conf_ver >= 2:
            conf['force_quiet'] = parser.getboolean('settings', 'force_quiet')
        else:
            conf['force_quiet'] = False

        return conf

    def __remove_html( self, text ):
        result = text
        result = result.replace(u'&nbsp;',      u' ')
        result = result.replace(u'&pound;',     u'£')
        result = result.replace(u'&euro;',      u'€')
        result = result.replace(u'&para;',      u'¶')
        result = result.replace(u'&sect;',      u'§')
        result = result.replace(u'&copy;',      u'©')
        result = result.replace(u'&reg;',       u'®')
        result = result.replace(u'&trade;',     u'™')
        result = result.replace(u'&deg;',       u'°')
        result = result.replace(u'&plusmn;',    u'±')
        result = result.replace(u'&frac14;',    u'¼')
        result = result.replace(u'&frac12;',    u'½')
        result = result.replace(u'&frac34;',    u'¾')
        result = result.replace(u'&times;',     u'×')
        result = result.replace(u'&divide;',    u'÷')
        result = result.replace(u'&fnof;',      u'ƒ')
        result = result.replace(u'&Alpha;',     u'Α')
        result = result.replace(u'&Beta;',      u'Β')
        result = result.replace(u'&Gamma;',     u'Γ')
        result = result.replace(u'&Delta;',     u'Δ')
        result = result.replace(u'&Epsilon;',   u'Ε')
        result = result.replace(u'&Zeta;',      u'Ζ')
        result = result.replace(u'&Eta;',       u'Η')
        result = result.replace(u'&Theta;',     u'Θ')
        result = result.replace(u'&Iota;',      u'Ι')
        result = result.replace(u'&Kappa;',     u'Κ')
        result = result.replace(u'&Lambda;',    u'Λ')
        result = result.replace(u'&Mu;',        u'Μ')
        result = result.replace(u'&Nu;',        u'Ν')
        result = result.replace(u'&Xi;',        u'Ξ')
        result = result.replace(u'&Omicron;',   u'Ο')
        result = result.replace(u'&Pi;',        u'Π')
        result = result.replace(u'&Rho;',       u'Ρ')
        result = result.replace(u'&Sigma;',     u'Σ')
        result = result.replace(u'&Tau;',       u'Τ')
        result = result.replace(u'&Upsilon;',   u'Υ')
        result = result.replace(u'&Phi;',       u'Φ')
        result = result.replace(u'&Chi;',       u'Χ')
        result = result.replace(u'&Psi;',       u'Ψ')
        result = result.replace(u'&Omega;',     u'Ω')
        result = result.replace(u'&alpha;',     u'α')
        result = result.replace(u'&beta;',      u'β')
        result = result.replace(u'&gamma;',     u'γ')
        result = result.replace(u'&delta;',     u'δ')
        result = result.replace(u'&epsilon;',   u'ε')
        result = result.replace(u'&zeta;',      u'ζ')
        result = result.replace(u'&eta;',       u'η')
        result = result.replace(u'&theta;',     u'θ')
        result = result.replace(u'&iota;',      u'ι')
        result = result.replace(u'&kappa;',     u'κ')
        result = result.replace(u'&lambda;',    u'λ')
        result = result.replace(u'&mu;',        u'μ')
        result = result.replace(u'&nu;',        u'ν')
        result = result.replace(u'&xi;',        u'ξ')
        result = result.replace(u'&omicron;',   u'ο')
        result = result.replace(u'&pi;',        u'π')
        result = result.replace(u'&rho;',       u'ρ')
        result = result.replace(u'&sigmaf;',    u'ς')
        result = result.replace(u'&sigma;',     u'σ')
        result = result.replace(u'&tau;',       u'τ')
        result = result.replace(u'&upsilon;',   u'υ')
        result = result.replace(u'&phi;',       u'φ')
        result = result.replace(u'&chi;',       u'χ')
        result = result.replace(u'&psi;',       u'ψ')
        result = result.replace(u'&omega;',     u'ω')
        result = result.replace(u'&larr;',      u'←')
        result = result.replace(u'&uarr;',      u'↑')
        result = result.replace(u'&rarr;',      u'→')
        result = result.replace(u'&darr;',      u'↓')
        result = result.replace(u'&harr;',      u'↔')
        result = result.replace(u'&spades;',    u'♠')
        result = result.replace(u'&clubs;',     u'♣')
        result = result.replace(u'&hearts;',    u'♥')
        result = result.replace(u'&diams;',     u'♦')
        result = result.replace(u'&quot;',      u'"')
        result = result.replace(u'&amp;',       u'&')
        result = result.replace(u'&lt;',        u'<')
        result = result.replace(u'&gt;',        u'>')
        result = result.replace(u'&hellip;',    u'…')
        result = result.replace(u'&prime;',     u'′')
        result = result.replace(u'&Prime;',     u'″')
        result = result.replace(u'&ndash;',     u'–')
        result = result.replace(u'&mdash;',     u'—')
        result = result.replace(u'&lsquo;',     u'‘')
        result = result.replace(u'&rsquo;',     u'’')
        result = result.replace(u'&sbquo;',     u'‚')
        result = result.replace(u'&ldquo;',     u'“')
        result = result.replace(u'&rdquo;',     u'”')
        result = result.replace(u'&bdquo;',     u'„')
        result = result.replace(u'&laquo;',     u'«')
        result = result.replace(u'&raquo;',     u'»')

        result = result.replace(u'<br>',    u'\n')

        return re.sub('<[^<]+?>', '', result)


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
