"""Stop words for retrieval, expressed in the same analysed form (folded + stemmed) as the index terms.

Raw word lists are kept readable; :func:`stop_terms` runs them through ``textproc`` so that whatever the
stemmer produces for "qanday", "bo'lsa" or "можно" is recognised as a stop term.
"""

from __future__ import annotations

from functools import lru_cache

from lex_agent.language.textproc import index_terms, stem_en

UZ_STOPWORDS = """
va ham hamda yoki uchun bilan bo'yicha haqida to'g'risida qanday qanaqa nima nimaga nega qancha qaysi kerak mumkin
bo'lsa bo'lgan bo'ladi bo'ladimi bo'lishi bo'lib ushbu bu shu u ular uning boshqa asosida muvofiq tartibda holatda
holda agar lekin ammo esa emas yo'q bor men meni menga mening biz siz sizga o'zim o'z kim qachon qayer qayerda
necha nechta bormi kerakmi mumkinmi hech har barcha ana mana endi keyin oldin kabi deb degan ekan edi xam iltimos
salom assalomu alaykum rahmat ayting aytib aytsangiz bilmoqchi bilmoqchiman savol javob qilsa qiladi qilish qilib
qilingan qilinadi etib etadi etish etilgan etiladi bo'lgan berilgan shuningdek jumladan yana faqat hamma qandaydir
nimadir birorta biror bir qila qilay qilaman qilyapti qilmoqchi qilmoqchiman bo'ldi bo'lyapti mumkinmi o'zi o'zingiz
juda ko'p sal ekanmi ekan yaxshi yomon to'g'ri noto'g'ri ha xo'p ok okay
orqali tomonidan sababli keyingi oldingi ichida davomida mobaynida qilsam qilishim qilishi qilishimiz
olsam bo'lsam bo'lamanmi bo'ladimi lozim kerakmi qachongacha nechchi qanchaga qanchadan qaysi
""".split()

UZ_CYRL_STOPWORDS = """
ва ҳам ҳамда ёки учун билан бўйича ҳақида тўғрисида қандай нима нега қанча қайси керак мумкин бўлса бўлган
бўлади ушбу бу шу у улар унинг бошқа асосида мувофиқ тартибда ҳолда агар лекин аммо эса эмас йўқ бор мен менга
менинг биз сиз ким қачон қаерда неча нечта ҳеч ҳар барча кейин олдин каби деб экан эди илтимос салом раҳмат
""".split()

RU_STOPWORDS = """
и в во на по с со к ко о об обо от до за из для при или как что чтобы так это этот эта эти то тот та те все всё
весь вся если мне меня мой моя мои моё я мы вы он она оно они его её их свой своя свои можно нужно надо только ли
не нет да есть был была были было будет будут который которая которые какой какая какие сколько куда где когда
почему зачем согласно порядке случае настоящего также тоже уже еще ещё очень бы же вот там тут здесь подскажите
пожалуйста здравствуйте привет спасибо вопрос ответ скажите расскажите хочу хотел хотела могу может могут
без делать сделать мой меня мне нам нас вам вас им ими него неё нее ему ей
""".split()

EN_STOPWORDS = """
the and for with that this from are was were what how does do did under about into is a an of to in on my i me
can it be if or by at should would will much many long please hello hi thanks question answer tell know want
""".split()

_KEEP = frozenset({"ish", "sud", "uy", "pul", "boj", "haq", "bola", "ota", "ona", "yer", "oy", "kun", "yil", "kam", "oz"})


@lru_cache(maxsize=4)
def stop_terms(language: str = "uz_latn") -> frozenset[str]:
    """Stop words of a query language in analysed (index-term) form, plus their raw lowercase forms."""
    out: set[str] = set()
    if language == "en":
        for w in EN_STOPWORDS:
            out.add(stem_en(w))
            out.add(w)
        return frozenset(out)
    for w in UZ_STOPWORDS:
        out.update(index_terms(w, language="uz_latn"))
        out.add(w.replace("'", ""))
    for w in UZ_CYRL_STOPWORDS:
        out.update(index_terms(w, language="uz_cyrl"))
    if language == "ru":
        for w in RU_STOPWORDS:
            out.update(index_terms(w, language="ru"))
            out.add(w)
    return frozenset(t for t in out if t and t not in _KEEP)
