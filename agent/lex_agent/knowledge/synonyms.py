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
    "ichkilik": "alkogol mastlik holati", "tekshiruvdan bosh tort": "tibbiy ko'rikdan o'tishdan bo'yin tovlash",
    "ozini himoya": "zaruriy mudofaa", "ozimni himoya": "zaruriy mudofaa", "hatla": "mol-mulkni xatlash",
    "sud ijrochi": "davlat ijrochisi ijro hujjati", "ijarada": "ijara turar joy", "ijaradagi": "ijara turar joy",
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

# English everyday/legal words -> the Russian statutory words (the corpus has every act in Russian; there is no
# English statute text, so an English question reaches the law only through this bridge and the situation lexicon).
EN: dict[str, str] = {
    # work
    r"fir(?:e|ed|ing)\b|dismiss|laid off|lay(?:ing)? off|let go": "увольнение прекращение трудового договора по инициативе работодателя",
    r"resign|quit(?:ting)?\b": "прекращение трудового договора по инициативе работника", r"notice\b": "предупреждение",
    r"redundan": "сокращение численности штата работников", r"salary|wage|pay\b|paid\b|paycheck": "заработная плата оплата труда",
    r"overtime": "сверхурочная работа", r"night (?:shift|work)": "работа в ночное время", r"weekend": "выходные дни",
    r"public holiday|bank holiday": "праздничные нерабочие дни", r"shift\b|shifts\b": "продолжительность ежедневной работы смены",
    r"working hours|work(?:ing)? week|hours a week": "продолжительность рабочего времени", r"vacation|annual leave|holiday leave": "ежегодный трудовой отпуск",
    r"unpaid leave": "отпуск без сохранения заработной платы", r"sick leave|sick\b|illness": "временная нетрудоспособность пособие",
    r"maternity|pregnan": "беременность и роды беременные женщины", r"childcare leave|parental leave|paternity leave": "отпуск по уходу за ребенком",
    r"probation": "предварительное испытание", r"employment contract|work contract": "трудовой договор",
    r"employer|boss\b": "работодатель", r"employee|worker|staff": "работник", r"severance": "выходное пособие",
    r"workbook|employment record": "трудовая книжка", r"(?:workplace|work) (?:injury|accident)|injured at work": "трудовое увечье возмещение вреда работодатель",
    r"strike\b": "забастовка", r"minimum wage": "минимальный размер оплаты труда", r"transfer(?:red)? to": "перевод на другую работу",
    r"unused leave": "компенсация за неиспользованный отпуск", r"business trip": "служебная командировка",
    r"discipline|reprimand": "дисциплинарное взыскание", r"labou?r inspector": "государственная инспекция труда",
    # family
    r"divorc": "расторжение брака", r"marri|wedding": "брак заключение брака брачный возраст", r"spouse|wife|husband": "супруг супруги",
    r"child support|alimony|maintenance": "алименты содержание", r"custody|live with (?:me|the mother|the father)": "место жительства ребенка",
    r"visit(?:ation)?\b|see (?:my|the|their) (?:child|kid|grand)": "общение с ребенком", r"grandparent|grandchild": "дедушка бабушка общение с ребенком",
    r"paternity": "установление отцовства", r"adopt": "усыновление", r"prenup|marriage contract|marital agreement": "брачный договор",
    r"parental rights": "лишение родительских прав", r"domestic violence|abus": "насилие притеснение охранный ордер",
    r"ex-?wife|ex-?husband|former spouse": "бывший супруг содержание после расторжения брака",
    # inheritance
    r"inherit|estate\b|heir": "наследство наследование наследники", r"\bwill\b|testament": "завещание",
    r"refuse (?:an |the )?inheritance|renounce": "отказ от наследства", r"no will|without a will": "наследование по закону очередь наследников",
    # civil
    r"loan|lend|borrow|lent\b": "заем договор займа", r"\bdebt": "долг обязательство взыскание",
    r"limitation period|statute of limitations": "исковая давность срок", r"contract": "договор",
    r"\bsell|\bsold|\bbuy|bought|purchase": "купля-продажа продавец покупатель оплата товара", r"gift": "дарение",
    r"\brent\b|lease|landlord|tenant|letting": "договор найма жилого помещения наймодатель наниматель аренда",
    r"sublet|sublease": "поднаем жилого помещения", r"power of attorney|proxy": "доверенность",
    r"damage|compensat|harm": "возмещение вреда ущерб", r"moral (?:harm|damage)|emotional distress": "компенсация морального вреда",
    r"flood": "затопление возмещение вреда", r"insur": "страхование страховая выплата", r"propert|own(?:er|ership)\b": "право собственности имущество",
    r"money sent by mistake|wrong (?:account|transfer)": "неосновательное обогащение",
    # consumer
    r"\bshop|\bstore|seller|retailer": "продавец потребитель", r"refund|money back": "возврат денег потребителю",
    r"exchange|return (?:a |an |the )?(?:item|product|purchase|goods)": "обмен товара надлежащего качества возврат",
    r"faulty|defect|broken|poor quality": "товар ненадлежащего качества недостатки", r"warranty|guarantee": "гарантийный срок",
    r"receipt": "чек документ об оплате", r"food poisoning|expired": "безопасность товара возмещение вреда",
    # housing
    r"evict": "выселение из жилого помещения", r"utilit|electricity|gas bill|water bill": "коммунальные услуги оплата",
    r"renovat|redevelop|remodel|knock down a wall": "переустройство и перепланировка жилых помещений",
    r"registration|register (?:at|my) (?:address|residence)|propiska": "регистрация по месту жительства месту пребывания",
    r"privati": "приватизация жилья", r"neighbou?r": "соседи",
    # admin and traffic
    r"\bfine\b|\bfined\b|penalt": "штраф административная ответственность", r"speed": "превышение скорости движения",
    r"red light|traffic light": "запрещающий сигнал светофора", r"drunk|alcohol|intoxicat|breathalyz|drink-?driv": "состояние опьянения освидетельствование",
    r"refus\w* (?:a |the )?(?:breath|alcohol|sobriety) test": "уклонение от освидетельствования на состояние опьянения",
    r"driv(?:ing|er)'?s? licen[cs]e|without a licen[cs]e": "водительское удостоверение право управления документы",
    r"seat ?belt": "ремни безопасности", r"phone while driving|on the phone": "пользование телефоном во время управления",
    r"car accident|crash|collision": "дорожно-транспортное происшествие", r"car insurance|motor insurance": "обязательное страхование гражданской ответственности владельцев транспортных средств",
    r"parking|park(?:ed)?\b": "стоянка остановка транспортного средства", r"road rage": "дорожное хулиганство",
    r"smok": "употребление табачной продукции в общественных местах", r"drinking in public|public drinking": "употребление алкогольной продукции в общественных местах",
    r"hooligan": "хулиганство", r"wedding (?:rules|limit)": "проведение свадеб семейных торжеств",
    # criminal
    r"theft|steal|stole": "кража", r"fraud|scam|swindl|cheat": "мошенничество", r"robb": "грабеж разбой",
    r"brib": "взятка дача получение взятки", r"assault|beat(?:en|ing)?\b|punch|injur": "телесное повреждение",
    r"murder|kill": "убийство", r"kidnap|abduct": "похищение человека", r"drug|narcotic": "наркотические средства",
    r"self-?defen[cs]e|defend(?:ing)? myself": "необходимая оборона", r"detain|arrest": "задержание подозреваемый права",
    r"lawyer|attorney|defen[cs]e counsel": "защитник адвокат", r"\bbail\b|pre-?trial": "мера пресечения",
    r"parole|early release": "условно-досрочное освобождение", r"threat": "угроза убийством", r"blackmail|extort": "вымогательство",
    r"hack|account was hacked": "неправомерный доступ к компьютерной информации", r"forg": "подделка документов",
    r"embezzl": "присвоение растрата", r"smuggl": "контрабанда", r"rape|sexual": "изнасилование",
    # procedure
    r"\bcourt": "суд", r"\bsue\b|lawsuit|file a claim|claim in court": "исковое заявление подача иска",
    r"appeal": "апелляционная жалоба", r"cassation": "кассационная жалоба", r"court fee|filing fee|state duty": "государственная пошлина",
    r"bailiff|enforcement|enforce": "исполнение исполнительный документ государственный исполнитель", r"seiz": "арест имущества должника",
    r"deadline|time limit|how long": "срок", r"hearing|decide (?:a |the )?(?:\w+ )?case|trial": "сроки рассмотрения и разрешения дел",
    r"civil case|civil dispute": "гражданское дело", r"criminal case": "уголовное дело",
    r"jurisdiction|which court": "подсудность", r"defer|instal?lment": "отсрочка рассрочка",
    # tax
    r"\btax": "налог", r"income tax|personal income": "налог на доходы физических лиц ставка", r"declaration|tax return": "декларация о совокупном годовом доходе",
    r"late payment interest|penalty interest": "пеня", r"\bvat\b": "налог на добавленную стоимость", r"tax audit|tax inspection": "налоговый аудит налоговая проверка",
    r"rental income": "доход от сдачи имущества в аренду", r"taxpayer": "налогоплательщик права налогоплательщиков",
    # social
    r"pension|retire": "пенсия пенсия по возрасту", r"disabilit": "инвалидность пенсия по инвалидности",
    r"survivor|breadwinner": "пенсия по случаю потери кормильца", r"benefit|allowance": "пособие",
    r"work experience|years of service|service record": "стаж работы",
    # rights and state
    r"complain\w* to (?:a |the )?(?:state|government)|government (?:agency|body)|ministry": "обращение государственный орган рассмотрение",
    r"personal data|my data": "персональные данные согласие на обработку", r"access to information|information request": "доступ к информации",
    r"privacy": "неприкосновенность частной жизни", r"ombuds": "уполномоченный по правам человека",
    # business
    r"\bllc\b|limited liability|company": "общество с ограниченной ответственностью участники", r"founder|shareholder|participant": "участник учредитель",
    r"licen[cs]e for|business licen": "лицензирование лицензия", r"entrepreneur|self-employed|sole trader": "индивидуальный предприниматель",
    # migration
    r"dual citizenship|second citizenship|two passports": "гражданство иностранного государства", r"citizenship|naturali": "гражданство прием в гражданство",
    r"foreign(?:er| national| citizen)": "иностранные граждане", r"residence permit": "вид на жительство",
    # public
    r"military|army|conscript": "воинская обязанность военная служба призыв", r"deferr?al|deferment|postpone": "отсрочка от призыва",
    r"school|universit|education": "образование", r"vaccin|hospital|medical": "охрана здоровья медицинская помощь",
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


@lru_cache(maxsize=1)
def _compiled_en() -> list[tuple[re.Pattern[str], str]]:
    return [(re.compile(r"(?<![a-z])(?:" + k + ")", re.I), v) for k, v in EN.items()]


def expansion_text(query: str, *, language: str, limit: int = 8) -> str:
    """Formal words for the everyday words of a question ("" when nothing matches)."""
    uz_rules, ru_rules = _compiled()
    if language == "en":
        view, rules = (query or "").lower(), _compiled_en()
        limit = max(limit, 10)
    elif language == "ru":
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
