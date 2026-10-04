"""Reading a boarding pass.

Every boarding pass issued by an IATA member carries the same barcode format —
BCBP, IATA Resolution 792 — as a PDF417 on paper or an Aztec code on a phone.
A fixed-length header of 60 characters holds the mandatory fields, and
everything after it is optional and varies by airline. We read the header and
ignore the rest.

**The boarding pass does not contain the gate.** This surprises people, and it
is the single most important fact about this feature. The barcode is printed at
check-in; the gate is assigned by the airport later, often much later, and
changes afterwards. So scanning tells us the *flight*, and the gate has to come
from the airport's live flight information system — see ``flights.py``.

That is not a limitation. It is the reason the system is worth having: the chair
asks the flight board where the gate is *now*, which is precisely what a human
pushing a wheelchair from the kerb cannot do.

Field layout, positions 1-60 of the M-format header:

===========  =====  ==================================================
Position     Size   Field
===========  =====  ==================================================
1            1      Format code, always 'M'
2            1      Number of legs encoded
3-22         20     Passenger name, ``FAMILY/GIVEN TITLE``
23           1      Electronic ticket indicator
24-30        7      Operating carrier PNR
31-33        3      From airport, IATA code
34-36        3      To airport, IATA code
37-39        3      Operating carrier designator
40-44        5      Flight number
45-47        3      Date of flight, ordinal day of year
48           1      Compartment code
49-52        4      Seat number
53-57        5      Check-in sequence number
58           1      Passenger status
59-60        2      Size of the variable-length section that follows, in hex
===========  =====  ==================================================

Verify this layout against a current copy of Resolution 792 before a live trial,
and against real passes from the airlines actually serving the airport. The
standard is stable but the conditional section beyond character 60 is not, and
some carriers pad the mandatory fields in their own way.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import re
from dataclasses import dataclass

#: Length of the mandatory header. Anything shorter is not a boarding pass.
HEADER_LENGTH = 60

#: Honorifics that may trail the given name inside the 20-character name field.
_TITLES = frozenset({"MR", "MRS", "MS", "MISS", "MSTR", "MASTER", "DR", "PROF", "SIR"})

_AIRPORT_RE = re.compile(r"^[A-Z]{3}$")
_CARRIER_RE = re.compile(r"^[A-Z0-9]{2,3}$")


class BoardingPassError(ValueError):
    """The scan was not a boarding pass we can read."""


@dataclass(frozen=True)
class BoardingPass:
    """The mandatory fields of one scanned boarding pass.

    This object holds personal data — a name and a PNR, which together identify a
    traveller and their booking. Treat it as transient: read what is needed to
    dispatch a chair, then let it go. ``pnr_digest`` exists so that a repeat scan
    can be recognised without keeping the PNR itself.
    """

    passenger_family_name: str
    passenger_given_name: str
    passenger_title: str
    pnr: str
    origin: str
    destination: str
    carrier: str
    flight_number: str
    day_of_year: int
    compartment: str
    seat: str
    sequence_number: str
    legs: int

    @property
    def flight_designator(self) -> str:
        """The flight as a board would show it, e.g. ``AI612``."""
        return f"{self.carrier}{self.flight_number.lstrip('0') or '0'}"

    @property
    def display_name(self) -> str:
        """How the chair's screen greets the passenger."""
        family = self.passenger_family_name.title()
        if self.passenger_title:
            return f"{self.passenger_title.title()} {family}"
        return f"{self.passenger_given_name.title()} {family}".strip()

    def flight_date(self, year: int | None = None) -> _dt.date:
        """Resolve the ordinal day to a calendar date.

        The mandatory header carries the day of the year but not the year itself,
        so this has to be supplied or assumed. Around the new year an assumption
        is wrong roughly half the time; for dispatching a chair it does not
        matter, and for anything that does matter, pass the year explicitly.
        """
        year = year if year is not None else _dt.date.today().year
        return _dt.date(year, 1, 1) + _dt.timedelta(days=self.day_of_year - 1)

    def pnr_digest(self, secret: bytes) -> str:
        """A keyed digest of the PNR, for recognising a repeat scan.

        Keyed rather than a plain hash because the PNR space is small enough to
        enumerate: an unkeyed hash of a six-character booking reference is not
        anonymous, it is a lookup table waiting to happen.
        """
        return hmac.new(secret, self.pnr.encode("ascii"), hashlib.sha256).hexdigest()[:16]


def _field(raw: str, start: int, length: int) -> str:
    """One field, 1-indexed inclusive start as the standard numbers them."""
    return raw[start - 1 : start - 1 + length]


def _split_name(field: str) -> tuple[str, str, str]:
    """``PEREIRA/MARIA MRS`` -> (family, given, title)."""
    name = field.strip()
    if "/" not in name:
        raise BoardingPassError(f"name field has no family/given separator: {name!r}")
    family, _, rest = name.partition("/")
    family = family.strip()
    if not family:
        raise BoardingPassError("name field has an empty family name")

    parts = rest.split()
    title = ""
    if len(parts) > 1 and parts[-1].upper() in _TITLES:
        title = parts.pop().upper()
    given = " ".join(parts).strip()
    return family, given, title


def parse(scan: str) -> BoardingPass:
    """Parse a scanned BCBP string.

    Raises :class:`BoardingPassError` with a specific reason on anything that is
    not a readable pass. The reason matters: the chair's screen has to tell the
    passenger whether to rescan, or to go and find a human.
    """
    if not scan:
        raise BoardingPassError("empty scan")

    raw = scan.rstrip("\r\n")
    if len(raw) < HEADER_LENGTH:
        raise BoardingPassError(
            f"scan is {len(raw)} characters, need at least {HEADER_LENGTH}; "
            "this is probably a bag tag or a loyalty card"
        )

    if raw[0] != "M":
        raise BoardingPassError(
            f"format code is {raw[0]!r}, expected 'M'; only the multi-leg format is defined"
        )

    legs_field = _field(raw, 2, 1)
    if not legs_field.isdigit() or legs_field == "0":
        raise BoardingPassError(f"leg count {legs_field!r} is not 1-9")

    family, given, title = _split_name(_field(raw, 3, 20))

    pnr = _field(raw, 24, 7).strip()
    if not pnr:
        raise BoardingPassError("no booking reference in the pass")

    origin = _field(raw, 31, 3).strip().upper()
    destination = _field(raw, 34, 3).strip().upper()
    for code, which in ((origin, "origin"), (destination, "destination")):
        if not _AIRPORT_RE.match(code):
            raise BoardingPassError(f"{which} {code!r} is not a three-letter airport code")

    carrier = _field(raw, 37, 3).strip().upper()
    if not _CARRIER_RE.match(carrier):
        raise BoardingPassError(f"carrier {carrier!r} is not a valid designator")

    flight_number = _field(raw, 40, 5).strip().upper()
    # A trailing alphabetic suffix is permitted; the rest must be digits.
    numeric = flight_number[:-1] if flight_number[-1:].isalpha() else flight_number
    if not numeric.isdigit():
        raise BoardingPassError(f"flight number {flight_number!r} is not numeric")

    day_field = _field(raw, 45, 3).strip()
    if not day_field.isdigit() or not 1 <= int(day_field) <= 366:
        raise BoardingPassError(f"date of flight {day_field!r} is not a day of the year")

    return BoardingPass(
        passenger_family_name=family,
        passenger_given_name=given,
        passenger_title=title,
        pnr=pnr,
        origin=origin,
        destination=destination,
        carrier=carrier,
        flight_number=numeric,
        day_of_year=int(day_field),
        compartment=_field(raw, 48, 1).strip().upper(),
        seat=_field(raw, 49, 4).strip(),
        sequence_number=_field(raw, 53, 5).strip(),
        legs=int(legs_field),
    )


def encode(
    *,
    family_name: str,
    given_name: str,
    title: str = "",
    pnr: str,
    origin: str,
    destination: str,
    carrier: str,
    flight_number: str,
    day_of_year: int,
    compartment: str = "Y",
    seat: str = "",
    sequence_number: str = "",
) -> str:
    """Build a BCBP header. For tests and for the demo — not for issuing passes."""
    name = f"{family_name.upper()}/{given_name.upper()}"
    if title:
        name = f"{name} {title.upper()}"
    if len(name) > 20:
        name = name[:20]

    return (
        "M1"
        + name.ljust(20)
        + "E"
        + pnr.upper().ljust(7)
        + origin.upper().ljust(3)
        + destination.upper().ljust(3)
        + carrier.upper().ljust(3)
        + flight_number.rjust(4, "0").ljust(5)
        + f"{day_of_year:03d}"
        + compartment.upper()[:1]
        + seat.ljust(4)
        + sequence_number.ljust(5)
        + "1"
        + "00"
    )
