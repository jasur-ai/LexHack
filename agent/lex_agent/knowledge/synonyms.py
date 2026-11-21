"""Word-level colloquial → statutory vocabulary for Uzbek (folded Latin) and Russian.

The situation lexicon covers whole situations; this table bridges single everyday words to the words statutes
use, so questions phrased in an unexpected way still reach the right articles: "kelin" → "er-xotin oila
aʼzosi", "zaharlandim" → "sifatsiz xavfsiz tovar", "blokladi" → "toʻxtatib turish operatsiyalar". Keys are word
prefixes in the folded view (lowercase Latin without apostrophes, x→h, q→k); multi-word keys are matched as
phrases. Values are added to the search as extra, lower-weight terms.
"""

from __future__ import annotations

import re
from functools import lru_cache

from lex_agent.knowledge.lexicon import fold_ru, fold_uz

# fmt: off
UZ: dict[str, str] = {
    # people and relations
    "kelin": "er-xotin oila a'zosi", "kuyov": "er-xotin oila a'zosi", "kaynona": "oila a'zosi qarindosh",
    "kaynota": "oila a'zosi qarindosh", "kaynisi": "qarindosh", "hotinim": "xotin er-xotin", "erim": "er er-xotin",
    "turmush ortog": "er-xotin", "ayolim": "xotin er-xotin", "sobik er": "nikohdan ajralgan er-xotin",
    "sobik hotin": "nikohdan ajralgan er-xotin", "farzand": "bola", "ugil": "bola voyaga yetmagan", "kizim": "bola",
    "nevara": "nevara bobo buvi", "chol": "keksa", "kampir": "keksa", "yetim": "ota-ona qaramog'idan mahrum bola",
    "nogiron": "nogironligi bo'lgan shaxs", "bokuvchi": "boquvchi", r"uka\b|ukam": "aka-uka qarindosh", r"opa\b|opam|opasi": "opa-singil qarindosh",
    "kushni": "qo'shni", "direktor": "ish beruvchi rahbar", "boshlik": "ish beruvchi rahbar", "hojayin": "ish beruvchi",
    "rabotodatel": "ish beruvchi", "ishchi": "xodim", "hodim": "xodim", "sotuvchi": "sotuvchi", "haridor": "sotib oluvchi iste'molchi",
    "mijoz": "iste'molchi", "kvartirant": "ijarachi ijaraga oluvchi", "uy egasi": "ijaraga beruvchi mulkdor",
    "militsiya": "ichki ishlar organlari", "politsiya": "ichki ishlar organlari", r"gai\b": "yo\'l harakati xavfsizligi",
    "yhhb": "yo'l harakati xavfsizligi", "prokuror": "prokuratura", "sudya": "sud", "advokat": "advokat himoyachi",
    "notarius": "notarius notarial", "hokim": "mahalliy davlat hokimiyati", "mahalla": "fuqarolar yig'ini",
    "soliqchi": "soliq organi", "bojhona": "bojxona", "bank": "bank kredit tashkiloti",
    # work
    "zarplat": "ish haqi", "maosh": "ish haqi", "oylik": "ish haqi", "avans": "ish haqi bo'nak", "premiya": "mukofot rag'batlantirish",
    "bonus": "mukofot rag'batlantirish", "shtraf": "jarima", "vigovor": "intizomiy jazo hayfsan", "hayfsan": "intizomiy jazo",
    "otpusk": "ta'til", "tatil": "ta'til", "bolnichn": "vaqtincha mehnatga qobiliyatsizlik", "dekret": "homiladorlik va tug'ish ta'tili",
    "smena": "ish vaqti smena", "pererabotk": "ish vaqtidan tashqari ish", "kech(?:gacha)? ishla": "ish vaqtidan tashqari ish",
    "hayda": "mehnat shartnomasini bekor qilish ishdan bo'shatish", "boshat": "mehnat shartnomasini bekor qilish",
    "uvoln": "mehnat shartnomasini bekor qilish", "sokrashen": "xodimlar soni shtati qisqarishi", "kiskartir": "xodimlar soni shtati qisqarishi",
    "ishga ol": "ishga qabul qilish", "ishga kir": "ishga qabul qilish", "trudovoy": "mehnat daftarchasi",
    "dogovor": "shartnoma", "kontrakt": "shartnoma", "ariza yoz": "ariza", "ish joyi": "ish joyi", "jarohat": "shikast baxtsiz hodisa ziyon",
    "mayib": "shikast sog'lig'iga ziyon", "ish tashla": "ish tashlash", "kasaba": "kasaba uyushmasi",
    "masofadan": "masofadan turib ishlash", "onlayn ishla": "masofadan turib ishlash", "staj": "ish staji",
    "pensiya": "pensiya", "pensioner": "pensiya", "nafaka": "nafaqa", "ishsiz": "ishsiz bandlik",
    # family
    "taloq": "nikohdan ajratish", "ajrash": "nikohdan ajratish", "ajral": "nikohdan ajratish", "razvod": "nikohdan ajratish",
    "zags": "fuqarolik holati dalolatnomalarini qayd etish", "fhdyo": "fuqarolik holati dalolatnomalarini qayd etish",
    r"toy(?:\b|da|ni|ga|dan|lar)": "nikoh", "uylan": "nikoh tuzish", "turmushga chik": "nikoh tuzish", "kelin bol": "nikoh tuzish",
    "alimen": "aliment ta'minot", "bola puli": "aliment nafaqa", "otalik": "otalikni belgilash nasl-nasab",
    "dnk": "otalikni belgilash", "metrka": "tug'ilganlik to'g'risida guvohnoma", "asrab": "farzandlikka olish",
    "vasiy": "vasiylik homiylik", "opeka": "vasiylik homiylik", "urib": "zo'rlik shikast", "kaltak": "zo'rlik badanga shikast",
    "zoravon": "zo'ravonlik tazyiq", "haqorat": "haqorat", "sokdi": "haqorat", "sokin": "haqorat bezorilik",
    # property, housing, contracts
    "kvartira": "turar joy uy-joy", "hovli": "uy-joy turar joy", r"dom\b": "uy-joy", "uyim": "uy-joy turar joy",
    "propiska": "yashash joyi bo'yicha ro'yxatdan o'tkazish", "royhatga kuy": "ro'yxatdan o'tkazish", "registratsiya": "ro'yxatdan o'tkazish",
    "arenda": "ijara", "ijara": "ijara", "ijaraga": "ijara", "kommunal": "kommunal xizmatlar to'lov", r"svet(?!ofor)": "elektr energiyasi",
    r"gaz(?!eta)": "gaz ta\'minoti", "remont": "ta'mirlash", "tamir": "ta'mirlash", "kadastr": "ko'chmas mulk davlat ro'yxati",
    "hujjat": "hujjat", "tilhat": "qarz shartnomasi", "raspiska": "qarz shartnomasi", "dolg": "qarz", "kar[zs]": "qarz",
    "kredit": "kredit", "nasiya": "kredit muddatli to'lov", "rassrochk": "muddatli to'lov", "garov": "garov",
    "zalog": "garov", "lombard": "garov omonat saqlash", "kafil": "kafillik", "sovga": "hadya", "hadya": "hadya",
    "sotib ol": "oldi-sotdi", "sotdim": "oldi-sotdi", "magazin": "sotuvchi savdo", "dokon": "sotuvchi savdo",
    "bozor": "savdo", r"chek(?:\b|i\b|ni\b| berma)": "kassa cheki", "garantiya": "kafolat muddati", "kafolat": "kafolat", "brak": "sifatsiz nuqsonli",
    "buzuk": "nuqsonli sifatsiz", "buzil": "nuqsonli sifatsiz", "sifatsiz": "nuqsonli sifatsiz", "zaharlan": "sifatsiz xavfsiz zarar sog'lig'iga",
    "muddati otgan": "yaroqlilik muddati o'tgan sifatsiz", "prosrochen": "yaroqlilik muddati o'tgan sifatsiz",
    "aldab": "aldash firibgarlik", "aldash": "firibgarlik", "moshennik": "firibgarlik", "piramida": "firibgarlik",
    "zarar": "zarar ziyon", "ziyon": "zarar ziyon", "kompensatsiya": "kompensatsiya qoplash",
    "meros": "meros vorislik", "vasiyat": "vasiyatnoma", "marhum": "meros qoldiruvchi vafot", "vafot": "vafot meros",
    "ozboshimcha": "o'zboshimchalik bilan qurilgan", "samostroy": "o'zboshimchalik bilan qurilgan", "yer uchastka": "yer uchastkasi",
    "tomorka": "tomorqa yer uchastkasi", "dala hovli": "yer uchastkasi",
    # traffic, administrative, criminal
    "mashina": "transport vositasi", "avtomobil": "transport vositasi", "moshina": "transport vositasi", r"rul(?:\b|da|ga)": "transport vositasini boshqarish",
    "haydovchi": "haydovchi transport vositasini boshqarish", "prava": "haydovchilik guvohnomasi transport vositasini boshqarish huquqi",
    "guvohnoma": "guvohnoma", "avariya": "yo'l-transport hodisasi", "dtp": "yo'l-transport hodisasi", "tokna": "yo'l-transport hodisasi",
    "piyoda": "piyoda", "svetofor": "svetofor signali", "tezlik": "harakat tezligi", "radar": "harakat tezligi foto video qayd",
    "kamera": "foto video qayd etish", "evakuator": "jarima maydonchasi", "tonirov": "qoraytirilgan oyna",
    "mast": "mastlik holati", "ichib": "mastlik holati alkogol", "aroq": "alkogol spirtli ichimlik", "pivo": "alkogol spirtli ichimlik",
    "sigaret": "tamaki mahsuloti", "kalyan": "tamaki mahsuloti", "nasha": "giyohvandlik vositasi", "narkotik": "giyohvandlik vositasi",
    "ogri": "o'g'rilik", "ogirla": "o'g'rilik talon-toroj", "tortib": "talonchilik", "reket": "tovlamachilik",
    "shantaj": "tovlamachilik", "pora": "pora", "vzyatka": "pora", "korrupsiya": "korrupsiya pora", "kotil": "qasddan odam o'ldirish",
    "oldir": "o'ldirish", "korkit": "qo'rqitish tahdid", "tahdid": "qo'rqitish tahdid", "zorla": "nomusga tegish zo'rlik",
    "bezori": "bezorilik", "janjal": "bezorilik", "mushtla": "badanga shikast", "kalla": "badanga shikast", "burn": "badanga shikast",
    "sindir": "shikast", "pichok": "sovuq qurol", "kurol": "qurol", "akkaunt": "kompyuter axboroti ruxsatsiz foydalanish",
    "akaunt": "kompyuter axboroti ruxsatsiz foydalanish", "telegram": "kompyuter axboroti", "vzlom": "ruxsatsiz foydalanish",
    "haker": "kompyuter axboroti ruxsatsiz foydalanish", "parol": "kompyuter axboroti", "karta": "bank kartasi to'lov",
    "kartadan": "bank kartasi to'lov ruxsatsiz", r"bola\w* ogirla": "odam o'g'irlash ozodlikdan mahrum qilish",
    r"odam\w* ogirla": "odam o'g'irlash ozodlikdan mahrum qilish", "garovga ol": "garovga olish ozodlikdan mahrum qilish",
    "kamal": "qamoq ozodlikdan mahrum qilish", "turma": "ozodlikdan mahrum qilish", "sutka": "ma'muriy qamoq",
    "ushla": "ushlab turish", "zaderj": "ushlab turish", "tergov": "tergov", "sudla": "sud",
    "ombudsman": "inson huquqlari bo'yicha vakil", "chet el": "chet el", "horij": "chet el", "migrant": "mehnat migratsiyasi",
    "pasport": "pasport", "id karta": "identifikatsiyalovchi id-karta", "armiya": "harbiy xizmat", "askar": "harbiy xizmat",
    "povestka": "chaqiruv", "voenkomat": "mudofaa ishlari bo'limi",
    # money, tax, business
    "nalog": "soliq", "solik": "soliq", "deklaratsiya": "deklaratsiya", "chegirma": "soliq imtiyozi chegirma",
    "biznes": "tadbirkorlik", "firma": "yuridik shaxs korxona", "ooo": "mas'uliyati cheklangan jamiyat", "mchj": "mas'uliyati cheklangan jamiyat",
    "yatt": "yakka tartibdagi tadbirkor", "litsenziya": "litsenziya", "ruhsatnoma": "ruxsat etish xususiyatiga ega hujjat",
    "tekshiruv": "tekshiruv nazorat", "proverka": "tekshiruv", "blokla": "operatsiyalarni to'xtatib turish", "muzlat": "to'xtatib turish",
    "arest": "xatlov", "hatlov": "xatlov", "mib": "majburiy ijro", "ijro": "ijro", "bankrot": "to'lovga qobiliyatsizlik",
    "tugat": "tugatish", r"yop(?:moq|ish|dim|sam)": "tugatish yopish", "omonat": "omonat", "depozit": "omonat", "sugurta": "sug'urta",
    "polis": "sug'urta polisi", "osago": "transport vositalari egalarining fuqarolik javobgarligini majburiy sug'urta qilish",
    "murojaat": "murojaat ariza shikoyat", "murojat": "murojaat ariza shikoyat", "shikoyat": "shikoyat", "ariza": "ariza",
    "javob berma": "murojaatni ko'rib chiqish muddati", "elektron": "elektron", "onlayn": "elektron",
    "kuchga kir": "qonuniy kuchga kirishi", "bajarma": "ijro etmaslik", "majburla": "majburlash",
}

RU: dict[str, str] = {
    "зарплат": "заработная плата", "оклад": "заработная плата", "премия": "поощрение", "штраф": "штраф",
    "уволи": "прекращение трудового договора", "увольн": "прекращение трудового договора", "сокращ": "сокращение численности штата",
    "больничн": "временная нетрудоспособность", "декрет": "отпуск по беременности и родам", "переработ": "сверхурочная работа",
    "начальник": "работодатель", "директор": "работодатель", "работодател": "работодатель", "трудовая": "трудовая книжка",
    "травм": "несчастный случай вред здоровью", "развод": "расторжение брака", "загс": "органы записи актов гражданского состояния",
    "свадьб": "брак", "алимент": "алименты содержание", "отцовств": "установление отцовства", "опек": "опека попечительство",
    "бьет": "насилие телесные повреждения", "бьёт": "насилие телесные повреждения", "избил": "телесные повреждения побои",
    "квартир": "жилое помещение", "прописк": "регистрация по месту жительства", "аренд": "аренда наем", "съем": "наем жилого помещения",
    "коммуналк": "коммунальные услуги", "ремонт": "ремонт подряд", "долг": "заем долг", "расписк": "договор займа",
    "кредит": "кредит", "рассрочк": "кредит", "залог": "залог", "подарил": "дарение", "дарств": "дарение",
    "магазин": "продавец торговля", "товар": "товар", "брак": "ненадлежащее качество", "бракован": "ненадлежащее качество",
    "сломал": "недостаток товара", "просроч": "срок годности ненадлежащее качество", "отравил": "вред здоровью ненадлежащее качество",
    "наслед": "наследство наследование", "завещ": "завещание", "умер": "открытие наследства смерть",
    "машин": "транспортное средство", "авто": "транспортное средство", "права": "право управления транспортным средством",
    "дтп": "дорожно-транспортное происшествие", "авари": "дорожно-транспортное происшествие", "пьян": "состояние опьянения",
    "скорост": "скорость движения", "камер": "фото видеофиксация", "парковк": "стоянка остановка",
    "украл": "кража", "украли": "кража", "кража": "кража", "обманул": "мошенничество", "мошен": "мошенничество",
    "развел": "мошенничество", "взятк": "взятка", "угрожа": "угроза", "взлом": "неправомерный доступ к компьютерной информации",
    "аккаунт": "компьютерная информация", "задерж": "задержание", "арест": "арест", "адвокат": "защитник адвокат",
    "налог": "налог", "вычет": "налоговые льготы", r"ип\b": "индивидуальный предприниматель", "ооо": "общество с ограниченной ответственностью",
    "бизнес": "предпринимательская деятельность", "лиценз": "лицензия", "проверк": "проверка контроль", "банкрот": "несостоятельность",
    "заблокир": "приостановление операций", "пенси": "пенсия", "инвалид": "инвалидность", "пособи": "пособие",
    "жалоб": "жалоба обращение", "обращени": "обращение", "армия": "воинская служба", "призыв": "призыв", "повестк": "призыв",
    "гражданств": "гражданство", "иностран": "иностранный гражданин", "суд": "суд", "исполнительн": "исполнительный документ",
}
# fmt: on

_UZ_KEYS = sorted(UZ, key=len, reverse=True)
_RU_KEYS = sorted(RU, key=len, reverse=True)


@lru_cache(maxsize=1)
def _compiled() -> tuple[list[tuple[re.Pattern[str], str]], list[tuple[re.Pattern[str], str]]]:
    def comp(key: str, uz: bool) -> re.Pattern[str]:
        k = key.replace("x", "h").replace("q", "k") if uz else key
        return re.compile(r"(?<![a-zа-яё])" + k, re.I)

    return [(comp(k, True), UZ[k]) for k in _UZ_KEYS], [(comp(k, False), RU[k]) for k in _RU_KEYS]


def expansion_text(query: str, *, language: str, limit: int = 8) -> str:
    """Formal words for the everyday words of a question ("" when nothing matches)."""
    uz_rules, ru_rules = _compiled()
    if language == "ru":
        view, rules = fold_ru(query), ru_rules
    else:
        view, rules = fold_uz(query), uz_rules
    out: list[str] = []
    for rx, words in rules:
        if rx.search(view) and words not in out:
            out.append(words)
            if len(out) >= limit:
                break
    return " ".join(out)
