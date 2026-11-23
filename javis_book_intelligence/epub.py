"""DRM-free EPUB 2/3 parser using ZIP + ElementTree + BeautifulSoup.

No EPUB content is executed; only OPF, XHTML and plain text are read.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath, Path
from urllib.parse import unquote, urlsplit
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from bs4 import BeautifulSoup

MAX_UNCOMPRESSED = 220 * 1024 * 1024
MAX_MEMBERS = 8000
MAX_ENTRY = 50 * 1024 * 1024
NS = {"c":"urn:oasis:names:tc:opendocument:xmlns:container", "opf":"http://www.idpf.org/2007/opf", "dc":"http://purl.org/dc/elements/1.1/"}

class EpubError(ValueError):
    pass

@dataclass(frozen=True)
class Chapter:
    title: str
    href: str
    text: str

@dataclass(frozen=True)
class ParsedBook:
    title: str
    subtitle: str
    language: str
    publisher: str
    publication_year: int | None
    isbn: str
    authors: list[str]
    chapters: list[Chapter]


def _read(zf: zipfile.ZipFile, name: str) -> bytes:
    try:
        return zf.read(name)
    except (KeyError, RuntimeError, ValueError) as e:
        raise EpubError(f"Missing or unreadable EPUB member: {name}") from e


def _safe_member(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name) and not name.startswith("/") and "\\" not in name and ".." not in p.parts and not name.startswith("//")


def _resolve(base: str, relative: str) -> str:
    rel = unquote(urlsplit(relative).path)
    result = posixpath.normpath(posixpath.join(posixpath.dirname(base), rel))
    if not _safe_member(result):
        raise EpubError("Unsafe EPUB path")
    return result


def _first_text(el: ET.Element, xpath: str) -> str:
    node = el.find(xpath, NS)
    return "" if node is None else ("".join(node.itertext())).strip()


def _paragraphs_to_text(soup: BeautifulSoup) -> str:
    for item in soup(["script", "style", "nav", "svg", "noscript", "head"]):
        item.decompose()
    body = soup.body or soup
    text = body.get_text(separator="\n", strip=True)
    lines = [re.sub(r"[\t ]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def parse_epub(path: Path) -> ParsedBook:
    if not zipfile.is_zipfile(path):
        raise EpubError("File is not a valid ZIP/EPUB")
    try:
        with zipfile.ZipFile(path) as zf:
            entries = zf.infolist()
            if len(entries) > MAX_MEMBERS:
                raise EpubError("EPUB has too many entries")
            if sum(x.file_size for x in entries) > MAX_UNCOMPRESSED or any(x.file_size > MAX_ENTRY for x in entries):
                raise EpubError("EPUB uncompressed data exceeds safety limit")
            if any(not _safe_member(x.filename) for x in entries):
                raise EpubError("EPUB contains an unsafe internal path")
            if any(x.file_size > 1_000_000 and x.file_size > max(x.compress_size, 1) * 1000 for x in entries):
                raise EpubError("EPUB contains an abnormal compression ratio")
            container = ET.fromstring(_read(zf, "META-INF/container.xml"))
            rootfile = container.find(".//c:rootfile", NS)
            if rootfile is None or not rootfile.get("full-path"):
                raise EpubError("No OPF rootfile in container.xml")
            opf_path = rootfile.get("full-path", "")
            if not _safe_member(opf_path):
                raise EpubError("Unsafe OPF path")
            opf = ET.fromstring(_read(zf, opf_path))
            metadata = opf.find("opf:metadata", NS)
            manifest = opf.find("opf:manifest", NS)
            spine = opf.find("opf:spine", NS)
            if metadata is None or manifest is None or spine is None:
                raise EpubError("Incomplete OPF metadata/manifest/spine")
            title = _first_text(metadata, "dc:title") or path.stem
            language = _first_text(metadata, "dc:language")
            publisher = _first_text(metadata, "dc:publisher")
            date = _first_text(metadata, "dc:date")
            year_match = re.search(r"\b(1[0-9]{3}|20[0-9]{2}|2100)\b", date)
            year = int(year_match.group(1)) if year_match else None
            isbn = ""
            for identifier in metadata.findall("dc:identifier", NS):
                candidate = "".join(identifier.itertext()).strip()
                if "isbn" in candidate.lower() or re.fullmatch(r"[0-9Xx-]{10,17}", candidate):
                    isbn = candidate
                    break
            authors = list(dict.fromkeys("".join(x.itertext()).strip() for x in metadata.findall("dc:creator", NS)))
            authors = [a for a in authors if a]
            resources = {item.get("id"): item.get("href", "") for item in manifest.findall("opf:item", NS)}
            chapters = []
            for ref in spine.findall("opf:itemref", NS):
                idref = ref.get("idref")
                if not idref or idref not in resources:
                    continue
                href = _resolve(opf_path, resources[idref])
                if not href.lower().endswith((".xhtml", ".html", ".htm", ".xml")):
                    continue
                raw = _read(zf, href)
                soup = BeautifulSoup(raw, "html.parser")
                text = _paragraphs_to_text(soup)
                if not text:
                    continue
                heading = soup.find(re.compile(r"^h[1-6]$"))
                unit_title = heading.get_text(" ", strip=True) if heading else ""
                if not unit_title and soup.title:
                    unit_title = soup.title.get_text(" ", strip=True)
                if not unit_title:
                    unit_title = f"Phần {len(chapters) + 1}"
                chapters.append(Chapter(title=unit_title[:300], href=href, text=text))
            if not chapters:
                raise EpubError("No readable XHTML chapters found in EPUB spine")
            return ParsedBook(title=title[:500], subtitle="", language=language[:50],
                              publisher=publisher[:250], publication_year=year,
                              isbn=isbn[:90], authors=authors, chapters=chapters)
    except zipfile.BadZipFile as e:
        raise EpubError("Damaged EPUB ZIP structure") from e
    except ET.ParseError as e:
        raise EpubError("Malformed EPUB XML metadata") from e
