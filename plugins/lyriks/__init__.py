from plugins.lyriks.deezerapi import DeezerAPI


if __name__ == '__main__':
    deez_api = DeezerAPI.get_instance()
    print(deez_api.get_lyrics_id('794823922'))
    print(deez_api.get_lyrics_isrc('JPH491605000'))
