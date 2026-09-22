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
    req=urllib.request.Request(URL,headers={"User-Agent":"sportpulse-radio-updater/1.1"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode("utf-8-sig")

def localize(name):
    s=name.strip()
    for a,b in WORDS:
        s=re.sub(re.escape(a),b,s,flags=re.I)
    return s

src=fetch()
lines=src.splitlines()
out=["#EXTM3U"]
count=0
i=0
while i < len(lines):
    line=lines[i].strip()
    if line.startswith("#EXTINF:") and "," in line:
        meta,name=line.rsplit(",",1)
        logo=""
        m=re.search(r'(?:tvg-logo|tv-logo)="([^"]*)"',meta,re.I)
        if m: logo=m.group(1).strip()
        # Normalize every station to the simple form understood by CoverFlow.
        ext='#EXTINF:-1'
        if logo:
            ext += ' tvg-logo="'+logo+'"'
        ext += ','+localize(name)
        # Find the following stream URL, skipping blank/comment lines.
        j=i+1
        while j < len(lines):
            u=lines[j].strip()
            if u and not u.startswith("#"):
                out.append(ext)
                out.append(u)
                count+=1
                i=j
                break
            if u.startswith("#EXTINF:"):
                break
            j+=1
    i+=1

OUT.parent.mkdir(parents=True,exist_ok=True)
# UTF-8 without BOM, CRLF for maximum Windows/M3U parser compatibility.
OUT.write_bytes(("\r\n".join(out)+"\r\n").encode("utf-8"))
print(f"Saved {OUT}; stations: {count}")
