"""What the chair says, in the languages its passengers actually speak.

A passenger who needs a wheelchair is disproportionately likely to be elderly,
and an elderly passenger in Goa or Maharashtra is markedly less likely to read
English than the airport's signage assumes. Every message the chair shows or
speaks lives here, in all four languages, so that none of them can be added in
English and quietly forgotten.

    >>> say("taking_to_gate", "mr", gate="4")
    'तुम्हाला गेट ४ कडे नेत आहे.'

Screens cycle through the languages; voice uses the one the passenger selected,
defaulting to the local language rather than to English.

----

**These translations need a native speaker before they are shown to anybody.**

They are a working draft so the plumbing can be built and tested, not finished
copy. The Konkani in particular should be checked by a Goan speaker: it is
written here in Devanagari, which is the official script in Goa, but Konkani has
real dialect variation and the register that suits a public announcement is not
something to guess at. Budget an afternoon with a native speaker of each
language; it is the cheapest quality improvement available to this project.

Numerals are a decision, not an oversight: Devanagari digits (४) are used in the
Devanagari-script messages because that is what a reader of those scripts expects
on a sign. If testing with passengers says otherwise, change ``format_number``
and nothing else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: The languages the chair speaks. ``kok`` is Konkani, ISO 639-3.
LANGUAGES: tuple[str, ...] = ("en", "hi", "mr", "kok")

#: Order in which a screen cycles. Local language first, English last — the
#: opposite of the usual airport default, and deliberate.
DISPLAY_ORDER: tuple[str, ...] = ("kok", "mr", "hi", "en")

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "हिंदी",
    "mr": "मराठी",
    "kok": "कोंकणी",
}

_DEVANAGARI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


class MissingTranslation(KeyError):
    """A message was asked for in a language that has no copy for it."""


# Keyed by message id, then language. Every message must exist in every
# language with exactly the same placeholders — enforced by
# :func:`validate_catalogue` and by the test suite.
CATALOGUE: dict[str, dict[str, str]] = {
    "welcome": {
        "en": "Welcome, {name}.",
        "hi": "आपका स्वागत है, {name}।",
        "mr": "आपले स्वागत आहे, {name}.",
        "kok": "तुमकां येवकार, {name}.",
    },
    "starting": {
        "en": "Please hold on. Starting now.",
        "hi": "कृपया पकड़कर बैठें। अब चल रहे हैं।",
        "mr": "कृपया घट्ट धरा. आता निघत आहे.",
        "kok": "उपकार करून घट्ट धरात. आतां वता.",
    },
    "taking_to_gate": {
        "en": "Taking you to Gate {gate}.",
        "hi": "आपको गेट {gate} तक ले जा रहे हैं।",
        "mr": "तुम्हाला गेट {gate} कडे नेत आहे.",
        "kok": "तुमकां गेट {gate} कडेन व्हरतां.",
    },
    "taking_to_lounge": {
        "en": "Taking you to the assistance lounge.",
        "hi": "आपको सहायता कक्ष तक ले जा रहे हैं।",
        "mr": "तुम्हाला मदत कक्षाकडे नेत आहे.",
        "kok": "तुमकां आदार कक्षाकडेन व्हरतां.",
    },
    "no_gate_yet": {
        "en": "Your gate has not been announced yet. We will come back for you.",
        "hi": "आपका गेट अभी घोषित नहीं हुआ है। हम आपको लेने वापस आएंगे।",
        "mr": "तुमचा गेट अजून जाहीर झालेला नाही. आम्ही तुम्हाला न्यायला परत येऊ.",
        "kok": "तुमचो गेट अजून जाहीर जाल्लो ना. आमी तुमकां व्हरूंक परत येतले.",
    },
    "gate_changed": {
        "en": "Your gate has changed. We are now going to Gate {gate}.",
        "hi": "आपका गेट बदल गया है। अब हम गेट {gate} जा रहे हैं।",
        "mr": "तुमचा गेट बदलला आहे. आता आपण गेट {gate} कडे जात आहोत.",
        "kok": "तुमचो गेट बदल्ला. आतां आमी गेट {gate} कडेन वतांव.",
    },
    "arrived_at_gate": {
        "en": "We have arrived at Gate {gate}.",
        "hi": "हम गेट {gate} पर पहुँच गए हैं।",
        "mr": "आपण गेट {gate} येथे पोहोचलो आहोत.",
        "kok": "आमी गेट {gate} हांगा पावले.",
    },
    "arrived_at_lounge": {
        "en": "We have arrived at the assistance lounge.",
        "hi": "हम सहायता कक्ष पहुँच गए हैं।",
        "mr": "आपण मदत कक्षात पोहोचलो आहोत.",
        "kok": "आमी आदार कक्षांत पावले.",
    },
    "chair_on_the_way": {
        "en": "A chair is on its way. About {minutes} minutes.",
        "hi": "एक कुर्सी आ रही है। लगभग {minutes} मिनट।",
        "mr": "एक खुर्ची येत आहे. सुमारे {minutes} मिनिटे.",
        "kok": "एक कदेल येता. सुमार {minutes} मिनटां.",
    },
    "obstacle_pausing": {
        "en": "Pausing. Someone is in the way.",
        "hi": "रुक रहे हैं। कोई रास्ते में है।",
        "mr": "थांबत आहे. कोणीतरी वाटेत आहे.",
        "kok": "रावतां. कोण तरी वाटेर आसा.",
    },
    "resuming": {
        "en": "Thank you for waiting. Moving again.",
        "hi": "प्रतीक्षा के लिए धन्यवाद। फिर से चल रहे हैं।",
        "mr": "वाट पाहिल्याबद्दल धन्यवाद. पुन्हा निघत आहे.",
        "kok": "रावल्ल्या खातीर देव बरें करूं. परत वतां.",
    },
    "stopped_for_staff": {
        "en": "Stopped. Please wait for a member of staff.",
        "hi": "रुक गए हैं। कृपया कर्मचारी की प्रतीक्षा करें।",
        "mr": "थांबलो आहे. कृपया कर्मचाऱ्याची वाट पहा.",
        "kok": "रावलां. उपकार करून कर्मचाऱ्याची वाट पळयात.",
    },
    "scan_failed": {
        "en": "That did not scan. Please hold your boarding pass to the reader again.",
        "hi": "यह स्कैन नहीं हुआ। कृपया अपना बोर्डिंग पास फिर से रीडर के सामने रखें।",
        "mr": "हे स्कॅन झाले नाही. कृपया तुमचा बोर्डिंग पास पुन्हा रीडरसमोर धरा.",
        "kok": "हें स्कॅन जालें ना. उपकार करून तुमचो बोर्डिंग पास परत रीडरामुखार धरात.",
    },
    "flight_not_found": {
        "en": "We cannot find flight {flight} today. Please check with your airline.",
        "hi": "आज हमें उड़ान {flight} नहीं मिल रही। कृपया अपनी एयरलाइन से पूछें।",
        "mr": "आज आम्हाला उड्डाण {flight} सापडत नाही. कृपया तुमच्या विमान कंपनीकडे विचारा.",
        "kok": "आयज आमकां विमान {flight} मेळना. उपकार करून तुमच्या विमान कंपनीकडेन विचारात.",
    },
}


@dataclass(frozen=True)
class Announcement:
    """One message, rendered in every language, ready for a screen to cycle."""

    message_id: str
    by_language: dict[str, str]

    def __getitem__(self, language: str) -> str:
        return self.by_language[language]

    @property
    def screen_lines(self) -> list[str]:
        """In display order: local languages first, English last."""
        return [self.by_language[lang] for lang in DISPLAY_ORDER]


def format_number(value: object, language: str) -> str:
    """Render a number in the digits a reader of that script expects."""
    text = str(value)
    if language in ("hi", "mr", "kok"):
        return text.translate(_DEVANAGARI_DIGITS)
    return text


def say(message_id: str, language: str, **params: object) -> str:
    """One message in one language.

    Falls back to English rather than raising, because a chair that has stopped
    and cannot explain why is worse than a chair that explains in the wrong
    language. The fallback is logged by the caller, not silently swallowed.
    """
    messages = CATALOGUE.get(message_id)
    if messages is None:
        raise MissingTranslation(f"no message {message_id!r} in the catalogue")

    template = messages.get(language) or messages["en"]
    localised = {key: format_number(value, language) for key, value in params.items()}
    try:
        return template.format(**localised)
    except KeyError as exc:
        raise MissingTranslation(
            f"message {message_id!r} in {language!r} wants {exc.args[0]!r}, which was not given"
        ) from exc


def announce(message_id: str, **params: object) -> Announcement:
    """One message in every language at once."""
    return Announcement(
        message_id=message_id,
        by_language={lang: say(message_id, lang, **params) for lang in LANGUAGES},
    )


def placeholders(template: str) -> set[str]:
    return set(_PLACEHOLDER_RE.findall(template))


def validate_catalogue() -> list[str]:
    """Check the catalogue for the mistakes that ship a blank screen.

    Returns a list of problems, empty when the catalogue is sound. Run in the
    test suite, so that a message added in English alone fails the build rather
    than silently falling back for every passenger who does not read English.
    """
    problems: list[str] = []

    for message_id, messages in CATALOGUE.items():
        if "en" not in messages:
            problems.append(f"{message_id} has no English copy to fall back to")
            continue

        expected = placeholders(messages["en"])
        for language in LANGUAGES:
            if language not in messages:
                problems.append(f"{message_id} is missing {language}")
                continue

            text = messages[language]
            if not text.strip():
                problems.append(f"{message_id} in {language} is empty")

            found = placeholders(text)
            if found != expected:
                problems.append(
                    f"{message_id} in {language} has placeholders {sorted(found)}, "
                    f"English has {sorted(expected)}"
                )

    for language in LANGUAGES:
        if language not in LANGUAGE_NAMES:
            problems.append(f"{language} has no name to show in a language picker")

    return problems
