#!/usr/bin/env python3
"""A command-line tool used to check links in docusaurus markdown documentation

To check all of our markdown documentation, from the repo root run:
python ./docs/checks/docs_link_checker.py -p docs -r docs -sr static -s docs -sp static --skip-external

The above command:
    - -p docs (also --path): The path to the markdown files you want to check. For example, if you wanted to check only the tutorial files, you could specify docs/tutorials
    - -r docs (also --docs-root): The root of the docs folder, used to resolve absolute and docroot paths
    - -sr static (also --static-root): The root of the static assets folder, used to resolve absolute paths for images
    - -s docs (also --site-prefix): The site path prefix, used to resolve abosulte paths (ex: in http://blah/docs, it is the docs part)
    - -sp static (also --static-prefix): The site static folder prefix, used to resolve abosulte image paths
    - --skip-external: If present, external (http) links are not checked
"""

from __future__ import annotations

import logging
import pathlib
import re
import sys
from typing import List, Optional

import click
import requests

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


class LinkReport:
    """Used to capture the details of a broken link

    Attributes:
        link: The link that is broken.
        file: The file in which the link is found.
        message: A message describing the failure.
    """

    def __init__(self, link: str, file: pathlib.Path, message: str):
        self.link = link
        self.file = file
        self.message = message

    def __str__(self):  # type: ignore[explicit-override] # FIXME
        return f"{self.message}: File: {self.file}, Link: {self.link}"


class LinkChecker:
    """Checks image and file links in a set of markdown files."""

    def __init__(  # noqa: PLR0913 # too many arguments
        self,
        docs_path: pathlib.Path,
        docs_root: pathlib.Path,
        static_root: pathlib.Path,
        site_prefix: str,
        static_prefix: str,
        skip_external: bool = False,
    ):
        """Initializes LinkChecker

        Args:
            docs_path: The directory of markdown (.md) files whose links you want to check
            docs_root: The root directory, used to resolve absolute and docroot paths
            site_prefix: The top-level folder (ex: /docs) used to resolve absolute links to local files
            static_prefix: The top-level static folder (ex: /static) used to resolve absolute image links to local files
            skip_external: Whether or not to skip checking external (http..) links
        """
        self._docs_path = docs_path
        self._docs_root = docs_root
        self._static_root = static_root
        self._site_prefix = site_prefix.strip("/")
        self._static_prefix = static_prefix.strip("/")
        self._skip_external = skip_external

        markdown_link_regex = r"!?\[(.*)\]\((.*?)\)"  # inline links, like [Description](link), images start with !
        self._markdown_link_pattern = re.compile(markdown_link_regex)

        external_link_regex = r"^https?:\/\/"  # links that start with http or https
        self._external_link_pattern = re.compile(external_link_regex)

        # with versioned docs, an absolute link may contain version information
        version_info_regex = r"//"
        self._version_info_pattern = re.compile(version_info_regex)

        # links that being with /{site_prefix}/(?:/(?P<version>))?/(?P<path>), may end with #abc
        # ex: ^/docs(?:/(?P<version>\d{1,2}\.\d{1,2}\.\d{1,2}))?/(?P<path>[\w/-]+?)(?:#\S+)?$
        #     /docs/0.15.50/cli#anchor
        absolute_link_regex = (
            r"^/"
            + site_prefix
            + r"(?:/(?P<version>\d{1,2}\.\d{1,2}\.\d{1,2}))?/(?P<path>[\w/-]+?)(?:#\S+)?$"
        )
        self._absolute_link_pattern = re.compile(absolute_link_regex)

        absolute_file_regex = rf"(?!(\/{site_prefix}\/))\/\S+\.mdx?(#[^'\"]+)?"
        self._absolute_file_pattern = re.compile(absolute_file_regex)

        # docroot links start without a . or a slash
        docroot_link_regex = r"^(?P<path>\w[\.\w\/-]+\.md)(?:#\S+)?$"
        self._docroot_link_pattern = re.compile(docroot_link_regex)

        # links starting a . or .., file ends with .md, may include an anchor with #abc
        relative_link_regex = r"^(?P<path>\.\.?[\.\w\/-]+\.md)(?:#\S+)?$"
        self._relative_link_pattern = re.compile(relative_link_regex)

        absolute_image_regex = r"^\/(?P<path>[\w\/-]+\.\w{3,4})$"
        self._absolute_image_pattern = re.compile(absolute_image_regex)

        # ending with a 3-4 character suffix
        relative_image_regex = r"^(?P<path>\.\.?[\.\w\/-]+\.\w{3,4})$"
        self._relative_image_pattern = re.compile(relative_image_regex)

    def _is_image_link(self, markdown_link: str) -> bool:
        return markdown_link.startswith("!")

    def _is_doc_link(self, markdown_link: str) -> bool:
        return not self._is_image_link(markdown_link)

    def _is_anchor_link(self, link: str) -> bool:
        return link.startswith("#")

    def _check_external_link(
        self, link: str, file: pathlib.Path
    ) -> Optional[LinkReport]:
        if self._skip_external:
            return None

        logger.debug(f"Checking external link {link} in file {file}", link, file)

        try:
            response = requests.get(link)

            if 400 <= response.status_code < 500:
                logger.info(
                    f"External link {link} failed in file {file} with code {response.status_code}"
                )
                return LinkReport(
                    link,
                    file,
                    f"External link returned status code: {response.status_code}",
                )
            else:
                logger.debug(
                    f"External link {link} successful in file {file}, response code: {response.status_code}",
                )
                return None
        except requests.exceptions.ConnectionError as err:
            logger.info(
                f"External link {link} in file {file} raised a connection error"
            )
            return LinkReport(
                link, file, f"External link raised a connection error {err.errno}"
            )

    def _get_absolute_path(self, path: pathlib.Path | str) -> pathlib.Path:
        return self._docs_root.joinpath(path).resolve()

    def _get_absolute_static_path(self, path: pathlib.Path | str) -> pathlib.Path:
        return self._static_root / path

    def _get_relative_path(
        self, file: pathlib.Path, path: pathlib.Path | str
    ) -> pathlib.Path:
        # link should be relative to the location of the current file
        return file.parent / path

    def _get_docroot_path(self, path: pathlib.Path | str) -> pathlib.Path:
        return self._docs_path / path

    def _check_absolute_link(
        self,
        link: str,
        file: pathlib.Path,
        path: pathlib.Path | str,
        version: Optional[str],
    ) -> Optional[LinkReport]:
        logger.debug(f"Checking absolute link {link} in file {file}")

        if version:
            logger.debug(f"Skipping absolute link {link} due to version information")
            return None

        # absolute links should point to files that exist (with the .md extension added)
        md_file = pathlib.Path(path).resolve().with_suffix(".md")
        logger.debug(f"Absolute link {link} resolved to path {md_file}")

        if not md_file.is_file():
            logger.info(f"Absolute link {link} in file {file} was not found")
            return LinkReport(link, file, f"Linked file {md_file} not found")
        else:
            logger.debug(f"Absolute link {link} in file {file} found")
            return None

    def _check_absolute_image(
        self, link: str, file: pathlib.Path, path: pathlib.Path
    ) -> Optional[LinkReport]:
        logger.debug(f"Checking absolute image {link} in file {file}")

        image_file = self._get_absolute_static_path(path)
        if not image_file.is_file():
            logger.info(f"Absolute image {link} in file {file} was not found")
            return LinkReport(link, file, f"Image {image_file} not found")
        else:
            logger.debug(f"Absolute image {link} in file {file} found")
            return None

    def _check_relative_link(
        self, link: str, file: pathlib.Path, path: pathlib.Path
    ) -> Optional[LinkReport]:
        logger.debug(f"Checking relative link {link} in file {file}")

        md_file = self._get_relative_path(file, path)
        logger.debug(f"Relative link {link} resolved to path {md_file}")

        if not md_file.is_file():
            logger.info(f"Relative link {link} in file {file} was not found")
            return LinkReport(link, file, f"Linked file {md_file} not found")
        else:
            logger.debug(f"Relative link {link} in file{file} found")
            return None

    def _check_relative_image(
        self, link: str, file: pathlib.Path, path: pathlib.Path
    ) -> Optional[LinkReport]:
        logger.debug(f"Checking relative image {link} in file {file}")

        image_file = self._get_relative_path(file, path)
        if not image_file.is_file():
            logger.info(f"Relative image {link} in file {file} was not found")
            return LinkReport(link, file, f"Image {image_file} not found")
        else:
            logger.debug(f"Relative image {link} in file {file} found")
            return None

    def _check_docroot_link(
        self, link: str, file: pathlib.Path, path: pathlib.Path | str
    ) -> Optional[LinkReport]:
        logger.debug(f"Checking docroot link {link} in file {file}")

        md_file = self._get_docroot_path(path)
        if not md_file.is_file():
            logger.info(f"Docroot link {link} in file {file} was not found")
            return LinkReport(link, file, f"Linked file {md_file} not found")
        else:
            logger.debug(f"Docroot link {link} in file {file} found")
            return None

    def _check_link(  # noqa: PLR0912, C901 # too complex
        self, match: re.Match, file: pathlib.Path
    ) -> Optional[LinkReport]:
        """Checks that a link is valid. Valid links are:
        - Absolute links that begin with a forward slash and the specified site prefix (ex: /docs) with no suffix
        - Absolute images with an image suffix
        - Relative links that begin with either . or .. and have a .md suffix
        - Relative images with an image suffix
        - Docroot links that begin with a character (neither . or /) are relative to the doc root (ex: /docs) and have a .md suffix
        - Absolute file paths for markdown files

        Args:
            match: A positive match of a markdown link (ex: [...](...)) or image
            file: The file where the match was found

        Returns:
            A LinkReport if the link is broken, otherwise None
        """
        link = match.group(2)

        # skip links that are anchor only (start with #)
        if self._is_anchor_link(link):
            return None

        if self._external_link_pattern.match(link):
            result = self._check_external_link(link, file)
        elif self._is_image_link(match.group(0)):
            match = self._relative_image_pattern.match(link)  # type: ignore[assignment]
            if match:
                result = self._check_relative_image(link, file, match.group("path"))
            else:
                match = self._absolute_image_pattern.match(link)
                if match:
                    result = self._check_absolute_image(link, file, match.group("path"))
                else:
                    result = LinkReport(link, file, "Invalid image link format")
        else:
            match = self._relative_link_pattern.match(link)  # type: ignore[assignment]
            if match:
                result = self._check_relative_link(link, file, match.group("path"))
            else:
                match = self._absolute_link_pattern.match(link)
                if match:
                    result = self._check_absolute_link(
                        link, file, match.group("path"), match.group("version")
                    )
                elif match := self._absolute_file_pattern.match(link):
                    # This could be more robust like the other checks, but the level of complexity will be high for versioned_docs,
                    # and we should be able to just set onBrokenMarkdownLinks: 'error'
                    result = None
                else:
                    match = self._docroot_link_pattern.match(link)
                    if match:
                        result = self._check_docroot_link(
                            link, file, match.group("path")
                        )
                    else:
                        result = LinkReport(link, file, "Invalid link format")

        return result

    def check_file(self, file: pathlib.Path) -> List[LinkReport]:
        """Looks for all the links in a file and checks them.

        Returns:
            A list of broken links, or an empty list if no links are broken
        """
        with open(file) as f:
            contents = f.read()

        matches = self._markdown_link_pattern.finditer(contents)

        result: List[LinkReport] = []

        for match in matches:
            report = self._check_link(match, file)

            if report:
                result.append(report)

            # sometimes the description may contain a reference to an image
            nested_match = self._markdown_link_pattern.match(match.group(1))
            if nested_match:
                report = self._check_link(nested_match, file)

                if report:
                    result.append(report)

        return result


@click.command(help="Checks links and images in Docusaurus markdown files")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=True, path_type=pathlib.Path),
    default=".",
    help="Path to markdown file(s) to check",
)
@click.option(
    "--docs-root",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=pathlib.Path),
    default=None,
    help="Root to all docs for link checking",
)
@click.option(
    "--static-root",
    "-sr",
    type=click.Path(exists=True, file_okay=False, path_type=pathlib.Path),
    default="docs/docusaurus/static",
    help="Root (static folder) to all images for link validating",
)
@click.option(
    "--site-prefix",
    "-s",
    default="docs",
    help="Top-most folder in the docs URL for resolving absolute paths",
)
@click.option(
    "--static-prefix",
    "-sp",
    default="static",
    help="Top-most folder in the site URL for resolving absolute image paths",
)
@click.option("--skip-external", is_flag=True)
def scan_docs_click(  # noqa: PLR0913
    path: pathlib.Path,
    docs_root: Optional[pathlib.Path],
    static_root: pathlib.Path,
    site_prefix: str,
    static_prefix: str,
    skip_external: bool,
) -> None:
    code, message = scan_docs(
        path, docs_root, static_root, site_prefix, static_prefix, skip_external
    )
    click.echo(message)
    sys.exit(code)


def scan_docs(  # noqa: C901, PLR0913
    path: pathlib.Path,
    docs_root: Optional[pathlib.Path],
    static_root: pathlib.Path,
    site_prefix: str,
    static_prefix: str,
    skip_external: bool,
) -> tuple[int, str]:
    if not docs_root:
        docs_root = path
    elif not docs_root.is_dir():
        return 1, f"Docs root path: {docs_root} is not a directory"

    # prepare our return value
    result: List[LinkReport] = list()
    checker = LinkChecker(
        path, docs_root, static_root, site_prefix, static_prefix, skip_external
    )

    if path.is_dir():
        # if the path is a directory, get all .md files within it
        for file in path.rglob("*.md"):
            report = checker.check_file(file)
            if report:
                result.extend(report)
    elif path.is_file():
        # else we support checking one file at a time
        result.extend(checker.check_file(path))
    else:
        return 1, f"Docs path: {path} is not a directory or file"

    if result:
        message: list[str] = []
        message.append("----------------------------------------------")
        message.append("------------- Broken Link Report -------------")
        message.append("----------------------------------------------")
        for line in result:
            message.append(str(line))

        return 1, "\n".join(message)
    else:
        return 0, "No broken links found"


def main():
    scan_docs_click()


if __name__ == "__main__":
    main()
