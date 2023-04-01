"""
pelican.plugins.busineess_cards
==================================

Plugin to generate pages from business vcards (vcf files).

"""

import base64
import logging
from datetime import datetime, timedelta
from os import path

import vobject
from pelican import signals
from pelican.generators import Generator
from pelican.readers import BaseReader

logger = logging.getLogger(__name__)

FILE_ENDING = "vcf"


class VCardReader(BaseReader):
    enabled = True

    file_extension = [FILE_ENDING]

    def read(self, filename):
        metadata = {
            "title": "testtitle",
            "afilename": filename,
            "template": "vcard",
            # 'category': ['vcard'],
            "vcard": {},
            "social": {},
            "urls": {},
            "phone": {},
            "email": {},
            "address": {},
            "bday": {},
            # 'qrcode': {}
        }

        if not filename.endswith(FILE_ENDING):
            return "", {}

        def append_to_metadata(data, data_key):
            key = "-".join(
                (
                    [e for e in data.params.get("TYPE") or [] if e not in ["pref"]]
                    or ["HOME"]
                )
            )
            logger.debug(f"{data.value} - {data.params} -> {key}")
            metadata[data_key].setdefault(key, []).append(data.value)

        with open(filename, "rb") as fh:
            content = fh.read()

            vcard = None
            for enc in ["utf-8", "latin-1", "Windows-1250", "ISO-8859-1"]:
                try:
                    vcard = vobject.readOne(
                        content.decode(enc)
                        .replace("\n\n", "\n")
                        .replace("\r\r", "\r")
                        .replace("\r\n\r\n", "\r\n")
                    )
                except Exception as err:
                    logger.warning(
                        f"unable to decode and parse {filename} content with {enc}: {err}"
                    )
                else:
                    break
            if not vcard:
                return "", {}

            metadata["vcard"] = vcard
            metadata["vcardfile"] = ".".join(
                [vcard.fn.value.replace(" ", "_"), FILE_ENDING]
            )
            metadata["photo"] = "data:image/{};{},{}".format(
                vcard.photo.params["TYPE"][0].lower(),
                {"b": "base64"}.get(vcard.photo.params["ENCODING"][0].lower()),
                base64.b64encode(vcard.photo.value).decode("utf-8"),
            )

            if hasattr(vcard, "bday"):
                metadata["bday"]["value"] = vcard.bday.value
                bday = datetime.strptime(vcard.bday.value, "%Y-%m-%d").date()
                metadata["bday"]["object"] = bday

                event = vobject.iCalendar()
                event.add("vevent")
                event.vevent.add("summary").value = f"{vcard.fn.value} Birthday"
                event.vevent.add("dtstart").value = bday
                event.vevent.add("dtend").value = bday + timedelta(days=1)
                event.vevent.add("rrule").value = "FREQ=YEARLY"
                data = event.serialize()
                metadata["bday"][
                    "href"
                ] = "data:application/ics;name=event.ics;base64,{}".format(
                    base64.b64encode(data.encode("utf-8")).decode("utf-8")
                )

            # urls
            for url in vcard.url_list:
                found = False
                for social in ["linkedin", "github", "twitter", "gitlab", "facebook"]:
                    if found := social in url.value:
                        metadata["social"].setdefault(social, []).append(url.value)
                        break

                if not found:
                    append_to_metadata(url, "urls")

            # emails
            for email in vcard.email_list:
                append_to_metadata(email, "email")

            # phones
            for phone in vcard.tel_list:
                append_to_metadata(phone, "phone")

            # addresses
            for adr in vcard.adr_list:
                res = []
                for k in [
                    "box",
                    "street",
                    "extended",
                    ["code", "city"],
                    "region",
                    "country",
                ]:
                    elem = " ".join(
                        [
                            getattr(adr.value, e)
                            for e in (k if isinstance(k, list) else [k])
                            if hasattr(adr.value, e)
                        ]
                    )
                    if elem:
                        res.append(elem)
                adr.value.adr_list = res
                append_to_metadata(adr, "address")

        return f"{vcard.fn.value} Business card", metadata


class VCardGenerator(Generator):
    def generate_output(self, writer):
        for p in self.context["pages"]:
            if vcard := p.metadata.get("vcard"):
                file_name = path.join(
                    self.settings["OUTPUT_PATH"],
                    p.save_as.replace("index.html", p.metadata["vcardfile"]),
                )
                with open(file_name, "w") as fh:
                    # TODO add url to vcf ??
                    fh.write(vcard.serialize())


def get_generator(generator):
    return VCardGenerator


def add_reader(readers):
    readers.reader_classes[FILE_ENDING] = VCardReader


# This is how pelican works.
def register():
    signals.readers_init.connect(add_reader)
    signals.get_generators.connect(get_generator)


#
