from time import sleep

import requests

from .lyricsapi import LyricsAPI


class DeezerAPI(LyricsAPI):

    __instance__ = None

    def __init__(self):
        if DeezerAPI.__instance__ is None:
            DeezerAPI.__instance__ = self
            self.headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/79.0.3945.130 Safari/537.36",
                "Accept-Language": "*"
            }
            self.session = requests.session()
        else:
            raise Exception('API object cannot be initialised more than once.')

    @staticmethod
    def get_instance():
        if not DeezerAPI.__instance__:
            DeezerAPI()
            return DeezerAPI.__instance__
        else:
            return DeezerAPI.__instance__

    @staticmethod
    def as_params(dct):
        return {'params': dct}

    @staticmethod
    def as_args(dct):
        return {'args': dct}

    def call_simple_api(self, entity, query):
        # noinspection PyBroadException
        try:
            response = self.session.get(
                'https://api.deezer.com/{}/{}'.format(entity, query),
                timeout=15,
                headers=self.headers
            )
            response_json = response.json()
            print(response.url)
            print(response_json)
            if 'error' in response_json and len(response_json['error']):
                raise Exception
            return response_json
        except Exception:
            return None

    def call_api(self, call_type, payload=None):
        args = {}
        params = {
            'api_version': '1.0',
            'api_token': 'null' if call_type == 'deezer.getUserData' else self.set_auth(),
            'input': '3',
            'method': call_type
        }
        if payload is not None:
            if 'args' in payload:
                args = payload['args']
            if 'params' in payload:
                params.update(payload['params'])

        # noinspection PyBroadException
        try:
            response = self.session.post(
                "http://www.deezer.com/ajax/gw-light.php",
                params=params,
                timeout=15,
                json=args,
                headers=self.headers
            )
            response_json = response.json()
            print(response.url)
            print(response_json)
            if 'error' in response_json and len(response_json['error']):
                sleep(2)
                return self.call_api(call_type, payload)
            return response_json['results']
        except Exception:
            return None

    def get_user_data(self):
        return self.call_api('deezer.getUserData')

    def set_auth(self, payload=None):
        user_data = self.get_user_data()
        return user_data['checkForm'] if user_data else None

    def search_isrc(self, isrc):
        return self.call_simple_api('track', 'isrc:{}'.format(isrc))

    def search_id(self, track_name):
        pass

    def get_lyrics_id(self, track_id):
        lyrics_raw = self.call_api('song.getLyrics', self.as_args({'sng_id': track_id}))
        if lyrics_raw:
            return self.parse_lyrics(lyrics_raw)
        return lyrics_raw

    def get_lyrics_isrc(self, isrc):
        track_id = self.search_isrc(isrc.replace('-', '')).get('id')
        if track_id:
            return self.get_lyrics_id(track_id)
        return None

    def parse_lyrics(self, lyrics):
        sync_lst = []
        sync = ''
        if 'LYRICS_SYNC_JSON' in lyrics:
            sync_lyrics_json = lyrics["LYRICS_SYNC_JSON"]
            for line, _ in enumerate(sync_lyrics_json):
                if sync_lyrics_json[line]["line"] != "":
                    timestamp = sync_lyrics_json[line]["lrc_timestamp"]
                    milliseconds = int(sync_lyrics_json[line]["milliseconds"])
                    sync_lst.append((sync_lyrics_json[line]["line"], milliseconds))
                else:
                    not_empty_line = line + 1
                    while sync_lyrics_json[not_empty_line]["line"] == "":
                        not_empty_line += 1
                    timestamp = sync_lyrics_json[not_empty_line]["lrc_timestamp"]
                sync += timestamp + sync_lyrics_json[line]["line"] + "\r\n"
            return sync
        return lyrics.get('LYRICS_TEXT')
