"""Topic-specific follow-up questions, shown as tappable suggestions under an answer.

Concepts of the situation lexicon may carry their own follow-ups (``follow_uz`` / ``follow_ru``); everything else gets
the questions of its legal domain. The list never repeats the topic just asked about: a suggestion whose own top
concept equals the question's top concept is skipped. Every suggestion is a question the agent answers well (see
``tests/test_assistant.py::test_domain_follow_ups_are_answerable``).
"""

from __future__ import annotations

from functools import lru_cache

# Situations where the next questions matter most get their own list (all four languages)
CONCEPT_FOLLOW_UPS: dict[str, dict[str, tuple[str, ...]]] = {
    "family.domestic_violence": {
        "uz": ("Himoya orderi qanday olinadi?", "Ajrashish tartibi qanday?", "Aliment qanday undiriladi?"),
        "ru": ("Как получить защитный ордер?", "Как оформить развод?", "Как взыскать алименты?"),
        "en": ("How do I get a protection order?", "How do I get a divorce?", "How do I claim child support?"),
    },
}

DOMAIN_FOLLOW_UPS: dict[str, dict[str, tuple[str, ...]]] = {
    "labour": {
        "uz": ("Ishdan boʻshatilganda qanday toʻlovlar beriladi?", "Ish haqi kechiksa nima qilish kerak?",
               "Yillik mehnat taʼtili necha kun?", "Sinov muddati qancha boʻladi?"),
        "ru": ("Какие выплаты положены при увольнении?", "Что делать, если задерживают зарплату?",
               "Сколько дней длится ежегодный отпуск?", "Какой максимальный испытательный срок?"),
        "en": ("What payments am I owed when dismissed?", "What can I do if my salary is late?",
               "How many days of annual leave do I get?", "How long can a probation period be?"),
    },
    "family": {
        "uz": ("Aliment qanday undiriladi?", "Ajrashish tartibi qanday?", "Ajrashganda bolalar kimda qoladi?",
               "Ajrashganda mol-mulk qanday boʻlinadi?"),
        "ru": ("Как взыскать алименты?", "Как оформить развод?", "С кем останутся дети после развода?",
               "Как делится имущество при разводе?"),
        "en": ("How do I claim child support?", "How do I get a divorce?",
               "Who do the children live with after a divorce?", "How is property divided in a divorce?"),
    },
    "civil": {
        "uz": ("Shartnoma buzilsa qanday javobgarlik bor?", "Qarzni qaytarmasa nima qilish kerak?",
               "Zararni undirish uchun qayerga murojaat qilaman?", "Daʼvo muddati qancha?"),
        "ru": ("Какая ответственность за нарушение договора?", "Что делать, если не возвращают долг?",
               "Куда обращаться за возмещением ущерба?", "Какой срок исковой давности?"),
        "en": ("What is the liability for breaching a contract?", "What can I do if someone won't repay a debt?",
               "Where do I claim compensation for damage?", "What is the limitation period for claims?"),
    },
    "inheritance": {
        "uz": ("Merosni qabul qilish muddati qancha?", "Vasiyatnoma qanday tuziladi?",
               "Vasiyatnoma boʻlmasa meros kimga oʻtadi?", "Majburiy ulushga kim haqli?"),
        "ru": ("Какой срок для принятия наследства?", "Как составить завещание?",
               "Кто наследует, если нет завещания?", "Кто имеет право на обязательную долю?"),
        "en": ("What is the deadline to accept an inheritance?", "How do I make a will?",
               "Who inherits if there is no will?", "Who is entitled to a compulsory share?"),
    },
    "housing": {
        "uz": ("Ijarachini uydan chiqarish tartibi qanday?", "Kommunal toʻlovlarni toʻlamasa nima boʻladi?",
               "Ijara shartnomasini muddatidan oldin bekor qilish mumkinmi?", "Uydan majburan chiqarish mumkinmi?"),
        "ru": ("Как выселить квартиранта?", "Что будет, если не платить за коммунальные услуги?",
               "Можно ли досрочно расторгнуть договор аренды?", "Могут ли принудительно выселить из жилья?"),
        "en": ("How can I evict a tenant?", "What happens if I don't pay utility bills?", "Can a lease be ended early?",
               "Can I be evicted from my home by force?"),
    },
    "consumer": {
        "uz": ("Sifatsiz tovarni qaytarish mumkinmi?", "Kafolat muddatida tovar buzilsa nima qilaman?",
               "Onlayn xaridni qaytarish mumkinmi?", "Sotuvchiga pretenziya qanday yoziladi?"),
        "ru": ("Можно ли вернуть некачественный товар?", "Что делать, если товар сломался по гарантии?",
               "Можно ли вернуть покупку из интернет-магазина?", "Как написать претензию продавцу?"),
        "en": ("Can I return a faulty product?", "What if a product breaks under warranty?",
               "Can I return an online purchase?", "How do I write a complaint to a seller?"),
    },
    "traffic": {
        "uz": ("Tezlikni oshirganlik uchun jarima qancha?", "Mast holda haydaganlik uchun qanday jazo bor?",
               "YTH sodir boʻlsa nima qilish kerak?", "Haydovchilik guvohnomasidan qachon mahrum qilinadi?"),
        "ru": ("Какой штраф за превышение скорости?", "Какое наказание за вождение в нетрезвом виде?",
               "Что делать при ДТП?", "Когда лишают водительских прав?"),
        "en": ("What is the fine for speeding?", "What is the penalty for drunk driving?",
               "What should I do after a road accident?", "When can my driving licence be suspended?"),
    },
    "admin": {
        "uz": ("Maʼmuriy jarima ustidan qanday shikoyat qilsa boʻladi?", "Jarimani oʻz vaqtida toʻlamasa nima boʻladi?",
               "Mayda bezorilik uchun qanday jazo bor?", "Maʼmuriy javobgarlikka tortish muddati qancha?"),
        "ru": ("Как обжаловать административный штраф?", "Что будет, если не оплатить штраф вовремя?",
               "Какое наказание за мелкое хулиганство?", "Какой срок привлечения к административной ответственности?"),
        "en": ("How do I appeal an administrative fine?", "What happens if I don't pay a fine on time?",
               "What is the penalty for petty hooliganism?", "What is the time limit for administrative liability?"),
    },
    "criminal": {
        "uz": ("Firibgarlik uchun qanday jazo bor?", "Jinoyat haqida qayerga ariza beriladi?",
               "Jabrlanuvchining qanday huquqlari bor?", "Tan jarohati yetkazganlik uchun javobgarlik qanday?"),
        "ru": ("Какое наказание за мошенничество?", "Куда подать заявление о преступлении?",
               "Какие права у потерпевшего?", "Какая ответственность за причинение телесных повреждений?"),
        "en": ("What is the penalty for fraud?", "Where do I report a crime?", "What rights does a victim have?",
               "What is the liability for causing bodily harm?"),
    },
    "procedure": {
        "uz": ("Sudga daʼvo arizasi qanday beriladi?", "Sud qarori ustidan qanday shikoyat qilinadi?",
               "Davlat hisobidan bepul yuridik yordam kimga beriladi?", "Sud qarori ijro etilmasa nima qilish kerak?"),
        "ru": ("Как подать исковое заявление в суд?", "Как обжаловать решение суда?",
               "Кому положена бесплатная юридическая помощь?", "Что делать, если решение суда не исполняют?"),
        "en": ("How do I file a lawsuit?", "How do I appeal a court decision?", "Who can get free legal aid?",
               "What if a court decision is not enforced?"),
    },
    "tax": {
        "uz": ("Jismoniy shaxslar daromad soligʻi stavkasi qancha?", "Mol-mulk soligʻi qachon toʻlanadi?",
               "Soliq imtiyozlari kimlarga beriladi?", "Daromad deklaratsiyasi qachon topshiriladi?"),
        "ru": ("Какая ставка налога на доходы физических лиц?", "Когда платить налог на имущество?",
               "Кому положены налоговые льготы?", "Когда подаётся декларация о доходах?"),
        "en": ("What is the personal income tax rate?", "When is property tax due?", "Who is entitled to tax benefits?",
               "When is the income tax return due?"),
    },
    "business": {
        "uz": ("Yakka tartibdagi tadbirkor qanday roʻyxatdan oʻtadi?", "MChJ qanday ochiladi?",
               "Oʻzini oʻzi band qilgan shaxs qanday soliq toʻlaydi?", "Tadbirkorlik faoliyatini qanday tugatish mumkin?"),
        "ru": ("Как зарегистрироваться индивидуальным предпринимателем?", "Как открыть ООО?",
               "Какие налоги платит самозанятый?", "Как закрыть бизнес?"),
        "en": ("How do I register as a sole trader?", "How do I set up an LLC?",
               "What taxes does a self-employed person pay?", "How do I close a business?"),
    },
    "social": {
        "uz": ("Yoshga doir pensiya olish uchun qancha staj kerak?", "Bolalar nafaqasi kimga beriladi?",
               "Nogironlik pensiyasi qanday tayinlanadi?", "Homiladorlik va tugʻish nafaqasi qancha?"),
        "ru": ("Какой стаж нужен для пенсии по возрасту?", "Кому положено пособие на детей?",
               "Как назначается пенсия по инвалидности?", "Какое пособие по беременности и родам?"),
        "en": ("How many years of service are needed for an old-age pension?", "Who gets child benefit?",
               "How is a disability pension granted?", "How much is maternity benefit?"),
    },
    "rights": {
        "uz": ("Davlat organi murojaatga qancha muddatda javob berishi kerak?",
               "Davlat xizmatchisining harakati ustidan qayerga shikoyat qilaman?",
               "Maʼlumot olish huquqi qanday taʼminlanadi?", "Shaxsiy maʼlumotlarim qanday himoya qilinadi?"),
        "ru": ("В какой срок госорган должен ответить на обращение?", "Куда жаловаться на действия чиновника?",
               "Как реализовать право на получение информации?", "Как защищены мои персональные данные?"),
        "en": ("How quickly must a state body answer an appeal?", "Where can I complain about an official's actions?",
               "How do I exercise my right to information?", "How are my personal data protected?"),
    },
    "property": {
        "uz": ("Yer uchastkasi qanday roʻyxatdan oʻtkaziladi?", "Koʻchmas mulkka egalik huquqi qanday rasmiylashtiriladi?",
               "Uyni sotishda qanday hujjatlar kerak?", "Yer uchastkasini olib qoʻyish mumkinmi?"),
        "ru": ("Как зарегистрировать земельный участок?", "Как оформить право собственности на недвижимость?",
               "Какие документы нужны для продажи дома?", "Могут ли изъять земельный участок?"),
        "en": ("How do I register a land plot?", "How do I register ownership of real estate?",
               "What documents are needed to sell a house?", "Can a land plot be taken away?"),
    },
    "finance": {
        "uz": ("Kredit toʻlanmasa bank nima qila oladi?", "Bank kredit shartlarini bir tomonlama oʻzgartira oladimi?",
               "Sugʻurta kompaniyasi toʻlovni rad etsa nima qilaman?", "OSAGO sugʻurtasi nimani qoplaydi?"),
        "ru": ("Что может сделать банк, если не платить кредит?",
               "Может ли банк в одностороннем порядке изменить условия кредита?",
               "Что делать, если страховая отказала в выплате?", "Что покрывает ОСАГО?"),
        "en": ("What can a bank do if I stop paying a loan?", "Can a bank change loan terms unilaterally?",
               "What if an insurer refuses to pay?", "What does compulsory motor insurance cover?"),
    },
    "migration": {
        "uz": ("Oʻzbekiston fuqaroligini qanday olish mumkin?", "Doimiy roʻyxatdan oʻtish qanday amalga oshiriladi?",
               "Chet el fuqarosi Oʻzbekistonda qancha muddat turishi mumkin?", "Ikki fuqarolikka ruxsat beriladimi?"),
        "ru": ("Как получить гражданство Узбекистана?", "Как оформить постоянную прописку?",
               "Сколько иностранец может находиться в Узбекистане?", "Разрешено ли двойное гражданство?"),
        "en": ("How can I obtain Uzbek citizenship?", "How do I register my permanent residence?",
               "How long can a foreigner stay in Uzbekistan?", "Is dual citizenship allowed?"),
    },
    "public": {
        "uz": ("Harbiy xizmatdan ozod qilish asoslari qanday?", "Shifokor xatosi uchun qayerga shikoyat qilish mumkin?",
               "Maktabga qabul qilish tartibi qanday?", "Bepul tibbiy yordam kimga koʻrsatiladi?"),
        "ru": ("Какие основания для освобождения от военной службы?", "Куда жаловаться на врачебную ошибку?",
               "Каков порядок приёма в школу?", "Кому оказывается бесплатная медицинская помощь?"),
        "en": ("What are the grounds for exemption from military service?",
               "Where can I complain about medical malpractice?", "How does school admission work?",
               "Who gets free medical care?"),
    },
}


def _base_key(lang_key: str) -> str:
    return "uz" if lang_key in ("uz", "uz_latn", "uz_cyrl") else lang_key


@lru_cache(maxsize=4096)
def _top_concept(text: str, language: str) -> str | None:
    from lex_agent.knowledge.lexicon import get_lexicon

    matches = get_lexicon().match(text, language=language)
    return matches[0].concept.id if matches else None


def _localize(items: tuple[str, ...], lang_key: str) -> list[str]:
    if lang_key != "uz_cyrl":
        return list(items)
    from lex_agent.language.transliterator import latin_to_cyrillic

    return [latin_to_cyrillic(x) for x in items]


def follow_ups(concept_ids: list[str], domain: str | None, lang_key: str, *, limit: int = 3) -> list[str]:
    """Suggestions for an answer about ``concept_ids`` (best first) in ``domain``; [] when nothing fits."""
    base = _base_key(lang_key)
    for cid in concept_ids[:2]:
        own = CONCEPT_FOLLOW_UPS.get(cid, {}).get(base)
        if own:
            return _localize(own, lang_key)[:limit]
    pool = DOMAIN_FOLLOW_UPS.get(domain or "", {}).get(base, ())
    if not pool:
        return []
    asked = concept_ids[0] if concept_ids else None
    language = {"uz": "uz_latn", "ru": "ru", "en": "en"}[base]
    picked = [q for q in pool if asked is None or _top_concept(q, language) != asked]
    return _localize(tuple(picked), lang_key)[:limit]
