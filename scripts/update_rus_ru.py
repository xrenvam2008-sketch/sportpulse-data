#!/usr/bin/env python3
import json, re, urllib.request
from pathlib import Path

PLAYLIST_URL = "https://iptv-org.github.io/iptv/languages/rus.m3u"
CHANNELS_URL = "https://iptv-org.github.io/api/channels.json"
OUT = Path("iptv/rus_RU.m3u")

CATEGORY_RU = {
    "animation":"Мультфильмы","auto":"Авто","business":"Бизнес","classic":"Классика",
    "comedy":"Комедия","cooking":"Кулинария","culture":"Культура","documentary":"Документальные",
    "education":"Образование","entertainment":"Развлекательные","family":"Семейные",
    "general":"Общие","kids":"Детские","legislative":"Законодательство","lifestyle":"Образ жизни",
    "movies":"Кино","music":"Музыка","news":"Новости","outdoor":"Активный отдых",
    "relax":"Релакс","religious":"Религия","science":"Наука","series":"Сериалы",
    "shop":"Магазины","sports":"Спорт","travel":"Путешествия","weather":"Погода"
}

def get_text(url):
    req=urllib.request.Request(url, headers={"User-Agent":"sportpulse-data-rus-ru-updater/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig")

def has_cyr(s):
    return bool(re.search(r"[А-Яа-яЁё]", s or ""))

def main():
    src=get_text(PLAYLIST_URL)
    channels=json.loads(get_text(CHANNELS_URL))
    by_id={c.get("id"):c for c in channels if c.get("id")}

    out=[]
    translated=0
    for line in src.splitlines():
        if not line.startswith("#EXTINF:"):
            out.append(line)
            continue

        m=re.search(r'tvg-id="([^"]*)"', line)
        raw_id=m.group(1) if m else ""
        base_id=raw_id.split("@",1)[0]
        ch=by_id.get(base_id)

        if ch:
            candidates=[]
            if has_cyr(ch.get("name","")):
                candidates.append(ch["name"])
            candidates += [x for x in (ch.get("alt_names") or []) if has_cyr(x)]
            ru_name=candidates[0] if candidates else None

            comma=line.rfind(",")
            if comma >= 0 and ru_name:
                old_title=line[comma+1:]
                suffix=""
                sm=re.search(r'(\s+(?:HD|SD|UHD|4K))?(\s*\([^)]*\))?(\s*\[[^]]*\])?\s*$', old_title)
                if sm:
                    suffix=sm.group(0)
                line=line[:comma+1] + ru_name + suffix
                translated += 1

            cats=ch.get("categories") or []
            if cats:
                cat=", ".join(CATEGORY_RU.get(str(x).lower(), str(x)) for x in cats)
                if 'group-title="' in line:
                    line=re.sub(r'group-title="[^"]*"', 'group-title="'+cat+'"', line)
                else:
                    pos=line.find(",")
                    if pos >= 0:
                        line=line[:pos] + ' group-title="'+cat+'"' + line[pos:]

        out.append(line)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out)+"\n", encoding="utf-8")
    print(f"Saved {OUT}; localized entries: {translated}")

if __name__ == "__main__":
    main()
