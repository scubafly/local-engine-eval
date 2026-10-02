"""Quality tasks for the local-engine comparison.

Everything here is scored deterministically -- no judge model, so the result costs nothing
and is reproducible. Four shapes, chosen because they are what the developer role actually
does, and because quantisation damage shows up in them first:

  code        write a function to spec; scored by running unit tests
  json        emit a tool call against a fixed schema; scored by parsing and validating
  constraint  obey a hard output constraint; scored by regex
  recall      find one planted fact in a long context; scored by exact match

Temperature is 0 everywhere, so a rerun on the same engine should reproduce.
"""

CODE = [
    ("code-01", "Schrijf een Python-functie `is_palindrome(s)` die True geeft als s een palindroom is, "
                "waarbij spaties, interpunctie en hoofdletters niet meetellen. Alleen code, geen uitleg.",
     "assert is_palindrome('Baas, neem een racecar, neem een saab') is True\n"
     "assert is_palindrome('hallo') is False\n"
     "assert is_palindrome('') is True\n"),
    ("code-02", "Schrijf een Python-functie `chunk(lst, n)` die een lijst in opeenvolgende stukken van "
                "maximaal n elementen opdeelt en een lijst van lijsten teruggeeft. Alleen code.",
     "assert chunk([1,2,3,4,5], 2) == [[1,2],[3,4],[5]]\n"
     "assert chunk([], 3) == []\n"
     "assert chunk([1], 5) == [[1]]\n"),
    ("code-03", "Schrijf een Python-functie `roman(n)` die een geheel getal van 1 tot 3999 omzet naar "
                "een Romeins cijfer als string. Alleen code.",
     "assert roman(1) == 'I'\nassert roman(4) == 'IV'\nassert roman(1994) == 'MCMXCIV'\n"
     "assert roman(3999) == 'MMMCMXCIX'\n"),
    ("code-04", "Schrijf een Python-functie `merge_intervals(iv)` die een lijst van [start, eind]-paren "
                "samenvoegt waar ze overlappen, gesorteerd teruggegeven. Alleen code.",
     "assert merge_intervals([[1,3],[2,6],[8,10]]) == [[1,6],[8,10]]\n"
     "assert merge_intervals([]) == []\n"
     "assert merge_intervals([[5,6],[1,2]]) == [[1,2],[5,6]]\n"),
    ("code-05", "Schrijf een Python-functie `word_freq(tekst)` die een dict teruggeeft met per woord "
                "(lowercase, alleen letters en cijfers) hoe vaak het voorkomt. Alleen code.",
     "assert word_freq('De kat, de hond!') == {'de': 2, 'kat': 1, 'hond': 1}\n"
     "assert word_freq('') == {}\n"),
    ("code-06", "Schrijf een Python-functie `flatten(x)` die willekeurig geneste lijsten plat maakt tot "
                "één lijst, met behoud van volgorde. Alleen code.",
     "assert flatten([1,[2,[3,[4]]],5]) == [1,2,3,4,5]\n"
     "assert flatten([]) == []\n"
     "assert flatten([[],[[]]]) == []\n"),
    ("code-07", "Schrijf een Python-functie `parse_duration(s)` die strings als '1h30m', '45s', '2h' "
                "omzet naar het aantal seconden als int. Alleen code.",
     "assert parse_duration('1h30m') == 5400\n"
     "assert parse_duration('45s') == 45\n"
     "assert parse_duration('2h') == 7200\n"),
    ("code-08", "Schrijf een Python-functie `top_k(lst, k)` die de k grootste getallen teruggeeft, "
                "gesorteerd van groot naar klein. Alleen code.",
     "assert top_k([5,1,9,3,9], 2) == [9,9]\n"
     "assert top_k([1], 5) == [1]\n"
     "assert top_k([], 3) == []\n"),
    ("code-09", "Schrijf een Python-functie `is_valid_brackets(s)` die controleert of ronde, vierkante "
                "en accolade-haakjes correct genest zijn. Alleen code.",
     "assert is_valid_brackets('([]{})') is True\n"
     "assert is_valid_brackets('([)]') is False\n"
     "assert is_valid_brackets('') is True\n"),
    ("code-10", "Schrijf een Python-functie `diff_lines(a, b)` die twee lijsten regels vergelijkt en een "
                "lijst tuples (teken, regel) teruggeeft, met '-' voor alleen in a, '+' voor alleen in b, "
                "' ' voor gelijk, in de volgorde van een eenvoudige lijn-voor-lijn vergelijking. Alleen code.",
     "r = diff_lines(['a','b'], ['a','c'])\n"
     "assert r == [(' ','a'), ('-','b'), ('+','c')], r\n"),
]

SCHEMA = """{
  "name": "create_ticket",
  "parameters": {
    "type": "object",
    "properties": {
      "title":    {"type": "string"},
      "priority": {"type": "string", "enum": ["low", "normal", "high"]},
      "labels":   {"type": "array", "items": {"type": "string"}},
      "estimate": {"type": "number"}
    },
    "required": ["title", "priority", "labels"]
  }
}"""

JSON_TASKS = [
    ("json-01", "De koffiemachine op kantoor lekt water, dat moet snel opgelost.", "high"),
    ("json-02", "Iemand mag ooit de kleur van de footer aanpassen, geen haast.", "low"),
    ("json-03", "De betaalpagina geeft een 500 bij iedere order. Productie staat stil.", "high"),
    ("json-04", "Voeg een dark mode toe aan het dashboard, zou fijn zijn volgende sprint.", "normal"),
    ("json-05", "De zoekfunctie negeert accenten, gebruikers klagen er wekelijks over.", "normal"),
    ("json-06", "Alle back-ups zijn sinds maandag mislukt.", "high"),
    ("json-07", "De tekst 'Inloggen' mag 'Aanmelden' worden.", "low"),
    ("json-08", "Schrijf tests voor de factuur-export, die is nu ongedekt.", "normal"),
    ("json-09", "Het SSL-certificaat verloopt morgen.", "high"),
    ("json-10", "Ruim de ongebruikte CSS-klassen op als er tijd over is.", "low"),
]

CONSTRAINT = [
    ("con-01", "Antwoord met precies één woord: wat is de hoofdstad van Frankrijk?",
     r"^\s*Parijs\.?\s*$"),
    ("con-02", "Geef alleen het getal, geen tekst en geen eenheid: hoeveel seconden zitten er in een uur?",
     r"^\s*3600\s*$"),
    ("con-03", "Antwoord uitsluitend met JA of NEE, in hoofdletters: is 17 een priemgetal?",
     r"^\s*JA\s*$"),
    ("con-04", "Noem drie kleuren, gescheiden door precies één komma zonder spaties, niets anders.",
     r"^\s*[A-Za-zéëï]+,[A-Za-zéëï]+,[A-Za-zéëï]+\s*$"),
    ("con-05", "Antwoord in exact vijf woorden waarom tests nuttig zijn. Geen interpunctie.",
     r"^\s*(?:[A-Za-zéëï]+\s+){4}[A-Za-zéëï]+\s*$"),
]

# One planted fact in a long filler body. The filler is deterministic, so every engine sees
# byte-identical input, and the needle sits mid-document where recall is hardest.
def haystack(needle_line: str, lines: int = 350) -> str:
    body = []
    for i in range(lines):
        if i == lines // 2:
            body.append(needle_line)
        body.append(f"Regel {i:04d}: logboek van de bouwploeg, geen bijzonderheden te melden, "
                    f"materiaal geleverd, weer droog, ploegleider aanwezig, meting {i * 7 % 97} mm.")
    return "\n".join(body)

RECALL = [
    ("rec-01", "De sleutel van de meterkast hangt achter het paneel met code 8831.", "8831"),
    ("rec-02", "De noodcontactpersoon op deze locatie is mevrouw Visserman.", "Visserman"),
    ("rec-03", "De fundering is gegoten op 14 maart en moet 28 dagen uitharden.", "28"),
    ("rec-04", "Het serienummer van de hijskraan is KR-7742-B.", "KR-7742-B"),
    ("rec-05", "De vergunning loopt af in week 37 van volgend jaar.", "37"),
]


def build():
    """Return a list of task dicts: id, kind, prompt, max_tokens, and the scoring payload."""
    tasks = []
    for tid, prompt, tests in CODE:
        tasks.append({"id": tid, "kind": "code", "prompt": prompt, "max_tokens": 3000,
                      "tests": tests})
    for tid, melding, prio in JSON_TASKS:
        tasks.append({"id": tid, "kind": "json", "max_tokens": 1500, "priority": prio,
                      "prompt": "Je roept een tool aan. Hier is het schema:\n\n" + SCHEMA +
                                "\n\nMelding: " + melding +
                                "\n\nGeef uitsluitend het argumenten-object als JSON, zonder "
                                "codeblok en zonder uitleg. Kies de juiste priority."})
    for tid, prompt, pattern in CONSTRAINT:
        tasks.append({"id": tid, "kind": "constraint", "prompt": prompt, "max_tokens": 1200,
                      "pattern": pattern})
    for tid, needle, answer in RECALL:
        tasks.append({"id": tid, "kind": "recall", "max_tokens": 1500, "answer": answer,
                      "prompt": "Hieronder staat een logboek. Lees het en beantwoord daarna de vraag "
                                "met alleen het gevraagde gegeven.\n\n" + haystack(needle) +
                                "\n\nVraag: " + {
                                    "8831": "Wat is de code achter het paneel?",
                                    "Visserman": "Wie is de noodcontactpersoon?",
                                    "28": "Hoeveel dagen moet de fundering uitharden?",
                                    "KR-7742-B": "Wat is het serienummer van de hijskraan?",
                                    "37": "In welke week loopt de vergunning af?",
                                }[answer]})
    return tasks
