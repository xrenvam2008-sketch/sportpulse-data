#!/usr/bin/env python3
import re, urllib.request
from pathlib import Path

URL="https://raw.githubusercontent.com/junguler/m3u-radio-music-playlists/main/russian.m3u"
OUT=Path("iptv/russian_radio_RU.m3u")

WORDS=[
("Komsomolskaya Pravda","Комсомольская Правда"),("Russkoe Radio","Русское Радио"),
("Russian Rock","Русский Рок"),("Radio Record","Радио Рекорд"),("Radio RECORD","Радио Рекорд"),
("Radio Relax","Радио Relax"),("Radio Vera","Радио Вера"),("Radio Maximum","Радио Maximum"),
("Radio DFM","Радио DFM"),("Europa Plus","Европа Плюс"),("Retro Nizhniy Novgorod","Ретро Нижний Новгород"),
("Nizhniy Novgorod","Нижний Новгород"),("Novosibirsk","Новосибирск"),("Petersburg","Петербург"),
("VostokFM","Восток FM"),("Avtoradio","Авторадио"),("Humor FM","Юмор FM"),
("Radio Center","Радио Центр"),("Radio Radonezh","Радио Радонеж"),("Radio Borneo","Радио Борнео"),
("Radio Vorona","Радио Ворона"),("Radio Caprice","Радио Caprice"),("Radio Jazz","Радио Jazz"),
("Old School","Старая школа"),("Russian Dance","Русский Dance"),("Russian Gold","Русское золото"),
("Russian","Русский"),("Radio","Радио")
]

def fetch():
    req=urllib.request.Request(URL,headers={"User-Agent":"sportpulse-radio-updater/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode("utf-8-sig")

def localize(name):
    s=name.strip()
    for a,b in WORDS: s=re.sub(re.escape(a),b,s,flags=re.I)
    return s

src=fetch()
out=[]
for line in src.splitlines():
    if line.startswith("#EXTINF:") and "," in line:
        meta,name=line.rsplit(",",1)
        line=meta+","+localize(name)
    out.append(line)
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text("\n".join(out)+"\n",encoding="utf-8")
print("Saved",OUT)
