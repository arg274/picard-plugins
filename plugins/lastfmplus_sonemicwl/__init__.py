# -*- coding: utf-8 -*-

import re
import traceback
from functools import partial

from PyQt5 import QtCore
from picard.config import BoolOption, IntOption, TextOption
from picard.metadata import register_track_metadata_processor
from picard.ui.options import register_options_page, OptionsPage
from picard.webservice import ratecontrol

from .ui_options_lastfmplus import UiLastfmOptionsPage

PLUGIN_NAME = 'Last.fm.Plus (with Sonemic genre whitelisting)'
PLUGIN_AUTHOR = 'RifRaf, Lukáš Lalinský, voiceinsideyou, Jaakko Perttilä, snobdiggy'
PLUGIN_DESCRIPTION = '''Uses folksonomy tags from Last.fm to<br/>
* Sort music into major and minor genres based on configurable genre "whitelists"<br/>
* Add "mood", "occasion" and other custom categories<br/>
* Add "original release year" and "decade" tags, as well as populate blank dates.'''
PLUGIN_VERSION = "0.16.1.1"
PLUGIN_API_VERSIONS = ["2.0"]

LASTFM_HOST = "ws.audioscrobbler.com"
LASTFM_PORT = 80
LASTFM_PATH = "/2.0/"

# From http://www.last.fm/api/tos, 2011-07-30
# 4.4 (...) You will not make more than 5 requests per originating IP address per second, averaged over a
# 5 minute period, without prior written consent. (...)
ratecontrol.set_minimum_delay((LASTFM_HOST, LASTFM_PORT), 300)

# Cache for Tags to avoid re-requesting tags within same Picard session
_cache = {}
# Keeps track of requests for tags made to webservice API but not yet returned (to avoid re-requesting the same URIs)
_pending_xmlws_requests = {}

# Cache to Find the Genres and other Tags
ALBUM_GENRE = {}
ALBUM_SUBGENRE = {}
ALBUM_COUNTRY = {}
ALBUM_CITY = {}
ALBUM_DECADE = {}
ALBUM_YEAR = {}
ALBUM_OCCASION = {}
ALBUM_CATEGORY = {}
ALBUM_MOOD = {}

# noinspection PyDictCreation
GENRE_FILTER = {}
GENRE_FILTER["_loaded_"] = False
GENRE_FILTER["major"] = ["ambient, blues, classical music, comedy, dance, electronic, experimental, field recordings, "
                         "folk, hip-hop, industrial music, jazz, metal, musical theatre and entertainment, new age, "
                         "pop, psychedelia, punk, r&b, regional music, rock, singer/songwriter, ska, sounds and "
                         "effects, spoken word"]
GENRE_FILTER["minor"] = ["16-bit, 2 tone, 2-step, aak, abstract hip-hop, acid croft, acid house, acid jazz, "
                         "acid rock, acid techno, acid trance, acidcore, acoustic blues, acoustic chicago blues, "
                         "acoustic rock, acoustic texas blues, adult contemporary, afoxé, african folk music, "
                         "african music, afro-cuban jazz, afro-funk, afro-house, afro-jazz, afro-rock, afrobeat, "
                         "afrobeats, aggrotech, ainu folk music, akan music, al jeel, al-maqam al-iraqi, "
                         "albanian folk music, algerian chaabi, alpenrock, alpine folk music, alsatian folk music, "
                         "alt-country, altai traditional music, alternative dance, alternative metal, alternative "
                         "r&b, alternative rock, amami shimauta, ambasse bey, ambient dub, ambient house, "
                         "ambient pop, ambient techno, ambient trance, american folk music, american primitivism, "
                         "americana, anarcho-punk, anasheed, anatolian rock, ancient chinese music, ancient egyptian "
                         "music, ancient greek music, ancient music, ancient roman music, andalusian classical music, "
                         "andalusian folk music, andalusian rock, andean folk music, andean new age, andean rock, "
                         "anti-folk, aor, apala, appalachian folk music, arabesque, arabesque rap, arabic bellydance "
                         "music, arabic classical music, arabic folk music, arabic jazz, arabic music, arabic pop, "
                         "aragonese folk music, armenian church music, armenian folk music, armenian music, "
                         "ars antiqua, ars nova, ars subtilior, art pop, art punk, art rock, assiko, asturian folk "
                         "music, atmospheric black metal, atmospheric drum and bass, atmospheric sludge metal, "
                         "australian folk music, austronesian traditional music, auvergnat folk music, avant-folk, "
                         "avant-garde jazz, avant-garde metal, avant-prog, axé, azerbaijani traditional music, "
                         "bachata, bagad, baggy / madchester, baila, baião, bakersfield sound, balearic beat, "
                         "balitaw, balkan brass band, balkan folk music, balkan music, balkan pop-folk, ballroom, "
                         "balochi traditional music, baltimore club, banda sinaloense, bandas de viento de méxico, "
                         "barbershop, bard music, baroque music, baroque pop, basque folk music, bass house, "
                         "bassline, batak pop, batucada, batuque, beat music, beat poetry, beatdown hardcore, bebop, "
                         "belarusian folk music, bend-skin, benga, bengali folk music, berber music, berlin school, "
                         "bhangra, big band, big beat, big room, biguine, bikutsi, birdsong, bit music, bitpop, "
                         "black ambient, black metal, blackgaze, bleep techno, blue-eyed soul, bluegrass, "
                         "bluegrass gospel, blues rock, bocet, bogino duu, bolero, bolero español, bolero son, bomba, "
                         "bongo flava, boogaloo, boogie, boogie rock, boogie woogie, boom bap, bop, bossa nova, "
                         "bounce, boy band, brass band, brazilian classical music, brazilian music, breakbeat, "
                         "breakbeat hardcore, breakcore, breakstep, brega, breton celtic folk music, breton folk "
                         "music, brill building, britcore, british blues, british dance band, british folk rock, "
                         "british rhythm & blues, britpop, bro-country, broken beat, brostep, brutal death metal, "
                         "brutal prog, bubblegum, bubblegum bass, bubblegum dance, bulawayo jazz, bulgarian folk "
                         "music, bullerengue, burmese classical music, byzantine chant, byzantine music, c-pop, c86, "
                         "cabaret, cabo-zouk, cadence lypso, cadence rampa, cajun, cakewalk, caklempong, calypso, "
                         "cambodian pop, canadian folk music, canadian maritime folk, canarian folk music, "
                         "canción melódica, candombe, candomblé music, cante alentejano, canterbury scene, "
                         "cantillation, canto a lo poeta, canto cardenche, cantonese opera, cantopop, cantu a tenore, "
                         "canzone d'autore, canzone napoletana, cape breton fiddling, cape breton folk music, "
                         "cape jazz, cape verdean music, capoeira music, car audio bass, caribbean folk music, "
                         "caribbean music, carimbó, cariso, carnatic classical music, cartoon music, catalan folk "
                         "music, ccm, celtic folk music, celtic music, celtic new age, celtic punk, celtic rock, "
                         "central african music, chacarera, chachachá, chalga, chamamé, chamber folk, chamber jazz, "
                         "chamber music, chamber pop, champeta, changüí, chanson, chanson alternative, "
                         "chanson réaliste, chanson à texte, chicago blues, chicago house, chicago soul, chicano rap, "
                         "chilena, chillstep, chillwave, chimurenga, chinese classical music, chinese folk music, "
                         "chinese opera, chiptune, chopped and screwed, choral, choro, chotis madrileño, "
                         "christian hip-hop, christian liturgical music, christian rock, chutney, city pop, "
                         "classical crossover, classical marches, classical period, classical waltz, close harmony, "
                         "cloud rap, cocktail, coco, coimbra fado, coladeira, coldwave, colinde, comedy rap, "
                         "comedy rock, comorian music, compas, complextro, concerto, conga, conscious hip-hop, "
                         "contemporary country, contemporary folk, contemporary r&b, cool jazz, coon song, copla, "
                         "coptic music, cornish folk music, corrido, corsican folk music, country, country & irish, "
                         "country blues, country boogie, country gospel, country pop, country rap, country rock, "
                         "country soul, country yodeling, coupé-décalé, cowboy, cowpunk, croatian folk music, "
                         "crossover thrash, crunk, crunkcore, crust punk, csango folk music, cuarteto, "
                         "cuban charanga, cuban music, cuban rumba, cueca, cumbia, cumbia argentina, cumbia mexicana, "
                         "cumbia peruana, cumbia sonidera, cumbia villera, cuplé, currulao, cyber metal, cybergrind, "
                         "czech folk music, d-beat, dabke, dagomba music, dance-pop, dance-punk, dancehall, dang-ak, "
                         "dangdut, dangdut koplo, danish folk music, danmono, dansbandsmusik, dansktop, danzón, "
                         "dark ambient, dark cabaret, dark electro, dark folk, dark jazz, dark psytrance, darkstep, "
                         "death 'n' roll, death doom metal, death industrial, death metal, deathcore, deathgrind, "
                         "deathrock, deathstep, deejay, deep funk, deep house, deep soul, delta blues, denpa, "
                         "depressive black metal, descarga, detroid techno, deutschpunk, deutschrock, dhrupad, "
                         "digital cumbia, digital dancehall, digital hardcore, dimotika, dirty south, disco, "
                         "disco polo, disco rap, dixieland, djanba, djent, doina, doo-wop, doom metal, downtempo, "
                         "dream pop, dream trance, drill, drill and bass, drone, drone metal, drum and bass, "
                         "drumfunk, drumstep, dub, dub poetry, dub techno, dubstep, dubstyle, duma, dunedin sound, "
                         "dungeon synth, duranguense, dutch cabaret, dutch folk music, dutch house, eai, east african "
                         "music, east asian classical music, east asian folk music, east asian music, east coast "
                         "hip-hop, easy listening, ebm, ecm style jazz, electric blues, electric texas blues, "
                         "electro, electro house, electro latino, electro swing, electro-disco, electro-industrial, "
                         "electroacoustic, electroclash, electronic dance music, electropop, electrotango, eleki, "
                         "emo, emo-pop, emocore, english folk music, enka, entechna, entechna laika, estonian folk "
                         "music, ethio-jazz, ethiopian church music, euro house, euro pop, euro-disco, euro-trance, "
                         "eurobeat, eurodance, european folk music, european free jazz, euskal kantagintza berria, "
                         "ewe music, exotica, experimental big band, experimental hip-hop, experimental rock, "
                         "expressionism, extratone, fado, fairy tales, fanfare, faroese folk music, fidget house, "
                         "field hollers, field recordings, fijian music, filin, filmi, finnish folk music, "
                         "finnish tango, flamenco, flamenco jazz, flamenco nuevo, flamenco pop, flashcore, "
                         "flemish folk music, folk baroque, folk metal, folk pop, folk punk, folk rock, folktronica, "
                         "fon music, footwork, forró, forró eletrônico, forró universitário, freak folk, freakbeat, "
                         "free folk, free improvisation, free jazz, freeform, freestyle, freetekno, french caribbean "
                         "music, french folk music, french hip-hop, french house, french pop, french-canadian folk "
                         "music, frenchcore, frevo, fuji, full-on psytrance, funaná, funeral doom metal, fungi, funk, "
                         "funk carioca, funk melody, funk metal, funk ostentação, funk rock, funkot, funktronica, "
                         "funky house, future funk, future garage, future house, futurepop, futurism, g-funk, gabber, "
                         "gaelic psalm, gagaku, gagauz folk music, galician folk music, gamelan, gamelan angklung, "
                         "gamelan degung, gamelan gong kebyar, gamelan jawa, gangsta rap, garage house, garage punk, "
                         "garage rock, garage rock revival, garifuna folk music, gascon folk music, genge, "
                         "georgian folk music, german folk music, ghazal, ghetto house, ghettotech, girl group, "
                         "glam metal, glam punk, glam rock, glitch, glitch hop, glitch pop, gnawa, go-go, goa trance, "
                         "gondang, goombay, goral music, goregrind, gospel, gothic country, gothic metal, "
                         "gothic rock, gqom, grebo, greek folk music, greek music, gregorian chant, grime, grindcore, "
                         "groove metal, group sounds, grunge, guaguancó, guajira, guaracha, guarania, gumbe, guoyue, "
                         "gwo ka, gypsy jazz, gypsy punk, għana, habanera, hamburger schule, han folk music, "
                         "happy hardcore, harawi, hard bop, hard house, hard rock, hard trance, hardcore [edm], "
                         "hardcore breaks, hardcore hip-hop, hardcore punk, hardstep, hardstyle, harsh noise, "
                         "harsh noise wall, hawaiian music, heartland rock, heavy metal, heavy psych, heikyoku, "
                         "hi-nrg, highlife, hill country blues, hill tribe music, himene tarava, hindustani classical "
                         "music, hip house, hiplife, hispanic music, hmong folk music, hmong pop, honky tonk, "
                         "horror punk, horror synth, horrorcore, house, huayno, humppa, hungarian folk music, "
                         "hyang-ak, hyphy, hypnagogic pop, ibiza trance, icelandic folk music, idm, illbient, "
                         "impressionism, indeterminacy, indian pop, indie folk, indie pop, indie rock, indietronica, "
                         "indigenous australian music, indorock, industrial, industrial hip-hop, industrial metal, "
                         "industrial rock, industrial techno, instrumental hip-hop, integral serialism, interview, "
                         "inuit vocal games, iranian folk music, iranian music, irish folk music, islamic modal "
                         "music, israeli folk music, italian folk music, italo dance, italo house, italo pop, "
                         "italo-disco, izlan, j-core, j-pop, jaipongan, jam band, jamaican music, jamaican ska, "
                         "jangle pop, japanese classical music, japanese folk music, japanese hardcore, "
                         "japanese hip-hop, japanese music, jazz fusion, jazz poetry, jazz pop, jazz rap, jazz-funk, "
                         "jazz-rock, jazzstep, jeong-ak, jerk rap, jersey club, jewish music, jiangnan sizhu, jibaro, "
                         "jit, jiuta, joik, jongo, joropo, jovem guarda, jug band, juke, jump-blues, jump-up, "
                         "jumpstyle, jungle, jungle terror, junkanoo, jùjú, jōruri, k-pop, kabarett, kabye folk "
                         "music, kafi, kagura, kalindula, kanto, kapuka, karadeniz folk music, karakalpak traditional "
                         "music, kaseko, kayōkyoku, kazakh traditional music, kecapi suling, keroncong, "
                         "khakas traditional music, khoisan folk music, khyal, kidumbak, kilapanga, "
                         "kirghiz traditional music, kirtan, kizomba, klapa, klezmer, kliningan, korean classical "
                         "music, korean folk music, kouta, krautrock, kritika, kuduro, kulintang, kumiuta, kundiman, "
                         "kurdish folk music, kwaito, kwassa kwassa, kwela, könsrock, lab polyphony, laika, lambada, "
                         "latin alternative, latin american music, latin classical music, latin disco, "
                         "latin electronic, latin freestyle, latin funk, latin house, latin jazz, latin pop, "
                         "latin rap, latin rock, latin soul, latvian folk music, levenslied, lieder, liedermacher, "
                         "light music, lilat, liquid funk, lithuanian folk music, lo-fi indie, lolicore, lounge, "
                         "lovers rock, lowercase, luk krung, luk thung, lăutărească, macedonian folk music, maddahi, "
                         "madrigal, maftirim, mahori, mahraganat, makina, makossa, malagasy folk music, "
                         "malagasy music, malayali folk music, maloya, mambo, mande folk music, mandopop, manele, "
                         "mangue beat, manila sound, manx folk music, mapuche music, marabi, maracatu, marchinha, "
                         "mariachi, marinera, marrabenta, martial industrial, math rock, mathcore, maxixe, mbalax, "
                         "mbaqanga, mbenga-mbuti music, mbube, medieval classical music, medieval folk metal, "
                         "medieval rock, melbourne bounce, melodic black metal, melodic death metal, "
                         "melodic hardcore, melodic metalcore, memphis rap, mento, merecumbé, merengue, merseybeat, "
                         "metal, metalcore, mexican folk music, mexican music, miami bass, microhouse, microsound, "
                         "microtonal, midwest emo, milonga, min'yō, minimal drum and bass, minimal synth, "
                         "minimal techno, minimal wave, minimalism, mizrahi music, mobb music, mod, mod revival, "
                         "moda de viola, modal jazz, modern classical, modern laika, molam, mongolian long song, "
                         "mongolian throat singing, mongolian traditional music, mono, mood kayō, moombahcore, "
                         "moombahton, moorish music, moravian folk music, morna, moutya, movimiento alterado, "
                         "mozambique, mpb, muliza, murga, musette, music hall, musical comedy, musika popullore, "
                         "musique concrète, muzică de mahala, muziki wa dansi, méringue, música criolla peruana, "
                         "música de intervenção, música gaúcha, nagauta, narodno zabavna glasba, nashville sound, "
                         "native american music, nature recordings, nederbeat, nederpop, neo kyma, neo-medieval folk, "
                         "neo-prog, neo-psychedelia, neo-soul, neo-traditionalist country, neoclassical metal, "
                         "neoclassical new age, neoclassicism, neofolk, nerdcore, neue deutche welle, neue deutsche "
                         "härte, neurofunk, new beat, new complexity, new jack swing, new orleans blues, new orleans "
                         "brass band, new orleans r&b, new romantic, new wave, new york hardcore, newa folk music, "
                         "newfoundland folk music, ngoma, nguni folk music, nhạc vàng, nintendocore, "
                         "nisiotika aigaiou, nisiotika ioniou, nitzhonot, no wave, noh, noise, noise pop, noise rock, "
                         "noisecore, nordic folk music, nordic folk rock, nordic old time dance music, nortec, "
                         "norteño, north african music, northeastern african music, northern soul, northumbrian folk "
                         "music, norwegian folk music, nouvelle chanson française, nova cançó, novelty piano, "
                         "novo dub, nrg, nu jazz, nu metal, nu style gabber, nu-disco, nubian music, nueva canción, "
                         "nueva canción española, nueva canción latinoamericana, nueva trova, numbers stations "
                         "broadcasts, nursery rhymes, nwobhm, nyahbinghi, nòva cançon, occitan folk music, oi!, "
                         "old-time, onda nueva, ondō, onkyo, opera, opera buffa, opera semiseria, opera seria, "
                         "operetta, oratorio, orchestral, ottoman military music, outlaw country, outsider house, "
                         "p-funk, pachanga, pagan black metal, pagode, pagode romântico, paisley underground, "
                         "pakacaping music, palingsound, palm wine music, papuan traditional music, partido alto, "
                         "pashto folk music, pasillo, pasodoble, peking opera, persian classical music, persian pop, "
                         "philippine music, philly soul, piano blues, piano rock, pibroch, picopop, piedmont blues, "
                         "pilón, pimba, pinoy folk rock, pinpeat, piphat, plainsong, plena, poetry, poezja śpiewana, "
                         "polish carpathian folk music, polish folk music, political hip-hop, polka, polynesian "
                         "music, polyphonic chant, pop ghazal, pop punk, pop rap, pop raï, pop reggae, pop rock, "
                         "pop soul, pop sunda, pops orchestra, porn groove, porro, portuguese folk music, portuguese "
                         "music, post-bop, post-grunge, post-hardcore, post-industrial, post-minimalism, post-punk, "
                         "post-punk revival, post-rock, power electronics, power metal, power noise, power pop, "
                         "powerviolence, powwow music, praise & worship, prank calls, prehistoric music, progressive "
                         "big band, progressive bluegrass, progressive country, progressive electronic, progressive "
                         "folk, progressive house, progressive metal, progressive pop, progressive psytrance, "
                         "progressive rock, progressive trance, proto-punk, psybient, psychedelic folk, psychedelic "
                         "pop, psychedelic rock, psychedelic soul, psychobilly, psytrance, pub rock, punk blues, "
                         "punk rock, punta, purple sound, qaraami, qawwali, queercore, rabiz, radio play, raga rock, "
                         "ragga, ragga jungle, raggacore, ragtime, ranchera, rap metal, rap rock, rapai dabõih, "
                         "rapso, rara, rasin, rasqueado, rautalanka, raï, red dirt, reggae, reggaeton, rembetika, "
                         "renaissance music, repente, revue, rhumba, rhythm & blues, riddim, riot grrrl, ripsaw, "
                         "ritual ambient, rock & roll, rock in opposition, rock opera, rock urbano español, "
                         "rockabilly, rocksteady, romani folk music, romanian dance-pop, romanian etno music, "
                         "romanian folk music, romanian music, romanticism, romanţe, roots reggae, roots rock, "
                         "rumba catalana, rumba flamenca, runolaulu, russian chanson, russian folk music, "
                         "russian romance, ryūkōka, rōkyoku, sacred harp music, saeta, sahrawi music, "
                         "sakha traditional music, salegy, salsa, salsa dura, salsa romántica, saluang klasik, samba, "
                         "samba de breque, samba de roda, samba soul, samba-canção, samba-choro, samba-enredo, "
                         "samba-exaltação, samba-jazz, samba-reggae, samba-rock, samoan music, samoyedic traditional "
                         "music, sanjo, santería music, santé engagé, sarala gee, sardana, schlager, schranz, "
                         "scottish folk music, scouse house, screamo, scrumpy and western, sea shanties, sean-nós, "
                         "seggae, semba, sephardic music, sequencer & midi, serialism, sertanejo, sertanejo de raiz, "
                         "sertanejo romântico, sertanejo universitário, sevdalinka, sevillanas, seychelles & "
                         "mascarene islands music, shadow music, shangaan electro, shaoxing opera, shashmaqam, "
                         "shaʻabi, shetland and orkney islands folk music, shibuya-kei, shidaiqu, shinkyoku, "
                         "shoegaze, shomyo, shona mbira music, show tunes, sinawi, ska punk, skate punk, "
                         "sketch comedy, skiffle, skiladika, skinhead reggae, skweee, slack-key guitar, slam death "
                         "metal, slavic folk music, slovak folk music, slovenian folk music, slowcore, sludge metal, "
                         "smooth jazz, smooth soul, snap, soca, soft rock, son calentano, son cubano, son huasteco, "
                         "son istmeño, son jarocho, songhai music, songo, sonorism, sophisti-pop, sotho-tswana folk "
                         "music, soukous, soukyoku, soul, soul jazz, sound collage, sound poetry, south american folk "
                         "music, south asian classical music, south asian folk music, south asian music, "
                         "southeast asian classical music, southeast asian folk music, southeast asian music, "
                         "southern african folk music, southern african music, southern gospel, southern hip-hop, "
                         "southern rock, southern soul, space age pop, space ambient, space disco, space rock, "
                         "spacesynth, spanish classical music, spanish folk music, spanish music, spectralism, "
                         "speeches, speed garage, speed metal, speedcore, spiritual jazz, spirituals, splittercore, "
                         "spouge, sri lankan folk music, stand-up comedy, standards, starogradska muzika, stereo, "
                         "stochastic music, stoner metal, stoner rock, stride, sufi rock, sumerian music, "
                         "sunshine pop, suomisaundi, surf music, surf punk, surf rock, sutartinės, swamp blues, "
                         "swamp rock, swedish folk music, swing, swing revival, swingueira, symphonic black metal, "
                         "symphonic metal, symphonic prog, symphonic rock, symphony, synth funk, synth punk, "
                         "synthpop, synthwave, syriac chant, séga, taarab, taiko, tajik traditional music, "
                         "talking blues, tallava, tamborera, tamborito, tango, tango nuevo, tape music, taquirari, "
                         "tassu, tatar folk music, tchink system, tchinkoumé, te pūoro māori, tech house, "
                         "tech trance, technical death metal, technical thrash metal, techno, techno kayō, techstep, "
                         "tecnobrega, tecnorumba, teen pop, tejano, tembang cianjuran, terrorcore, tex-mex, "
                         "thai classical music, third stream, third wave ska, thrash metal, thrashcore, "
                         "throat singing, thumri, tibetan traditional music, tigrinya, timba, tishoumaren, tizita, "
                         "tonada, tondero, tone poem, tosk polyphony, totalism, township jive, tradi-modern, "
                         "traditional arabic pop, traditional black gospel, traditional cajun, traditional country, "
                         "traditional doom metal, traditional folk music, traditional maloya, traditional pop, "
                         "traditional raï, traditional séga, tragédie en musique, trance, trance metal, trancecore, "
                         "trancestep, trap, trap rap, tribal ambient, tribal guarachero, tribal house, trip hop, "
                         "tropical house, tropicália, tropipop, trot, trova, trova yucateca, truck driving country, "
                         "trás-os-montes folk music, tsonga disco, tsugaru shamisen, tuareg music, tumba, tumbélé, "
                         "turbo-folk, turkic-mongolic traditional music, turkish classical music, turkish folk music, "
                         "turkish music, turkish pop, turkish sufi music, turkmen traditional music, turntable music, "
                         "turntablism, tuvan throat singing, twee pop, uk bass, uk funky, uk garage, uk hip-hop, "
                         "uk82, ukrainian folk music, unyago, uplifting trance, upopo, urban cowboy, "
                         "uyghur traditional music, uzbek traditional music, uzun hava, vallenato, vals criollo, "
                         "vanguarda paulista, vaporwave, vaudeville, vaudeville blues, venezuelan malagueña, "
                         "vietnamese classical music, vietnamese folk music, viking metal, visor, vocal jazz, "
                         "vocal surf, vocal trance, volkstümliche musik, waka, war metal, warsaw city folk, "
                         "wassoulou, welsh folk music, west african music, west coast hip-hop, west coast rock, "
                         "western classical music, western swing, whale song, witch house, wolof music, wonky, "
                         "wonky techno, work songs, xote, yass, yayue, yodeling, yoruba music, yukar, yé-yé, zamba, "
                         "zamrock, zarzuela, zeuhl, zeybek, zhabdro gorgom, zinli, znamenny chant, zolo, zouglou, "
                         "zouk, zouk love, zydeco, özgün müzik, čalgija"]
GENRE_FILTER["country"] = ["african, american, arabic, australian, austrian, belgian, brazilian, british, canadian, "
                           "caribbean, celtic, chinese, cuban, danish, dutch, eastern europe, egyptian, estonian, "
                           "european, finnish, french, german, greek, hawaiian, ibiza, icelandic, indian, iranian, "
                           "irish, island, israeli, italian, jamaican, japanese, korean, mexican, middle eastern, "
                           "new zealand, norwegian, oriental, polish, portuguese, russian, scandinavian, scottish, "
                           "southern, spanish, swedish, swiss, thai, third world, turkish, welsh, western"]
GENRE_FILTER["city"] = ["acapulco, adelaide, amsterdam, athens, atlanta, atlantic city, auckland, austin, "
                        "bakersfield, bali, baltimore, bangalore, bangkok, barcelona, barrie, beijing, belfast, "
                        "berlin, birmingham, bogota, bombay, boston, brasilia, brisbane, bristol, brooklyn, brussels, "
                        "bucharest, budapest, buenos aires, buffalo, calcutta, calgary, california, cancun, caracas, "
                        "charlotte, chicago, cincinnati, cleveland, copenhagen, dallas, delhi, denver, detroit, "
                        "dublin, east coast, edmonton, frankfurt, geneva, glasgow, grand rapids, guadalajara, "
                        "halifax, hamburg, hamilton, helsinki, hong kong, houston, illinois, indianapolis, istanbul, "
                        "jacksonville, kansas city, kiev, las vegas, leeds, lisbon, liverpool, london, los angeles, "
                        "louisville, madrid, manchester, manila, marseille, mazatlan, melbourne, memphis, "
                        "mexico city, miami, michigan, milan, minneapolis, minnesota, mississippi, monterrey, "
                        "montreal, munich, myrtle beach, nashville, new jersey, new orleans, new york, new york city, "
                        "niagara falls, omaha, orlando, oslo, ottawa, palm springs, paris, pennsylvania, perth, "
                        "philadelphia, phoenix, phuket, pittsburgh, portland, puebla, raleigh, reno, richmond, "
                        "rio de janeiro, rome, sacramento, salt lake city, san antonio, san diego, san francisco, "
                        "san jose, santiago, sao paulo, seattle, seoul, shanghai, sheffield, spokane, stockholm, "
                        "sydney, taipei, tampa, texas, tijuana, tokyo, toledo, toronto, tucson, tulsa, vancouver, "
                        "victoria, vienna, warsaw, wellington, westcoast, windsor, winnipeg, zurich"]
GENRE_FILTER["mood"] = ["angry, bewildered, bouncy, calm, cheerful, chill, cold, complacent, crazy, crushed, cynical, "
                        "depressed, dramatic, dreamy, drunk, eclectic, emotional, energetic, envious, feel good, "
                        "flirty, funky, groovy, happy, haunting, healing, high, hopeful, hot, humorous, inspiring, "
                        "intense, irritated, laidback, lonely, lovesongs, meditation, melancholic, mellow, moody, "
                        "morose, passionate, peaceful, playful, pleased, positive, quirky, reflective, rejected, "
                        "relaxed, retro, sad, sentimental, silly, smooth, soulful, spiritual, suicidal, surprised, "
                        "sympathetic, trippy, upbeat, uplifting, weird, wild, yearning"]
GENRE_FILTER["decade"] = ["1800s, 1810s, 1820s, 1830s, 1980s, 1850s, 1860s, 1870s, 1880s, 1890s, 1900s, 1910s, 1920s, "
                          "1930s, 1940s, 1950s, 1960s, 1970s, 1980s, 1990s, 2000s"]
GENRE_FILTER["year"] = ["1801, 1802, 1803, 1804, 1805, 1806, 1807, 1808, 1809, 1810, 1811, 1812, 1813, 1814, 1815, "
                        "1816, 1817, 1818, 1819, 1820, 1821, 1822, 1823, 1824, 1825, 1826, 1827, 1828, 1829, 1830, "
                        "1831, 1832, 1833, 1834, 1835, 1836, 1837, 1838, 1839, 1840, 1841, 1842, 1843, 1844, 1845, "
                        "1846, 1847, 1848, 1849, 1850, 1851, 1852, 1853, 1854, 1855, 1856, 1857, 1858, 1859, 1860, "
                        "1861, 1862, 1863, 1864, 1865, 1866, 1867, 1868, 1869, 1870, 1871, 1872, 1873, 1874, 1875, "
                        "1876, 1877, 1878, 1879, 1880, 1881, 1882, 1883, 1884, 1885, 1886, 1887, 1888, 1889, 1890, "
                        "1891, 1892, 1893, 1894, 1895, 1896, 1897, 1898, 1899, 1900, 1901, 1902, 1903, 1904, 1905, "
                        "1906, 1907, 1908, 1909, 1910, 1911, 1912, 1913, 1914, 1915, 1916, 1917, 1918, 1919, 1920, "
                        "1921, 1922, 1923, 1924, 1925, 1926, 1927, 1928, 1929, 1930, 1931, 1932, 1933, 1934, 1935, "
                        "1936, 1937, 1938, 1939, 1940, 1941, 1942, 1943, 1944, 1945, 1946, 1947, 1948, 1949, 1950, "
                        "1951, 1952, 1953, 1954, 1955, 1956, 1957, 1958, 1959, 1960, 1961, 1962, 1963, 1964, 1965, "
                        "1966, 1967, 1968, 1969, 1970, 1971, 1972, 1973, 1974, 1975, 1976, 1977, 1978, 1979, 1980, "
                        "1981, 1982, 1983, 1984, 1985, 1986, 1987, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, "
                        "1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, "
                        "2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020"]
GENRE_FILTER["occasion"] = ["background, birthday, breakup, carnival, chillout, christmas, death, dinner, drinking, "
                            "driving, graduation, halloween, hanging out, heartache, holiday, late night, love, "
                            "new year, party, protest, rain, rave, romantic, sleep, spring, summer, sunny, twilight, "
                            "valentine, wake up, wedding, winter, work"]
GENRE_FILTER["category"] = ["animal songs, attitude, autumn, b-side, ballad, banjo, bass, beautiful, body parts, "
                            "bootlegs, brass, cafe del mar, chamber music, clarinet, classic, classic tunes, "
                            "compilations, covers, cowbell, deceased, demos, divas, dj, drugs, drums, duets, "
                            "field recordings, female, female vocalists, film score, flute, food, genius, girl group, "
                            "great lyrics, guitar solo, guitarist, handclaps, harmonica, historical, horns, hypnotic, "
                            "influential, insane, jam, keyboard, legends, life, linedance, live, loved, lyricism, "
                            "male, male vocalists, masterpiece, melodic, memories, musicals, nostalgia, novelty, "
                            "number songs, old school, oldie, oldies, one hit wonders, orchestra, organ, parody, "
                            "poetry, political, promos, radio programs, rastafarian, remix, samples, satire, "
                            "saxophone, showtunes, sing-alongs, singer-songwriter, slide guitar, solo instrumentals, "
                            "songs with names, soundtracks, speeches, stories, strings, stylish, synth, title is a "
                            "full sentence, top 40, traditional, trumpet, unique, unplugged, violin, virtuoso, "
                            "vocalization, vocals"]
GENRE_FILTER["translate"] = {
    "16 bit": "16-bit",
    "16bit": "16-bit",
    "2 step": "2-step",
    "2step": "2-step",
    "abstract hip hop": "abstract hip-hop",
    "abstract hiphop": "abstract hip-hop",
    "afoxe": "afoxé",
    "afro cuban jazz": "afro-cuban jazz",
    "afro funk": "afro-funk",
    "afro house": "afro-house",
    "afro jazz": "afro-jazz",
    "afro rock": "afro-rock",
    "afrocuban jazz": "afro-cuban jazz",
    "afrofunk": "afro-funk",
    "afrohouse": "afro-house",
    "afrojazz": "afro-jazz",
    "afrorock": "afro-rock",
    "al maqam al iraqi": "al-maqam al-iraqi",
    "almaqam aliraqi": "al-maqam al-iraqi",
    "alt country": "alt-country",
    "altcountry": "alt-country",
    "alternative country": "alt-country",
    "alternative r&b": "alternative r&b",
    "anarcho punk": "anarcho-punk",
    "anarchopunk": "anarcho-punk",
    "anti folk": "anti-folk",
    "antifolk": "anti-folk",
    "avant folk": "avant-folk",
    "avant garde jazz": "avant-garde jazz",
    "avant garde metal": "avant-garde metal",
    "avant prog": "avant-prog",
    "avantfolk": "avant-folk",
    "avantgarde jazz": "avant-garde jazz",
    "avantgarde metal": "avant-garde metal",
    "avantprog": "avant-prog",
    "axe": "axé",
    "baiao": "baião",
    "balkan pop folk": "balkan pop-folk",
    "balkan popfolk": "balkan pop-folk",
    "bandas de viento de mexico": "bandas de viento de méxico",
    "bend skin": "bend-skin",
    "bendskin": "bend-skin",
    "blue eyed soul": "blue-eyed soul",
    "blueeyed soul": "blue-eyed soul",
    "bolero espanol": "bolero español",
    "bro country": "bro-country",
    "brocountry": "bro-country",
    "c pop": "c-pop",
    "cabo zouk": "cabo-zouk",
    "cabozouk": "cabo-zouk",
    "calgija": "čalgija",
    "cancion melodica": "canción melódica",
    "candomble music": "candomblé music",
    "carimbo": "carimbó",
    "chachacha": "chachachá",
    "chamame": "chamamé",
    "changui": "changüí",
    "chanson a texte": "chanson à texte",
    "chanson realiste": "chanson réaliste",
    "chotis madrileno": "chotis madrileño",
    "christian hip hop": "christian hip-hop",
    "christian hiphop": "christian hip-hop",
    "conscious hip hop": "conscious hip-hop",
    "conscious hiphop": "conscious hip-hop",
    "contemporary r&b": "contemporary r&b",
    "coupe-decale": "coupé-décalé",
    "coupé décalé": "coupé-décalé",
    "coupédécalé": "coupé-décalé",
    "cpop": "c-pop",
    "cuple": "cuplé",
    "d beat": "d-beat",
    "dance pop": "dance-pop",
    "dance punk": "dance-punk",
    "dancepop": "dance-pop",
    "dancepunk": "dance-punk",
    "dang ak": "dang-ak",
    "dangak": "dang-ak",
    "danzon": "danzón",
    "dbeat": "d-beat",
    "doo wop": "doo-wop",
    "doowop": "doo-wop",
    "drum 'n' bass": "drum and bass",
    "drum n bass": "drum and bass",
    "east coast hip hop": "east coast hip-hop",
    "east coast hiphop": "east coast hip-hop",
    "electro disco": "electro-disco",
    "electro industrial": "electro-industrial",
    "electrodisco": "electro-disco",
    "electroindustrial": "electro-industrial",
    "emo pop": "emo-pop",
    "emopop": "emo-pop",
    "ethio jazz": "ethio-jazz",
    "ethiojazz": "ethio-jazz",
    "euro disco": "euro-disco",
    "euro trance": "euro-trance",
    "eurodisco": "euro-disco",
    "eurotrance": "euro-trance",
    "experimental hip hop": "experimental hip-hop",
    "experimental hiphop": "experimental hip-hop",
    "forro": "forró",
    "forro eletronico": "forró eletrônico",
    "forro universitario": "forró universitário",
    "french canadian folk music": "french-canadian folk music",
    "french hip hop": "french hip-hop",
    "french hiphop": "french hip-hop",
    "frenchcanadian folk music": "french-canadian folk music",
    "full on psytrance": "full-on psytrance",
    "fullon psytrance": "full-on psytrance",
    "funana": "funaná",
    "funk ostentacao": "funk ostentação",
    "g funk": "g-funk",
    "gfunk": "g-funk",
    "ghana": "għana",
    "go go": "go-go",
    "gogo": "go-go",
    "guaguanco": "guaguancó",
    "hardcore hip hop": "hardcore hip-hop",
    "hardcore hiphop": "hardcore hip-hop",
    "hi nrg": "hi-nrg",
    "hinrg": "hi-nrg",
    "hyang ak": "hyang-ak",
    "hyangak": "hyang-ak",
    "industrial hip hop": "industrial hip-hop",
    "industrial hiphop": "industrial hip-hop",
    "instrumental hip hop": "instrumental hip-hop",
    "instrumental hiphop": "instrumental hip-hop",
    "italo disco": "italo-disco",
    "italodisco": "italo-disco",
    "j core": "j-core",
    "j pop": "j-pop",
    "japanese hip hop": "japanese hip-hop",
    "japanese hiphop": "japanese hip-hop",
    "japanese pop": "j-pop",
    "jazz funk": "jazz-funk",
    "jazz rock": "jazz-rock",
    "jazzfunk": "jazz-funk",
    "jazzrock": "jazz-rock",
    "jcore": "j-core",
    "jeong ak": "jeong-ak",
    "jeongak": "jeong-ak",
    "joruri": "jōruri",
    "jpop": "j-pop",
    "juju": "jùjú",
    "jump blues": "jump-blues",
    "jump up": "jump-up",
    "jumpblues": "jump-blues",
    "jumpup": "jump-up",
    "k pop": "k-pop",
    "kayokyoku": "kayōkyoku",
    "konsrock": "könsrock",
    "korean pop": "k-pop",
    "kpop": "k-pop",
    "lautareasca": "lăutărească",
    "lo fi indie": "lo-fi indie",
    "lofi indie": "lo-fi indie",
    "mbenga mbuti music": "mbenga-mbuti music",
    "mbengambuti music": "mbenga-mbuti music",
    "merecumbe": "merecumbé",
    "meringue": "méringue",
    "min'yo": "min'yō",
    "mood kayo": "mood kayō",
    "musica criolla peruana": "música criolla peruana",
    "musica de intervencao": "música de intervenção",
    "musica gaucha": "música gaúcha",
    "musique concrete": "musique concrète",
    "muzica de mahala": "muzică de mahala",
    "neo medieval folk": "neo-medieval folk",
    "neo prog": "neo-prog",
    "neo psychedelia": "neo-psychedelia",
    "neo soul": "neo-soul",
    "neo traditionalist country": "neo-traditionalist country",
    "neomedieval folk": "neo-medieval folk",
    "neoprog": "neo-prog",
    "neopsychedelia": "neo-psychedelia",
    "neosoul": "neo-soul",
    "neotraditionalist country": "neo-traditionalist country",
    "neue deutsche harte": "neue deutsche härte",
    "new orleans r&b": "new orleans r&b",
    "nhac vang": "nhạc vàng",
    "norteno": "norteño",
    "nouvelle chanson francaise": "nouvelle chanson française",
    "nova canco": "nova cançó",
    "nova cancon": "nòva cançon",
    "nu disco": "nu-disco",
    "nudisco": "nu-disco",
    "nueva cancion": "nueva canción",
    "nueva cancion espanola": "nueva canción española",
    "nueva cancion latinoamericana": "nueva canción latinoamericana",
    "old time": "old-time",
    "oldtime": "old-time",
    "ondo": "ondō",
    "ozgun muzik": "özgün müzik",
    "p funk": "p-funk",
    "pagode romantico": "pagode romântico",
    "pfunk": "p-funk",
    "pilon": "pilón",
    "poezja spiewana": "poezja śpiewana",
    "political hip hop": "political hip-hop",
    "political hiphop": "political hip-hop",
    "pop rai": "pop raï",
    "post bop": "post-bop",
    "post grunge": "post-grunge",
    "post hardcore": "post-hardcore",
    "post industrial": "post-industrial",
    "post minimalism": "post-minimalism",
    "post punk": "post-punk",
    "post punk revival": "post-punk revival",
    "post rock": "post-rock",
    "postbop": "post-bop",
    "postgrunge": "post-grunge",
    "posthardcore": "post-hardcore",
    "postindustrial": "post-industrial",
    "postminimalism": "post-minimalism",
    "postpunk": "post-punk",
    "postpunk revival": "post-punk revival",
    "postrock": "post-rock",
    "proto punk": "proto-punk",
    "protopunk": "proto-punk",
    "rai": "raï",
    "rapai daboih": "rapai dabõih",
    "rock urbano espanol": "rock urbano español",
    "rokyoku": "rōkyoku",
    "romanian dance pop": "romanian dance-pop",
    "romanian dancepop": "romanian dance-pop",
    "romante": "romanţe",
    "ryukoka": "ryūkōka",
    "salsa romantica": "salsa romántica",
    "samba canção": "samba-canção",
    "samba choro": "samba-choro",
    "samba enredo": "samba-enredo",
    "samba exaltação": "samba-exaltação",
    "samba jazz": "samba-jazz",
    "samba reggae": "samba-reggae",
    "samba rock": "samba-rock",
    "samba-cancao": "samba-canção",
    "samba-exaltacao": "samba-exaltação",
    "sambacanção": "samba-canção",
    "sambachoro": "samba-choro",
    "sambaenredo": "samba-enredo",
    "sambaexaltação": "samba-exaltação",
    "sambajazz": "samba-jazz",
    "sambareggae": "samba-reggae",
    "sambarock": "samba-rock",
    "sante engage": "santé engagé",
    "santeria music": "santería music",
    "sean nós": "sean-nós",
    "sean-nos": "sean-nós",
    "seannós": "sean-nós",
    "sertanejo romantico": "sertanejo romântico",
    "sertanejo universitario": "sertanejo universitário",
    "sha`abi": "shaʻabi",
    "shibuya kei": "shibuya-kei",
    "shibuyakei": "shibuya-kei",
    "slack key guitar": "slack-key guitar",
    "slackkey guitar": "slack-key guitar",
    "son istmeno": "son istmeño",
    "sophisti pop": "sophisti-pop",
    "sophistipop": "sophisti-pop",
    "sotho tswana folk music": "sotho-tswana folk music",
    "sothotswana folk music": "sotho-tswana folk music",
    "southern hip hop": "southern hip-hop",
    "southern hiphop": "southern hip-hop",
    "stand up comedy": "stand-up comedy",
    "standup comedy": "stand-up comedy",
    "sutartines": "sutartinės",
    "tchinkoume": "tchinkoumé",
    "te puoro maori": "te pūoro māori",
    "techno kayo": "techno kayō",
    "tex mex": "tex-mex",
    "texmex": "tex-mex",
    "tradi modern": "tradi-modern",
    "tradimodern": "tradi-modern",
    "traditional rai": "traditional raï",
    "traditional sega": "traditional séga",
    "tragedie en musique": "tragédie en musique",
    "tras-os-montes folk music": "trás-os-montes folk music",
    "tropicalia": "tropicália",
    "trás os montes folk music": "trás-os-montes folk music",
    "trásosmontes folk music": "trás-os-montes folk music",
    "tumbele": "tumbélé",
    "turbo folk": "turbo-folk",
    "turbofolk": "turbo-folk",
    "turkic mongolic traditional music": "turkic-mongolic traditional music",
    "turkicmongolic traditional music": "turkic-mongolic traditional music",
    "uk hip hop": "uk hip-hop",
    "uk hiphop": "uk hip-hop",
    "venezuelan malaguena": "venezuelan malagueña",
    "volkstumliche musik": "volkstümliche musik",
    "west coast hip hop": "west coast hip-hop",
    "west coast hiphop": "west coast hip-hop",
    "ye-ye": "yé-yé",
    "yé yé": "yé-yé",
    "yéyé": "yé-yé"
}


def matches_list(s, lst):
    if s in lst:
        return True
    for item in lst:
        if '*' in item:
            if re.match(re.escape(item).replace(r'\*', '.*?'), s):
                return True
    return False


# Function to sort/compare a 2 Element of Tupel


def cmptaginfo(a, b):
    return (a[1][0] > b[1][0]) - (a[1][0] < b[1][0]) * -1


def cmptaginfokey(a):
    return a[1][0]


def _lazy_load_filters(cfg):
    if not GENRE_FILTER["_loaded_"]:
        GENRE_FILTER["major"] = cfg["lastfm_genre_major"].split(',')
        GENRE_FILTER["minor"] = cfg["lastfm_genre_minor"].split(',')
        GENRE_FILTER["decade"] = cfg["lastfm_genre_decade"].split(',')
        GENRE_FILTER["year"] = cfg["lastfm_genre_year"].split(',')
        GENRE_FILTER["country"] = cfg["lastfm_genre_country"].split(',')
        GENRE_FILTER["city"] = cfg["lastfm_genre_city"].split(',')
        GENRE_FILTER["mood"] = cfg["lastfm_genre_mood"].split(',')
        GENRE_FILTER["occasion"] = cfg["lastfm_genre_occasion"].split(',')
        GENRE_FILTER["category"] = cfg["lastfm_genre_category"].split(',')
        GENRE_FILTER["translate"] = dict([item.split(',') for item in cfg["lastfm_genre_translations"].split("\n")])
        GENRE_FILTER["_loaded_"] = True


def apply_translations_and_sally(tag_to_count, sally, factor):
    ret = {}
    for name, count in tag_to_count.items():
        # apply translations
        try:
            name = GENRE_FILTER["translate"][name.lower()]
        except KeyError:
            pass

        # make sure it's lowercase
        lower = name.lower()

        if lower not in ret or ret[lower][0] < (count * factor):
            ret[lower] = [count * factor, sally]
    return list(ret.items())


def _tags_finalize(album, metadata, tags, get_next):
    """Processes the tag metadata to decide which tags to use and sets metadata"""

    if get_next:
        get_next(tags)
    else:
        cfg = album.tagger.config.setting

        # last tag-weight for inter-tag comparsion
        lastw = {"n": False, "s": False}
        # List: (use sally-tags, use track-tags, use artist-tags, use
        # drop-info,use minweight,searchlist, max_elems
        info = {"major": [True, True, True, True, True, GENRE_FILTER["major"], cfg["lastfm_max_group_tags"]],
                "minor": [True, True, True, True, True, GENRE_FILTER["minor"], cfg["lastfm_max_minor_tags"]],
                "country": [True, False, True, False, False, GENRE_FILTER["country"], 1],
                "city": [True, False, True, False, False, GENRE_FILTER["city"], 1],
                "decade": [True, True, False, False, False, GENRE_FILTER["decade"], 1],
                "year": [True, True, False, False, False, GENRE_FILTER["year"], 1],
                "year2": [True, True, False, False, False, GENRE_FILTER["year"], 1],
                "year3": [True, True, False, False, False, GENRE_FILTER["year"], 1],
                "mood": [True, True, True, False, False, GENRE_FILTER["mood"], cfg["lastfm_max_mood_tags"]],
                "occasion": [True, True, True, False, False, GENRE_FILTER["occasion"],
                             cfg["lastfm_max_occasion_tags"]],
                "category": [True, True, True, False, False, GENRE_FILTER["category"],
                             cfg["lastfm_max_category_tags"]]
                }
        hold = {"all/tags": []}

        # Init the Album-Informations
        albid = album.id
        if cfg["write_id3v23"]:
            year_tag = '~id3:TORY'
        else:
            year_tag = '~id3:TDOR'
        glb = {"major": {'metatag': 'grouping', 'data': ALBUM_GENRE},
               "country": {'metatag': 'comment:Songs-DB_Custom3', 'data': ALBUM_COUNTRY},
               "city": {'metatag': 'comment:Songs-DB_Custom3', 'data': ALBUM_CITY},
               "year": {'metatag': year_tag, 'data': ALBUM_YEAR},
               "year2": {'metatag': 'originalyear', 'data': ALBUM_YEAR},
               "year3": {'metatag': 'date', 'data': ALBUM_YEAR}}
        for elem in list(glb.keys()):
            if albid not in glb[elem]['data']:
                glb[elem]['data'][albid] = {'count': 1, 'genres': {}}
            else:
                # noinspection PyTypeChecker
                glb[elem]['data'][albid]['count'] += 1

        if tags:
            # search for tags
            tags.sort(key=cmptaginfokey, reverse=True)
            for lowered, [weight, stype] in tags:
                name = lowered.title()
                # if is tag which should only used for extension (if too few
                # tags found)
                s = stype == 1
                arttag = stype > 0  # if is artist tag
                if name not in hold["all/tags"]:
                    hold["all/tags"].append(name)

                # Decide if tag should be searched in major and minor fields
                drop = not (s and (
                        not lastw['s'] or (lastw['s'] - weight) < cfg["lastfm_max_artisttag_drop"])) and not (
                        not s and (not lastw['n'] or (lastw['n'] - weight) < cfg["lastfm_max_tracktag_drop"]))
                if not drop:
                    if s:
                        lastw['s'] = weight
                    else:
                        lastw['n'] = weight

                below = (s and weight < cfg["lastfm_min_artisttag_weight"]) or (
                        not s and weight < cfg["lastfm_min_tracktag_weight"])

                for group, ielem in list(info.items()):
                    if matches_list(lowered, ielem[5]):
                        if below and ielem[4]:
                            # If Should use min-weigh information
                            break
                        if drop and ielem[3]:
                            # If Should use the drop-information
                            break
                        if s and not ielem[0]:
                            # If Sally-Tag and should not be used
                            break
                        if arttag and not ielem[2]:
                            # If Artist-Tag and should not be used
                            break
                        if not arttag and not ielem[1]:
                            # If Track-Tag and should not be used
                            break

                        # prefer Not-Sally-Tags (so, artist OR track-tags)
                        if not s and group + "/sally" in hold and name in hold[group + "/sally"]:
                            hold[group + "/sally"].remove(name)
                            hold[group + "/tags"].remove(name)
                        # Insert Tag
                        if not group + "/tags" in hold:
                            hold[group + "/tags"] = []
                        if name not in hold[group + "/tags"]:
                            if s:
                                if not group + "/sally" in hold:
                                    hold[group + "/sally"] = []
                                hold[group + "/sally"].append(name)
                            # collect global genre information for special
                            # tag-filters
                            if not arttag and group in glb:
                                # noinspection PyTypeChecker
                                if name not in glb[group]['data'][albid]['genres']:
                                    # noinspection PyTypeChecker
                                    glb[group]['data'][albid]['genres'][name] = weight
                                else:
                                    # noinspection PyTypeChecker
                                    glb[group]['data'][albid]['genres'][name] += weight
                            # append tag
                            hold[group + "/tags"].append(name)
                        # Break becase every Tag should be faced only by one
                        # GENRE_FILTER
                        break

            # cut to wanted size
            for group, ielem in list(info.items()):
                while group + "/tags" in hold and len(hold[group + "/tags"]) > ielem[6]:
                    # Remove first all Sally-Tags
                    if group + "/sally" in hold and len(hold[group + "/sally"]) > 0:
                        deltag = hold[group + "/sally"].pop()
                        hold[group + "/tags"].remove(deltag)
                    else:
                        hold[group + "/tags"].pop()

            # join the information
            join_tags = cfg["lastfm_join_tags_sign"]

            def join_tags_or_not(lst):
                if join_tags:
                    return join_tags.join(lst)
                return lst

            if 1:
                used = []

                # write the major-tags
                if "major/tags" in hold and len(hold["major/tags"]) > 0:
                    metadata["grouping"] = join_tags_or_not(hold["major/tags"])
                    used.extend(hold["major/tags"])

                # write the decade-tags
                if "decade/tags" in hold and len(hold["decade/tags"]) > 0 and cfg["lastfm_use_decade_tag"]:
                    metadata["decade"] = join_tags_or_not(
                        [item.lower() for item in hold["decade/tags"]])
                    used.extend(hold["decade/tags"])

                # write country tag
                if "country/tags" in hold and len(hold["country/tags"]) > 0 and "city/tags" in hold and len(
                        hold["city/tags"]) > 0 and cfg["lastfm_use_country_tag"] and cfg["lastfm_use_city_tag"]:
                    metadata["country"] = join_tags_or_not(
                        hold["country/tags"] + hold["city/tags"])
                    used.extend(hold["country/tags"])
                    used.extend(hold["city/tags"])
                elif "country/tags" in hold and len(hold["country/tags"]) > 0 and cfg["lastfm_use_country_tag"]:
                    metadata["country"] = join_tags_or_not(
                        hold["country/tags"])
                    used.extend(hold["country/tags"])
                elif "city/tags" in hold and len(hold["city/tags"]) > 0 and cfg["lastfm_use_city_tag"]:
                    metadata["city"] = join_tags_or_not(
                        hold["city/tags"])
                    used.extend(hold["city/tags"])

                # write the mood-tags
                if "mood/tags" in hold and len(hold["mood/tags"]) > 0:
                    metadata["mood"] = join_tags_or_not(hold["mood/tags"])
                    used.extend(hold["mood/tags"])

                # write the occasion-tags
                if "occasion/tags" in hold and len(hold["occasion/tags"]) > 0:
                    metadata["occasion"] = join_tags_or_not(
                        hold["occasion/tags"])
                    used.extend(hold["occasion/tags"])

                # write the category-tags
                if "category/tags" in hold and len(hold["category/tags"]) > 0:
                    metadata["category"] = join_tags_or_not(
                        hold["category/tags"])
                    used.extend(hold["category/tags"])

                # include major tags as minor tags also copy major to minor if
                # no minor genre
                if cfg["lastfm_app_major2minor_tag"] and "major/tags" in hold and "minor/tags" in hold and len(
                        hold["minor/tags"]) > 0:
                    used.extend(hold["major/tags"])
                    used.extend(hold["minor/tags"])
                    if len(used) > 0:
                        metadata["genre"] = join_tags_or_not(
                            hold["major/tags"] + hold["minor/tags"])
                elif cfg["lastfm_app_major2minor_tag"] and "major/tags" in hold and "minor/tags" not in hold:
                    used.extend(hold["major/tags"])
                    if len(used) > 0:
                        metadata["genre"] = join_tags_or_not(
                            hold["major/tags"])
                elif "minor/tags" in hold and len(hold["minor/tags"]) > 0:
                    metadata["genre"] = join_tags_or_not(
                        hold["minor/tags"])
                    used.extend(hold["minor/tags"])
                else:
                    if "minor/tags" not in hold and "major/tags" in hold:
                        metadata["genre"] = metadata["grouping"]

                # replace blank original year with release date
                if cfg["lastfm_use_year_tag"]:
                    if "year/tags" not in hold and len(metadata["date"]) > 0:
                        metadata["originalyear"] = metadata["date"][:4]
                        if cfg["write_id3v23"]:
                            metadata["~id3:TORY"] = metadata["date"][:4]
                            # album.tagger.log.info('TORY: %r', metadata["~id3:TORY"])
                        else:
                            metadata["~id3:TDOR"] = metadata["date"][:4]
                            # album.tagger.log.info('TDOR: %r', metadata["~id3:TDOR"])
                    if metadata["originalyear"] > metadata["date"][:4]:
                        metadata["originalyear"] = metadata["date"][:4]
                    if metadata["~id3:TDOR"] > metadata["date"][:4] and not cfg["write_id3v23"]:
                        metadata["~id3:TDOR"] = metadata["date"][:4]
                    if metadata["~id3:TORY"] > metadata["date"][:4] and cfg["write_id3v23"]:
                        metadata["~id3:TORY"] = metadata["date"][:4]
                # Replace blank decades
                if "decade/tags" not in hold and len(metadata["originalyear"]) > 0 and int(
                        metadata["originalyear"]) > 1999 and cfg["lastfm_use_decade_tag"]:
                    metadata["comment:Songs-DB_Custom1"] = "20%s0s" % str(metadata["originalyear"])[2]
                elif "decade/tags" not in hold and len(metadata["originalyear"]) > 0 and int(
                        metadata["originalyear"]) < 2000 and int(metadata["originalyear"]) > 1899\
                        and cfg["lastfm_use_decade_tag"]:
                    metadata["comment:Songs-DB_Custom1"] = "19%s0s" % str(metadata["originalyear"])[2]
                elif "decade/tags" not in hold and len(metadata["originalyear"]) > 0 and int(
                        metadata["originalyear"]) < 1900 and int(metadata["originalyear"]) > 1799\
                        and cfg["lastfm_use_decade_tag"]:
                    metadata["comment:Songs-DB_Custom1"] = "18%s0s" % str(metadata["originalyear"])[2]


def _tags_downloaded(album, metadata, sally, factor, get_next, current, data, reply, error):
    q = QtCore.QUrlQuery(reply.url())
    cachetag = q.queryItemValue('artist')
    if q.queryItemValue('method') == "Track.getTopTags":
        cachetag += q.queryItemValue('method')

    try:
        try:
            intags = data.lfm[0].toptags[0].tag
        except AttributeError:
            intags = []

        # Extract just names and counts from response; apply no parsing at this stage
        tag_to_count = {}
        for tag in intags:
            # name of the tag
            name = tag.name[0].text.strip()

            # count of the tag
            try:
                count = int(tag.count[0].text.strip())
            except ValueError:
                count = 0

            tag_to_count[name] = count

        _cache[cachetag] = tag_to_count
        tags = apply_translations_and_sally(tag_to_count, sally, factor)
        _tags_finalize(album, metadata, current + tags, get_next)

        # Process any pending requests for the same URL
        if cachetag in _pending_xmlws_requests:
            pending = _pending_xmlws_requests[cachetag]
            del _pending_xmlws_requests[cachetag]
            for delayed_call in pending:
                delayed_call()

    except Exception:
        album.tagger.log.error("Problem processing downloaded tags in last.fm plus plugin: %s", traceback.format_exc())
        raise
    finally:
        # noinspection PyProtectedMember
        album._requests -= 1
        # noinspection PyProtectedMember
        album._finalize_loading(None)


def get_tags(album, metadata, artist, get_next, current, track=None, cachetag=None):
    """Get tags from an URL."""

    # Ensure config is loaded (or reloaded if has been changed)
    _lazy_load_filters(album.tagger.config.setting)

    if not cachetag:
        cachetag = artist

    queryargs = {
        "api_key": album.tagger.config.setting["lastfm_api_key"],
        "artist": artist,
        "method": "Artist.getTopTags",
    }

    sally = 2
    if album.tagger.config.setting["lastfm_artist_tag_us_ex"]:
        sally = 1
    factor = album.tagger.config.setting["lastfm_artist_tags_weight"] / 100.0
    if track:
        queryargs["method"] = "Track.getTopTags"
        queryargs["track"] = track
        cachetag += track
        sally = 0
        factor = 1.0

    if cachetag in _cache:
        tags = apply_translations_and_sally(_cache[cachetag], sally, factor)
        _tags_finalize(album, metadata, current + tags, get_next)
    else:

        # If we have already sent a request for this URL, delay this call until later
        if cachetag in _pending_xmlws_requests:
            _pending_xmlws_requests[cachetag].append(
                partial(get_tags, album, metadata, artist, get_next, current, track=track, cachetag=cachetag))
        else:
            _pending_xmlws_requests[cachetag] = []
            # noinspection PyProtectedMember
            album._requests += 1
            album.tagger.webservice.get(LASTFM_HOST, LASTFM_PORT, LASTFM_PATH,
                                        partial(_tags_downloaded, album, metadata, sally, factor, get_next, current),
                                        parse_response_type="xml", queryargs=queryargs, priority=True, important=True)


def process_track(album, metadata, release, track):
    tagger = album.tagger
    use_track_tags = tagger.config.setting["lastfm_use_track_tags"]
    use_artist_tags = tagger.config.setting["lastfm_artist_tag_us_ex"] or tagger.config.setting[
        "lastfm_artist_tag_us_yes"]

    if use_track_tags or use_artist_tags:
        artist = metadata["artist"]
        title = metadata["title"]
        if artist:
            if use_artist_tags:
                get_artist_tags_func = partial(get_tags, album, metadata, artist, None)
            else:
                get_artist_tags_func = None
            if title and use_track_tags:
                get_tags(album, metadata, artist, get_artist_tags_func, [], track=title)
            elif get_artist_tags_func:
                get_artist_tags_func([])


class LastfmOptionsPage(OptionsPage):
    NAME = "lastfmplus"
    TITLE = "Last.fm.Plus"
    PARENT = "plugins"

    options = [
        TextOption("setting", "lastfm_api_key", ""),
        IntOption("setting", "lastfm_max_minor_tags", 5),
        IntOption("setting", "lastfm_max_group_tags", 3),
        IntOption("setting", "lastfm_max_mood_tags", 5),
        IntOption("setting", "lastfm_max_occasion_tags", 5),
        IntOption("setting", "lastfm_max_category_tags", 5),
        BoolOption("setting", "lastfm_use_country_tag", False),
        BoolOption("setting", "lastfm_use_city_tag", False),
        BoolOption("setting", "lastfm_use_decade_tag", False),
        BoolOption("setting", "lastfm_use_year_tag", False),
        TextOption("setting", "lastfm_join_tags_sign", ""),
        BoolOption("setting", "lastfm_app_major2minor_tag", True),
        BoolOption("setting", "lastfm_use_track_tags", True),
        IntOption("setting", "lastfm_min_tracktag_weight", 5),
        IntOption("setting", "lastfm_max_tracktag_drop", 90),
        BoolOption("setting", "lastfm_artist_tag_us_no", False),
        BoolOption("setting", "lastfm_artist_tag_us_ex", True),
        BoolOption("setting", "lastfm_artist_tag_us_yes", False),
        IntOption("setting", "lastfm_artist_tags_weight", 95),
        IntOption("setting", "lastfm_min_artisttag_weight", 10),
        IntOption("setting", "lastfm_max_artisttag_drop", 80),
        TextOption("setting", "lastfm_genre_major", ",".join(GENRE_FILTER["major"]).lower()),
        TextOption("setting", "lastfm_genre_minor", ",".join(GENRE_FILTER["minor"]).lower()),
        TextOption("setting", "lastfm_genre_decade", ", ".join(GENRE_FILTER["decade"]).lower()),
        TextOption("setting", "lastfm_genre_year", ", ".join(GENRE_FILTER["year"]).lower()),
        TextOption("setting", "lastfm_genre_occasion", ", ".join(GENRE_FILTER["occasion"]).lower()),
        TextOption("setting", "lastfm_genre_category", ", ".join(GENRE_FILTER["category"]).lower()),
        TextOption("setting", "lastfm_genre_country", ", ".join(GENRE_FILTER["country"]).lower()),
        TextOption("setting", "lastfm_genre_city", ", ".join(GENRE_FILTER["city"]).lower()),
        TextOption("setting", "lastfm_genre_mood", ",".join(GENRE_FILTER["mood"]).lower()),
        TextOption("setting", "lastfm_genre_translations",
                   "\n".join(["%s,%s" % (k, v) for k, v in list(GENRE_FILTER["translate"].items())]).lower())
    ]

    def __init__(self, parent=None):
        super(LastfmOptionsPage, self).__init__(parent)
        self.ui = UiLastfmOptionsPage()
        self.ui.setup_ui(self)
        # TODO Not yet implemented properly
        # self.ui.check_translation_list.clicked.connect(self.check_translations)
        self.ui.check_word_lists.clicked.connect(self.check_words)
        self.ui.load_default_lists.clicked.connect(self.load_defaults)
        self.ui.filter_report.clicked.connect(self.create_report)

    # function to check all translations and make sure a corresponding word
    # exists in word lists, notify in message translations pointing nowhere.
    #    def check_translations(self):
    #        cfg = self.config.setting
    #        translations = (cfg["lastfm_genre_translations"].replace("\n", "|"))
    #        tr2 = list(item for item in translations.split('|'))
    #        wordlists = (cfg["lastfm_genre_major"] + cfg["lastfm_genre_minor"] + cfg["lastfm_genre_country"] +
    #        cfg["lastfm_genre_occasion"] + cfg["lastfm_genre_mood"] + cfg["lastfm_genre_decade"] +
    #        cfg["lastfm_genre_year"] + cfg["lastfm_genre_category"])
    #        # TODO need to check to see if translations are in wordlists
    #        QtGui.QMessageBox.information(
    #            self, self.tr("QMessageBox.showInformation()"), ",".join(tr2))

    # function to check that word lists contain no duplicate entries, notify
    # in message duplicates and which lists they appear in
    def check_words(self):
        # cfg = self.config.setting
        # Create a set for each option cfg option

        word_sets = {
            "Major": set(str(self.ui.genre_major.text()).split(",")),
            "Minor": set(str(self.ui.genre_minor.text()).split(",")),
            "Countries": set(str(self.ui.genre_country.text()).split(",")),
            "Cities": set(str(self.ui.genre_city.text()).split(",")),
            "Moods": set(str(self.ui.genre_mood.text()).split(",")),
            "Occasions": set(str(self.ui.genre_occasion.text()).split(",")),
            "Decades": set(str(self.ui.genre_decade.text()).split(",")),
            "Years": set(str(self.ui.genre_year.text()).split(",")),
            "Categories": set(str(self.ui.genre_category.text()).split(","))
        }

        text = []
        duplicates = {}

        for name, words in word_sets.items():
            for word in words:
                word = word.strip().title()
                duplicates.setdefault(word, []).append(name)

        for word, names in duplicates.items():
            if len(names) > 1:
                names = "%s and %s" % (", ".join(names[:-1]), names.pop())
                text.append('"%s" in %s lists.' % (word, names))

        if not text:
            text = "No issues found."
        else:
            text = "\n\n".join(text)

        # Display results in information box
        # QtGui.QMessageBox.information(self, self.tr("QMessageBox.showInformation()"), text)

    # load/reload defaults
    def load_defaults(self):
        self.ui.genre_major.setText(", ".join(GENRE_FILTER["major"]))
        self.ui.genre_minor.setText(", ".join(GENRE_FILTER["minor"]))
        self.ui.genre_decade.setText(", ".join(GENRE_FILTER["decade"]))
        self.ui.genre_country.setText(", ".join(GENRE_FILTER["country"]))
        self.ui.genre_city.setText(", ".join(GENRE_FILTER["city"]))
        self.ui.genre_year.setText(", ".join(GENRE_FILTER["year"]))
        self.ui.genre_occasion.setText(", ".join(GENRE_FILTER["occasion"]))
        self.ui.genre_category.setText(", ".join(GENRE_FILTER["category"]))
        self.ui.genre_mood.setText(", ".join(GENRE_FILTER["mood"]))
        self.ui.genre_translations.setText(
            "00s, 2000s\n10s, 1910s\n1920's, 1920s\n1930's, 1930s\n1940's, 1940s\n1950's, 1950s\n1960's, "
            "1960s\n1970's, 1970s\n1980's, 1980s\n1990's, 1990s\n2-tone, 2 tone\n20's, 1920s\n2000's, 2000s\n2000s, "
            "2000s\n20s, 1920s\n20th century classical, classical\n30's, 1930s\n30s, 1930s\n3rd wave ska revival, "
            "ska\n40's, 1940s\n40s, 1940s\n50's, 1950s\n50s, 1950s\n60's, 1960s\n60s, 1960s\n70's, 1970s\n70s, "
            "1970s\n80's, 1980s\n80s, 1980s\n90's, 1990s\n90s, 1990s\na capella, a cappella\nabstract-hip-hop, "
            "hip-hop\nacapella, a cappella\nacid-rock, acid rock\nafrica, african\naggresive, angry\naggressive, "
            "angry\nalone, lonely\nalready-dead, deceased\nalt rock, alternative rock\nalt-country, alternative "
            "country\nalternative  punk, punk\nalternative dance, dance\nalternative hip-hop, hip-hop\nalternative "
            "pop-rock, pop rock\nalternative punk, punk\nalternative rap, rap\nambient-techno, ambient\namericain, "
            "american\namericana, american\nanimal-songs, animal songs\nanimals, animal songs\nanti-war, "
            "protest\narena rock, rock\natmospheric-drum-and-bass, drum and bass\nau, australian\naussie hip hop, "
            "aussie hip-hop\naussie hiphop, aussie hip-hop\naussie rock, australian\naussie, australian\naussie-rock, "
            "rock\naustralia, australian\naustralian aboriginal, world\naustralian country, country\naustralian hip "
            "hop, aussie hip-hop\naustralian hip-hop, aussie hip-hop\naustralian rap, aussie hip-hop\naustralian "
            "rock, rock\naustralian-music, australian\naustralianica, australian\naustralicana, australian\naustria, "
            "austrian\navantgarde, avant-garde\nbakersfield-sound, bakersfield\nbaroque pop, baroque\nbeach music, "
            "beach\nbeat, beats\nbelgian music, belgian\nbelgian-music, belgian\nbelgium, belgian\nbhangra, "
            "indian\nbig beat, beats\nbigbeat, beats\nbittersweet, cynical\nblack metal, doom metal\nblue, "
            "sad\nblues guitar, blues\nblues-rock, blues rock\nbluesrock, blues rock\nbollywood, indian\nboogie, "
            "boogie woogie\nboogiewoogieflu, boogie woogie\nbrazil, brazilian\nbreakbeats, breakbeat\nbreaks artists, "
            "breakbeat\nbrit, british\nbrit-pop, brit pop\nbrit-rock, brit rock\nbritish blues, blues\nbritish punk, "
            "punk\nbritish rap, rap\nbritish rock, brit rock\nbritish-folk, folk\nbritpop, brit pop\nbritrock, "
            "brit rock\nbroken beat, breakbeat\nbrutal-death-metal, doom metal\nbubblegum, bubblegum pop\nbuddha bar, "
            "chillout\ncalming, relaxed\ncanada, canadian\ncha-cha, cha cha\ncha-cha-cha, cha cha\nchicago blues, "
            "blues\nchildren, kids\nchildrens music, kids\nchildrens, kids\nchill out, chillout\nchill-out, "
            "chillout\nchilled, chill\nchillhouse, chill\nchillin, hanging out\nchristian, gospel\nchina, "
            "chinese\nclasica, classical\nclassic blues, blues\nclassic jazz, jazz\nclassic metal, metal\nclassic "
            "pop, pop\nclassic punk, punk\nclassic roots reggae, roots reggae\nclassic soul, soul\nclassic-hip-hop, "
            "hip-hop\nclassical crossover, classical\nclassical music, classical\nclassics, classic tunes\nclassique, "
            "classical\nclub-dance, dance\nclub-house, house\nclub-music, club\ncollegiate acappella, "
            "a cappella\ncomedy rock, humour\ncomedy, humour\ncomposer, composers\nconscious reggae, "
            "reggae\ncontemporary classical, classical\ncontemporary gospel, gospel\ncontemporary jazz, "
            "jazz\ncontemporary reggae, reggae\ncool-covers, covers\ncountry folk, country\ncountry soul, "
            "country\ncountry-divas, country\ncountry-female, country\ncountry-legends, country\ncountry-pop, "
            "country pop\ncountry-rock, country rock\ncover, covers\ncover-song, covers\ncover-songs, covers\ncowboy, "
            "country\ncowhat-fav, country\ncowhat-hero, country\ncuba, cuban\ncyberpunk, punk\nd'n'b, "
            "drum and bass\ndance party, party\ndance-punk, punk\ndance-rock, rock\ndancefloor, "
            "dance\ndancehall-reggae, dancehall\ndancing, dance\ndark-psy, psytrance\ndark-psytrance, "
            "psytrance\ndarkpsy, dark ambient\ndeath metal, doom metal\ndeathcore, thrash metal\ndeep house, "
            "house\ndeep-soul, soul\ndeepsoul, soul\ndepressing, depressed\ndepressive, depressed \ndeutsch, "
            "german\ndisco-funk, disco\ndisco-house, disco\ndiva, divas\ndj mix, dj\ndnb, drum and bass\ndope, "
            "drugs\ndownbeat, downtempo\ndream dance, trance\ndream trance, trance\ndrill 'n' bass, "
            "drum and bass\ndrill and bass, drum and bass\ndrill n bass, drum and bass\ndrill-n-bass, "
            "drum and bass\ndrillandbass, drum and bass\ndrinking songs, drinking\ndriving-music, driving\ndrum 'n' "
            "bass, drum and bass\ndrum n bass, drum and bass\ndrum'n'bass, drum and bass\ndrum, drums\ndrum-n-bass, "
            "drum and bass\ndrumandbass, drum and bass\ndub-u, dub\ndub-u-dub, dub\ndub-wise, dub\nduet, duets\nduo, "
            "duets\ndutch artists, dutch\ndutch rock, rock\ndutch-bands, dutch\ndutch-sound, dutch\nearly reggae, "
            "reggae\neasy, easy listening\negypt, egyptian\neighties, 1980s\nelectro dub, electro\nelectro funk, "
            "electro\nelectro house, house\nelectro rock, electro\nelectro-pop, electro\nelectroclash, "
            "electro\nelectrofunk, electro\nelectrohouse, house\nelectronic, electronica\nelectronic-rock, "
            "rock\nelectronicadance, dance\nelectropop, electro pop\nelectropunk, punk\nelegant, stylish\nelektro, "
            "electro\nelevator, elevator music\nemotive, emotional\nenergy, energetic\nengland, british\nenglish, "
            "british\nenraged, angry\nepic-trance, trance\nethnic fusion, ethnic\neuro-dance, eurodance\neuro-pop, "
            "europop\neuro-trance, trance\neurotrance, trance\neurovision, eurodance\nexperimental-rock, "
            "experimental\nfair dinkum australian mate, australian\nfeel good music, feel good\nfeelgood, "
            "feel good\nfemale artists, female\nfemale country, country\nfemale fronted, female\nfemale singers, "
            "female\nfemale vocalist, female vocalists\nfemale-vocal, female vocalists\nfemale-vocals, "
            "female vocalists\nfemale-voices, female vocalists\nfield recording, field recordings\nfilm, "
            "film score\nfilm-score, film score\nfingerstyle guitar, fingerstyle\nfinland, finnish\nfinnish-metal, "
            "metal\nflamenco rumba, rumba\nfolk-jazz, folk jazz\nfolk-pop, folk pop\nfolk-rock, folk rock\nfolkrock, "
            "folk rock\nfrancais, french\nfrance, french\nfreestyle, electronica\nfull on, energetic\nfull-on, "
            "energetic\nfull-on-psychedelic-trance, psytrance\nfull-on-trance, trance\nfullon, intense \nfuneral, "
            "death\nfunky breaks, breaks\nfunky house, house\nfunny, humorous\ngabber, hardcore\ngeneral pop, "
            "pop\ngeneral rock, rock\ngentle, smooth\ngermany, german\ngirl-band, girl group\ngirl-group, "
            "girl group\ngirl-groups, girl group\ngirl-power, girl group\ngirls, girl group\nglam metal, "
            "glam rock\nglam, glam rock\ngloomy, depressed\ngoa classic, goa trance\ngoa, goa trance\ngoa-psy-trance, "
            "psytrance\ngoatrance, trance\ngolden oldies, oldies\ngoth rock, gothic rock\ngoth, gothic\ngothic doom "
            "metal, gothic metal\ngreat-lyricists, great lyrics\ngreat-lyrics, great lyrics\ngrime, "
            "dubstep\ngregorian chant, gregorian\ngrock 'n' roll, rock and roll\ngroovin, groovy\ngrunge rock, "
            "grunge\nguitar god, guitar\nguitar gods, guitar\nguitar hero, guitar\nguitar rock, rock\nguitar-solo, "
            "guitar solo\nguitar-virtuoso, guitarist\nhair metal, glam rock\nhanging-out, hanging out\nhappiness, "
            "happy\nhappy thoughts, happy\nhard dance, dance\nhard house, house\nhard-trance, "
            "trance\nhardcore-techno, techno\nhawaii, hawaiian\nheartbreak, heartache\nheavy rock, "
            "hard rock\nhilarious, humorous\nhip hop, hip-hop\nhip-hop and rap, hip-hop\nhip-hoprap, hip-hop\nhiphop, "
            "hip-hop\nhippie, stoner rock\nhope, hopeful\nhorrorcore, thrash metal\nhorrorpunk, horror punk\nhumor, "
            "humour\nindia, indian\nindie electronic, electronica\nindietronica, electronica\ninspirational, "
            "inspiring\ninstrumental pop, instrumental \niran, iranian\nireland, irish\nisrael, israeli\nitaly, "
            "italian\njam band, jam\njamaica, jamaican\njamaican ska, ska\njamaician, jamaican\njamaican-artists, "
            "jamaican\njammer, jam\njazz blues, jazz\njazz funk, jazz\njazz hop, jazz\njazz piano, jazz\njpop, "
            "j-pop\njrock, j-rock\njazz rock, jazz\njazzy, jazz\njump blues, blues\nkiwi, new zealand\nlaid back, "
            "easy listening\nlatin rock, latin\nlatino, latin\nle rap france, french rap\nlegend, legends\nlegendary, "
            "legends\nlekker ska, ska\nlions-reggae-dancehall, dancehall\nlistless, irritated\nlively, "
            "energetic\nlove metal, metal\nlove song, romantic\nlove-songs, lovesongs\nlovely, "
            "beautiful\nmade-in-usa, american\nmakes me happy, happy\nmale country, country\nmale groups, male\nmale "
            "rock, male\nmale solo artists, male\nmale vocalist, male vocalists\nmale-vocal, "
            "male vocalists\nmale-vocals, male vocalists\nmarijuana, drugs\nmelancholic days, melancholy\nmelodic "
            "death metal, doom metal\nmelodic hardcore, hardcore\nmelodic metal, metal\nmelodic metalcore, "
            "metal\nmelodic punk, punk\nmelodic trance, trance\nmetalcore, thrash metal\nmetro downtempo, "
            "downtempo\nmetro reggae, reggae\nmiddle east, middle eastern\nminimal techno, techno\nmood, "
            "moody\nmorning, wake up\nmoses reggae, reggae\nmovie, soundtracks\nmovie-score, "
            "soundtracks\nmovie-score-composers, composers\nmovie-soundtrack, soundtracks\nmusical, "
            "musicals\nmusical-theatre, musicals\nneder rock, rock \nnederland, dutch\nnederlands, "
            "dutch\nnederlandse-muziek, dutch\nnederlandstalig, dutch\nnederpop, pop\nnederrock, rock\nnederska, "
            "ska\nnedertop, dutch\nneo prog, progressive\nneo progressive rock, progressive rock\nneo progressive, "
            "progressive\nneo psychedelia, psychedelic\nneo soul, soul\nnerd rock, rock\nnetherlands, "
            "dutch\nneurofunk, funk\nnew rave, rave\nnew school breaks, breaks \nnew school hardcore, hardcore\nnew "
            "traditionalist country, traditional country\nnice elevator music, elevator music\nnight, "
            "late night\nnight-music, late night\nnoise pop, pop\nnoise rock, rock\nnorway, norwegian\nnostalgic, "
            "nostalgia\nnu breaks, breaks\nnu jazz, jazz\nnu skool breaks, breaks \nnu-metal, nu metal\nnumber-songs, "
            "number songs\nnumbers, number songs\nnumetal, metal\nnz, new zealand\nold country, country\nold school "
            "hardcore, hardcore \nold school hip-hop, hip-hop\nold school reggae, reggae\nold school soul, "
            "soul\nold-favorites, oldie\nold-skool, old school\nold-timey, oldie\noldschool, old school\none hit "
            "wonder, one hit wonders\noptimistic, positive\noutlaw country, country\noz hip hop, aussie hip-hop\noz "
            "rock, rock\noz, australian\nozzie, australian\npancaribbean, caribbean\nparodies, parody\nparty-groovin, "
            "party\nparty-music, party\nparty-time, party\npiano rock, piano\npolitical punk, punk\npolitical rap, "
            "rap\npool party, party\npop country, country pop\npop music, pop\npop rap, rap\npop-rap, rap\npop-rock, "
            "pop rock\npop-soul, pop soul\npoprock, pop rock\nportugal, portuguese\npositive-vibrations, "
            "positive\npost grunge, grunge\npost hardcore, hardcore\npost-grunge, grunge\npost-hardcore, "
            "hardcore\npost-punk, post punk\npost-rock, post rock\npostrock, post rock\npower ballad, ballad\npower "
            "ballads, ballad\npower metal, metal\nprog rock, progressive rock\nprogressive breaks, "
            "breaks\nprogressive house, house\nprogressive metal, nu metal\nprogressive psytrance, psytrance "
            "\nprogressive trance, psytrance\nproto-punk, punk\npsy, psytrance\npsy-trance, psytrance\npsybient, "
            "ambient\npsych folk, psychedelic folk\npsych, psytrance\npsychadelic, psychedelic\npsychedelia, "
            "psychedelic\npsychedelic pop, psychedelic\npsychedelic trance, psytrance\npsychill, psytrance\npsycho, "
            "insane\npsytrance artists, psytrance\npub rock, rock \npunk blues, punk\npunk caberet, punk\npunk "
            "favorites, punk \npunk pop, punk\npunk revival, punk\npunkabilly, punk\npunkrock, punk rock\nqueer, "
            "quirky\nquiet, relaxed\nr and b, r&b\nr'n'b, r&b\nr-n-b, r&b\nraggae, reggae\nrap and hip-hop, "
            "rap\nrap hip-hop, rap\nrap rock, rap\nrapcore, rap metal\nrasta, rastafarian\nrastafari, "
            "rastafarian\nreal hip-hop, hip-hop\nreegae, reggae\nreggae and dub, reggae\nreggae broeder, "
            "reggae\nreggae dub ska, reggae\nreggae roots, roots reggae\nreggae-pop, reggae pop\nreggea, "
            "reggae\nrelax, relaxed\nrelaxing, relaxed\nrhythm and blues, r&b\nrnb, r&b\nroad-trip, driving\nrock "
            "ballad, ballad\nrock ballads, ballad\nrock n roll, rock and roll\nrock pop, pop rock\nrock roll, "
            "rock and roll\nrock'n'roll, rock and roll\nrock-n-roll, rock and roll\nrocknroll, "
            "rock and roll\nrockpop, pop rock\nromance, romantic\nromantic-tension, romantic\nroots and culture, "
            "roots\nroots rock, rock\nrootsreggae, roots reggae \nrussian alternative, russian\nsad-songs, "
            "sad\nsample, samples\nsaturday night, party\nsax, saxophone\nscotland, scottish\nseden, "
            "swedish\nsensual, passionate\nsing along, sing-alongs\nsing alongs, sing-alongs\nsing-along, "
            "sing-alongs\nsinger-songwriters, singer-songwriter\nsingersongwriter, singer-songwriter\nsixties, "
            "1960s\nska revival, ska \nska-punk, ska punk\nskacore, ska\nskate punk, punk\nskinhead reggae, "
            "reggae\nsleepy, sleep\nslow jams, slow jam\nsmooth soul, soul\nsoft, smooth\nsolo country acts, "
            "country\nsolo instrumental, solo instrumentals\nsoothing, smooth\nsoulful drum and bass, "
            "drum and bass\nsoundtrack, soundtracks\nsouth africa, african\nsouth african, african\nsouthern rap, "
            "rap\nsouthern soul, soul\nspain, spanish\nspeed metal, metal\nspeed, drugs\nspirituals, "
            "spiritual\nspliff, drugs\nstoner, stoner rock\nstreet punk, punk\nsuicide, death\nsuicide, "
            "suicidal\nsummertime, summer\nsun-is-shining, sunny\nsunshine pop, pop\nsuper pop, pop\nsurf, "
            "surf rock\nswamp blues, swamp rock\nswamp, swamp rock\nsweden, swedish\nswedish metal, metal\nsymphonic "
            "power metal, symphonic metal\nsynthpop, synth pop\ntexas blues, blues\ntexas country, country\nthird "
            "wave ska revival, ska\nthird wave ska, ska\ntraditional-ska, ska\ntrancytune, trance\ntranquility, "
            "peaceful\ntribal house, tribal\ntribal rock, tribal\ntrip hop, trip-hop\ntriphop, trip-hop\ntwo tone, "
            "2 tone\ntwo-tone, 2 tone\nuk hip-hop, hip-hop\nuk, british\nunited kingdom, british\nunited states, "
            "american\nuntimely-death, deceased\nuplifting trance, trance\nus, american\nusa, american\nvocal house, "
            "house\nvocal jazz, jazz vocal\nvocal pop, pop\nvocal, vocals\nwales, welsh\nweed, drugs\nwest-coast, "
            "westcoast\nworld music, world\nxmas, christmas\n")

    def import_newlist(self):
        # noinspection PyUnresolvedReferences
        file_name = QtGui.QFileDialog.getOpenFileName(self,
                                                      self.tr("QFileDialog.getOpenFileName()"),
                                                      self.ui.fileName.text(),
                                                      self.tr("All Files (*);;Text Files (*.txt)"))
        if not file_name.isEmpty():
            # noinspection PyUnresolvedReferences
            self.ui.fileName.setText(file_name)
        columns = []
        lists = {}
        with open(file_name) as f:
            for line in f:
                data = line.rstrip('\r\n').split(",")
                if not columns:  # first line
                    columns = tuple(data)
                    for column in columns:
                        lists[column] = []
                else:  # data lines
                    for column, value in zip(columns, data):
                        if value:
                            lists[column].append(value)

        self.ui.genre_major.setText(', '.join(lists['Major']))
        self.ui.genre_minor.setText(', '.join(lists['Minor']))
        self.ui.genre_country.setText(', '.join(lists['Country']))
        self.ui.genre_city.setText(', '.join(lists['City']))
        self.ui.genre_decade.setText(', '.join(lists['Decade']))
        self.ui.genre_mood.setText(', '.join(lists['Mood']))
        self.ui.genre_occasion.setText(', '.join(lists['Occasion']))

    # Function to create simple report window.  Could do a count of values in
    # each section and the amount of translations. Total tags being scanned
    # for.
    def create_report(self):
        cfg = self.config.setting
        options = [
            ('lastfm_genre_major', 'Major Genre Terms'),
            ('lastfm_genre_minor', 'Minor Genre Terms'),
            ('lastfm_genre_country', 'Country Terms'),
            ('lastfm_genre_city', 'City Terms'),
            ('lastfm_genre_mood', 'Mood Terms'),
            ('lastfm_genre_occasion', 'Occasions Terms'),
            ('lastfm_genre_decade', 'Decade Terms'),
            ('lastfm_genre_year', 'Year Terms'),
            ('lastfm_genre_category', 'Category Terms'),
            ('lastfm_genre_translations', 'Translation Terms'),
        ]
        text = []
        for name, label in options:
            nterms = cfg[name].count(',') + 1
            if nterms:
                text.append(" &bull; %d %s" % (nterms, label))
        if not text:
            text = "No terms found"
        else:
            text = "You have a total of:<br />" + "<br />".join(text) + ""
        # Display results in information box
        # QtGui.QMessageBox.information(self, self.tr("QMessageBox.showInformation()"), text)

    def load(self):
        # general
        cfg = self.config.setting
        self.ui.api_key.setText(cfg["lastfm_api_key"])
        self.ui.max_minor_tags.setValue(cfg["lastfm_max_minor_tags"])
        self.ui.max_group_tags.setValue(cfg["lastfm_max_group_tags"])
        self.ui.max_mood_tags.setValue(cfg["lastfm_max_mood_tags"])
        self.ui.max_occasion_tags.setValue(cfg["lastfm_max_occasion_tags"])
        self.ui.max_category_tags.setValue(cfg["lastfm_max_category_tags"])
        self.ui.use_country_tag.setChecked(cfg["lastfm_use_country_tag"])
        self.ui.use_city_tag.setChecked(cfg["lastfm_use_city_tag"])
        self.ui.use_decade_tag.setChecked(cfg["lastfm_use_decade_tag"])
        self.ui.use_year_tag.setChecked(cfg["lastfm_use_year_tag"])
        self.ui.join_tags_sign.setText(cfg["lastfm_join_tags_sign"])
        self.ui.app_major2minor_tag.setChecked(cfg["lastfm_app_major2minor_tag"])
        self.ui.use_track_tags.setChecked(cfg["lastfm_use_track_tags"])
        self.ui.min_tracktag_weight.setValue(cfg["lastfm_min_tracktag_weight"])
        self.ui.max_tracktag_drop.setValue(cfg["lastfm_max_tracktag_drop"])
        self.ui.artist_tag_us_no.setChecked(cfg["lastfm_artist_tag_us_no"])
        self.ui.artist_tag_us_ex.setChecked(cfg["lastfm_artist_tag_us_ex"])
        self.ui.artist_tag_us_yes.setChecked(cfg["lastfm_artist_tag_us_yes"])
        self.ui.artist_tags_weight.setValue(cfg["lastfm_artist_tags_weight"])
        self.ui.min_artisttag_weight.setValue(cfg["lastfm_min_artisttag_weight"])
        self.ui.max_artisttag_drop.setValue(cfg["lastfm_max_artisttag_drop"])
        self.ui.genre_major.setText(cfg["lastfm_genre_major"].replace(",", ", "))
        self.ui.genre_minor.setText(cfg["lastfm_genre_minor"].replace(",", ", "))
        self.ui.genre_decade.setText(cfg["lastfm_genre_decade"].replace(",", ", "))
        self.ui.genre_country.setText(cfg["lastfm_genre_country"].replace(",", ", "))
        self.ui.genre_city.setText(cfg["lastfm_genre_city"].replace(",", ", "))
        self.ui.genre_year.setText(cfg["lastfm_genre_year"].replace(",", ", "))
        self.ui.genre_occasion.setText(cfg["lastfm_genre_occasion"].replace(",", ", "))
        self.ui.genre_category.setText(cfg["lastfm_genre_category"].replace(",", ", "))
        self.ui.genre_year.setText(cfg["lastfm_genre_year"].replace(",", ", "))
        self.ui.genre_mood.setText(cfg["lastfm_genre_mood"].replace(",", ", "))
        self.ui.genre_translations.setText(cfg["lastfm_genre_translations"].replace(",", ", "))

    def save(self):
        self.config.setting["lastfm_api_key"] = self.ui.api_key.text()
        self.config.setting["lastfm_max_minor_tags"] = self.ui.max_minor_tags.value()
        self.config.setting["lastfm_max_group_tags"] = self.ui.max_group_tags.value()
        self.config.setting["lastfm_max_mood_tags"] = self.ui.max_mood_tags.value()
        self.config.setting["lastfm_max_occasion_tags"] = self.ui.max_occasion_tags.value()
        self.config.setting["lastfm_max_category_tags"] = self.ui.max_category_tags.value()
        self.config.setting["lastfm_use_country_tag"] = self.ui.use_country_tag.isChecked()
        self.config.setting["lastfm_use_city_tag"] = self.ui.use_city_tag.isChecked()
        self.config.setting["lastfm_use_decade_tag"] = self.ui.use_decade_tag.isChecked()
        self.config.setting["lastfm_use_year_tag"] = self.ui.use_year_tag.isChecked()
        self.config.setting["lastfm_join_tags_sign"] = self.ui.join_tags_sign.text()
        self.config.setting["lastfm_app_major2minor_tag"] = self.ui.app_major2minor_tag.isChecked()
        self.config.setting["lastfm_use_track_tags"] = self.ui.use_track_tags.isChecked()
        self.config.setting["lastfm_min_tracktag_weight"] = self.ui.min_tracktag_weight.value()
        self.config.setting["lastfm_max_tracktag_drop"] = self.ui.max_tracktag_drop.value()
        self.config.setting["lastfm_artist_tag_us_no"] = self.ui.artist_tag_us_no.isChecked()
        self.config.setting["lastfm_artist_tag_us_ex"] = self.ui.artist_tag_us_ex.isChecked()
        self.config.setting["lastfm_artist_tag_us_yes"] = self.ui.artist_tag_us_yes.isChecked()
        self.config.setting["lastfm_artist_tags_weight"] = self.ui.artist_tags_weight.value()
        self.config.setting["lastfm_min_artisttag_weight"] = self.ui.min_artisttag_weight.value()
        self.config.setting["lastfm_max_artisttag_drop"] = self.ui.max_artisttag_drop.value()

        # parse littlebit the text-inputs
        tmp0 = {}
        tmp1 = [tmp0.setdefault(i.strip(), i.strip())
                for i in self.ui.genre_major.text().lower().split(",") if i not in tmp0]
        tmp1.sort()
        self.config.setting["lastfm_genre_major"] = ",".join(tmp1)
        tmp0 = {}
        tmp1 = [tmp0.setdefault(i.strip(), i.strip())
                for i in self.ui.genre_minor.text().lower().split(",") if i not in tmp0]
        tmp1.sort()
        self.config.setting["lastfm_genre_minor"] = ",".join(tmp1)
        tmp0 = {}
        tmp1 = [tmp0.setdefault(i.strip(), i.strip())
                for i in self.ui.genre_decade.text().lower().split(",") if i not in tmp0]
        tmp1.sort()
        self.config.setting["lastfm_genre_decade"] = ",".join(tmp1)
        tmp0 = {}
        tmp1 = [tmp0.setdefault(i.strip(), i.strip())
                for i in self.ui.genre_year.text().lower().split(",") if i not in tmp0]
        tmp1.sort()
        self.config.setting["lastfm_genre_year"] = ",".join(tmp1)
        tmp0 = {}
        tmp1 = [tmp0.setdefault(i.strip(), i.strip())
                for i in self.ui.genre_country.text().lower().split(",") if i not in tmp0]
        tmp1.sort()
        self.config.setting["lastfm_genre_country"] = ",".join(tmp1)
        tmp0 = {}
        tmp1 = [tmp0.setdefault(i.strip(), i.strip())
                for i in self.ui.genre_city.text().lower().split(",") if i not in tmp0]
        tmp1.sort()
        self.config.setting["lastfm_genre_city"] = ",".join(tmp1)
        tmp0 = {}
        tmp1 = [tmp0.setdefault(i.strip(), i.strip())
                for i in self.ui.genre_occasion.text().lower().split(",") if i not in tmp0]
        tmp1.sort()
        self.config.setting["lastfm_genre_occasion"] = ",".join(tmp1)
        tmp0 = {}
        tmp1 = [tmp0.setdefault(i.strip(), i.strip())
                for i in self.ui.genre_category.text().lower().split(",") if i not in tmp0]
        tmp1.sort()
        self.config.setting["lastfm_genre_category"] = ",".join(tmp1)
        tmp0 = {}
        tmp1 = [tmp0.setdefault(i.strip(), i.strip())
                for i in self.ui.genre_mood.text().lower().split(",") if i not in tmp0]
        tmp1.sort()
        self.config.setting["lastfm_genre_mood"] = ",".join(tmp1)

        trans = {}
        tmp0 = self.ui.genre_translations.toPlainText().lower().split("\n")
        for tmp1 in tmp0:
            tmp2 = tmp1.split(',')
            if len(tmp2) == 2:
                tmp2[0] = tmp2[0].strip()
                tmp2[1] = tmp2[1].strip()
                if len(tmp2[0]) < 1 or len(tmp2[1]) < 1:
                    continue
                if tmp2[0] in trans and trans[tmp2[0]] != tmp2[1]:
                    del trans[tmp2[0]]
                elif not tmp2[0] in trans:
                    trans[tmp2[0]] = tmp2[1]

        tmp3 = sorted(trans.items())

        self.config.setting["lastfm_genre_translations"] = "\n".join(["%s,%s" % (k, v) for k, v in tmp3])
        GENRE_FILTER["_loaded_"] = False


register_track_metadata_processor(process_track)
register_options_page(LastfmOptionsPage)
