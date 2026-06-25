from __future__ import annotations


COUNTRY_LANGUAGES: dict[str, list[str]] = {
    "laos": ["Lao"],
    "lao pdr": ["Lao"],
    "thailand": ["Thai"],
    "vietnam": ["Vietnamese"],
    "cambodia": ["Khmer"],
    "japan": ["Japanese"],
    "korea": ["Korean"],
    "south korea": ["Korean"],
    "china": ["Chinese"],
    "taiwan": ["Traditional Chinese"],
    "indonesia": ["Indonesian"],
    "malaysia": ["Malay"],
    "france": ["French"],
    "italy": ["Italian"],
    "spain": ["Spanish", "Catalan"],
    "portugal": ["Portuguese"],
    "mexico": ["Spanish"],
    "peru": ["Spanish", "Quechua"],
    "morocco": ["Arabic", "French"],
    "turkey": ["Turkish"],
    "greece": ["Greek"],
    "germany": ["German"],
    "austria": ["German"],
    "switzerland": ["German", "French", "Italian"],
    "brazil": ["Portuguese"],
    "argentina": ["Spanish"],
    "chile": ["Spanish"],
    "egypt": ["Arabic"],
    "india": ["Hindi", "English"],
    "nepal": ["Nepali"],
    "georgia": ["Georgian"],
    "iceland": ["Icelandic"],
}

LANGUAGE_SEARCH_PHRASES: dict[str, str] = {
    "Lao": "ທ່ອງທ່ຽວ ສະຖານທີ່ ຄໍາແນະນໍາ",
    "Thai": "แนะนำที่เที่ยว",
    "Vietnamese": "địa điểm du lịch gợi ý",
    "Khmer": "កន្លែងទេសចរណ៍ណែនាំ",
    "Japanese": "旅行 おすすめ 場所",
    "Korean": "여행 추천 장소",
    "Chinese": "旅游 推荐 地点",
    "Traditional Chinese": "旅遊 推薦 地點",
    "Indonesian": "rekomendasi tempat wisata",
    "Malay": "cadangan tempat melancong",
    "French": "lieux à visiter conseils voyage",
    "Italian": "posti da visitare consigli viaggio",
    "Spanish": "lugares para visitar consejos de viaje",
    "Catalan": "llocs per visitar consells de viatge",
    "Portuguese": "lugares para visitar dicas de viagem",
    "Arabic": "أماكن سياحية نصائح سفر",
    "Turkish": "gezilecek yerler seyahat önerileri",
    "Greek": "μέρη για επίσκεψη ταξιδιωτικές προτάσεις",
    "German": "reise empfehlungen sehenswürdigkeiten",
    "Quechua": "turismo lugares recomendados",
    "Hindi": "यात्राおすすめ स्थान",
    "Nepali": "घुम्न जाने ठाउँ सिफारिस",
    "Georgian": "სამოგზაურო რეკომენდაციები ადგილები",
    "Icelandic": "ferðalög staðir meðmæli",
}


def unique_strings(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in items if item.strip()))


def infer_local_languages(destinations: list[str]) -> list[str]:
    text = " ".join(destinations).lower()
    languages: list[str] = []
    for place, place_languages in COUNTRY_LANGUAGES.items():
        if place in text:
            languages.extend(place_languages)
    return unique_strings(languages)


def build_local_language_query(base_query: str, languages: list[str]) -> str:
    phrases = [
        LANGUAGE_SEARCH_PHRASES.get(language, f"{language} travel recommendations")
        for language in languages
    ]
    return f"{base_query} {' '.join(phrases)}".strip()
