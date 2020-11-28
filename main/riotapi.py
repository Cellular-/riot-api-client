import requests as r, json, sqlite3, os, atexit, sys, inspect
from apiresources import Account, Matchlist
from configparser import SafeConfigParser
from customexceptions import *
from datetime import datetime
from enum import Enum

parser = SafeConfigParser()
parser.read('./config/env')

header = {'request_header': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Charset': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://developer.riotgames.com',
                'X-Riot-Token': parser.get('api_resources', 'key')
            }
        }

endpoints = {'summoner': {
                    'account': {'info': 'https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summoner_name}'},
                    'stats': {'match_list': 'https://na1.api.riotgames.com/lol/match/v4/matchlists/by-account/{account_id}'}
                }
            }

class RiotApi():
    def __init__(self):
        pass

    def dict_factory(self, cursor, row):
        results = {}
        for index, col_name in enumerate(cursor.description):
            results[col_name[0]] = row[index]

        return results

    def summoner_store(self, summoner_account):
        id = None

        if not isinstance(summoner_account, Account):
            raise TypeError('An instance of the Account class must be passed in.')

        try:
            conn = sqlite3.connect(parser.get('database', 'full_path'))
            cursor = conn.cursor()

            query = f'''insert into account
                        values (NULL,
                                '%(id)s',
                                '%(accountId)s',
                                '%(puuid)s',
                                '%(name)s',
                                '%(profileIconId)s',
                                '%(revisionDate)s',
                                '%(summonerLevel)d',
                                '{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}')''' % vars(summoner_account)

            cursor.execute(query)
            conn.commit()
            id = cursor.lastrowid
            cursor.close()
        except sqlite3.IntegrityError as error:
            if 'UNIQUE constraint' in str(error):
                print('The name or account id is not unique for\n %s' % summoner_account)
        except sqlite3.OperationalError as error:
            print(error)
        except Exception as error:
            print(error)
        finally:
            return id

    def summoner_query(self, name=None):
        """
        name - summoner's name of interest

        return - response

        raises - ApiError if summoner does not exist
        """
        if not isinstance(name, str):
            raise TypeError("Summoner name must be a string")

        endpoint = endpoints['summoner']['account']['info'].format(summoner_name=name)

        response = r.get(endpoint, headers=header["request_header"])
    
        if response.status_code != 200:
            raise ApiError(endpoint, response.status_code, response.reason)

        return Account(**response.json())

    def summoner_get_account_info(self, name=None):
        if not isinstance(name, str):
            raise TypeError("Summoner name must be a string")

    def summoner_matchlist(self, account_id):
        response = r.get(endpoints['summoner']['stats']['match_list']\
                        .format(account_id=account_id), headers=header["request_header"])

        return response

    def summoner_store_matchlist(self, matchlist):
        try:
            conn = sqlite3.connect(parser.get('database', 'full_path'))
            cursor = conn.cursor()

            query = f'''insert into matchlist
                        values (NULL,
                                '%(platformId)s',
                                '%(gameId)s',
                                '%(champion)d',
                                '%(queue)s',
                                '%(season)d',
                                '%(timestamp)d',
                                '%(role)s',
                                '%(lane)s')'''

            for match in matchlist['matches']:
                cursor.execute(query % match)
                conn.commit()
        except sqlite3.IntegrityError as error:
            print(error)
        except sqlite3.OperationalError as error:
            print(error)
        finally:
            cursor.close()

    def run_cli_tool(self):
        def add_summoner():
            summoner_name = None
            while not summoner_name:
                summoner_name = str(input('Enter a summoner name: '))

            try:
                account = self.summoner_query(name=summoner_name)

                record_id = self.summoner_store(account)
                if record_id:
                    print("Added %s to database with row id %d" % (account.name, record_id))
            except ApiError as error:
                print(error)
            finally:
                record_id = None

        def get_matchlist():
            summoner_name = None
            while not summoner_name:
                summoner_name = str(input('Enter a summoner account ID: '))
            
            try:
                matchlist_data = self.summoner_matchlist(account_id=summoner_name)
                matchlist = Matchlist(**matchlist_data)

                self.summoner_store_matchlist(matchlist.json())
            except Exception as error:
                print(error)

        def get_account_info():
            summoner_name = None
            results = None
            while not summoner_name:
                summoner_name = str(input('Enter a summoner name: '))

            conn = sqlite3.connect(parser.get('database', 'full_path'))
            conn.row_factory = self.dict_factory
            cursor = conn.cursor()

            query = f'''select id, accountId, name, summonerLevel
                        from account 
                        where lower(name) = \'{summoner_name.lower()}\''''

            cursor.execute(query)
            conn.commit()
            account_info = Account(**cursor.fetchone())
            conn.close()

            print('\n')
            print('*' * len(account_info.accountId))
            print("Account information for {}".format(account_info.name))
            print(account_info)
            print('*' * 50)
            print('\n')

        def print_menu():
            menu = 'League of Legends Tool\n' \
                's - Create account record for given summoner name\n' \
                'r - Get summoner account info from database\n' \
                'm - Get summoner matchlist\n' \
                'p - Print menu\n' \
                'q - quit\n' \
                'Select an option: '

            print(menu)

        menu_commands = {'s': add_summoner,
                         'm': get_matchlist,
                         'r': get_account_info,
                         'q': lambda: sys.exit(0),
                         'p': print_menu}

        def is_valid_menu_option(menu_option):
            return menu_option in [command for command in menu_commands.keys()]

        while(True):
            print_menu()
            menu_option = str(input())
            
            while(not is_valid_menu_option(menu_option)):
                menu_option = str(input())
            
            menu_commands[menu_option]()

if __name__ == '__main__':
    from atexit_functions import funcs
    for func in funcs:
        atexit.register(func)

    RiotApi().run_cli_tool()