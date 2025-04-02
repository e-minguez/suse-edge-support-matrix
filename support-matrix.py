#!/usr/bin/env python3
import re
import json
import datetime
import requests
from bs4 import BeautifulSoup
from lxml import etree
from lxml.builder import ElementMaker
from jinja2 import Template


def get_release_sections(url):
    """
    Gets all sections with IDs matching the patterns:
        'id-release-X-Y-Z' or 'release-notes-X-Y-Z'
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        release_sections = soup.find_all(
            "section", id=re.compile(r"(id-)?release(-notes)?-\d+-\d+-\d+")
        )
        return release_sections

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_components_versions_subsection(release_section):
    """
    Gets the "Components Versions" section from the release section
    """
    try:
        components = release_section.find(
            "section", attrs={"data-id-title": "Components Versions"}
        )
        return components
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_availability_date(release_section):
    """
    Gets the "availability date" from the release section
    """
    date_pattern = r"\d{1,2}(?:st|nd|rd|th) [A-Za-z]+ \d{4}"
    try:
        date_text_search = release_section.find(
            string=re.compile(r"Availability Date:")
        )
        if date_text_search:
            date_match = re.findall(date_pattern, date_text_search)
            if date_match:
                return date_match[0]
        return None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_components_versions_tables_from_section(section):
    """
    Gets tables from a given section.
    """
    try:
        tables = section.find_all("table", attrs={"class" == "informaltable"})
        return tables

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def extract_data_from_table(table):
    """
    Extracts data from a table and constructs a JSON-like structure.
    Skips cells with "N/A" or empty values.
    """
    data = []
    header = []
    rows = table.find_all("tr")
    first_row = True  # Flag to identify the header row
    for row in rows:
        cells = row.find_all(["td", "th"])
        if first_row:
            header = [cell.text.strip() for cell in cells]
            first_row = False
        else:
            row_data = {}
            for i, cell in enumerate(cells):
                if i < len(header):  # Make sure we don't go out of bounds
                    value = cell.text.strip()
                    # Skip empty cells and "N/A" cells
                    if value and value != "N/A":
                        row_data[header[i]] = value
                    # For artifact location, get the raw content
                    if header[i] == "Artifact Location (URL/Image)":
                        # Actually, get the content removing the <td>
                        row_data[header[i]] = "".join([str(c) for c in cell.contents])
            if row_data:
                data.append(row_data)
    return data


def get_dicts_by_name(data):
    """
    Creates a dictionary where keys are "Name" values from a list of dictionaries.

    Args:
        data: A list of dictionaries, where each dictionary should have a "Name" key.

    Returns:
        A dictionary where keys are "Name" values and values are the corresponding dictionaries.
    """
    if not isinstance(data, list):
        raise TypeError("Input data must be a list.")

    result: Dict[str, Dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue  # skip non dict items
        if "Name" in item:
            name = item["Name"]
            result[name] = item
            result[name].pop("Name")
        else:
            print("Item missing 'Name' key: %s", item)
    return result


def get_release_data(url):
    """Retrieves release data from a given URL."""
    try:
        release_sections = get_release_sections(url)

        if not release_sections:
            print(f"No release sections found for {url}")
            return None

        releases_data = []
        for section in release_sections:
            try:
                release_title = section.get("data-id-title")
                if not release_title:
                    print(f"data-id-title not found in section for {url}")
                    continue

                parts = release_title.split()
                if len(parts) < 2:
                    print(f"Invalid release title format: {release_title} in {url}")
                    continue
                release_version = parts[1]

                components_section = get_components_versions_subsection(section)

                availability_date = get_availability_date(section)

                if not components_section:
                    print(f"No components section found for {release_title} in {url}")
                    continue

                release_url = f"{url}#{components_section['id']}"

                tables = get_components_versions_tables_from_section(components_section)

                if not tables:
                    print(
                        f"No matching tables found in section {release_title} in {url}"
                    )
                    releases_data.append(
                        {"Version": release_version, "URL": release_url, "Data": []}
                    )  # append empty data
                    continue

                all_table_data = []  # create a list to store data from all tables
                for table in tables:
                    table_data = extract_data_from_table(table)
                    if table_data:
                        all_table_data.extend(table_data)

                releases_data.append(
                    {
                        "Version": release_version,
                        "URL": release_url,
                        "AvailabilityDate": availability_date,
                        "Data": all_table_data,
                    }
                )

            except Exception as inner_e:
                print(f"Error processing release section in {url}: {inner_e}")
                continue

        return releases_data

    except Exception as outer_e:
        print(f"Error retrieving release data from {url}: {outer_e}")
        return None


def get_urls(docsurl):
    """Retrieves URLs of the SUSE Edge docs from SUSE documentation pages."""
    try:
        response = requests.get(docsurl, timeout=30)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        soup = BeautifulSoup(response.content, "html.parser")
        edge_docs = soup.find("div", attrs={"data-product-family": "SUSE Edge"})

        if not edge_docs:
            print(f"SUSE Edge data not found on {docsurl}")
            return None

        supported_versions_json = edge_docs.get("data-supported-versions")

        if not supported_versions_json:
            print(f"data-supported-versions not found on {docsurl}")
            return None

        try:
            supported_versions = json.loads(supported_versions_json)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {docsurl}: {e}")
            return None

        urls = [
            f"https://documentation.suse.com/suse-edge/{version['name']}/html/edge/id-release-notes.html"
            for version in supported_versions
        ]
        return urls

    except Exception as e:
        print(f"An unexpected error occurred fetching {docsurl}: {e}")
        return None


def get_all_releases_data():
    """Retrieves and processes release data from SUSE documentation pages."""

    all_releases = []
    product_urls = get_urls("https://documentation.suse.com/en-us/?tab=products")

    if product_urls:
        for product_url in product_urls:
            try:
                releases = get_release_data(product_url)
                if releases:
                    for release in releases:
                        version = release["Version"]
                        url = release["URL"]
                        availability_date = release["AvailabilityDate"]
                        processed_data = get_dicts_by_name(release["Data"])
                        if processed_data:
                            all_releases.append(
                                {
                                    "Version": version,
                                    "URL": url,
                                    "AvailabilityDate": availability_date,
                                    "Data": processed_data,
                                }
                            )

            except Exception as e:
                print(f"Error processing URL {product_url}: {e}")

    return all_releases


def convert_date_format(date_string):
    """
    Converts a date string in "DDth Month YYYY" format to "YYYY-MM-DD" format.

    Args:
        date_string (str): The date string to convert.

    Returns:
        str: The converted date string, or None if the conversion fails.
    """
    try:
        clean_string = re.sub(r"(\d)(st|nd|rd|th)", r"\1", date_string)
        date_object = datetime.datetime.strptime(clean_string, "%d %B %Y")
        return date_object.strftime("%Y-%m-%d")
    except ValueError:
        return None


def create_xml_with_elementmaker(data):
    """Creates the main XML structure."""

    E = ElementMaker(
        namespace="http://docbook.org/ns/docbook",
        nsmap={
            None: "http://docbook.org/ns/docbook",
            "its": "http://www.w3.org/2005/11/its",
            "xi": "http://www.w3.org/2001/XInclude",
            "xlink": "http://www.w3.org/1999/xlink",
            "xml": "http://www.w3.org/XML/1998/namespace",
        },
    )

    ARTICLE = E.article
    TITLE = E.title
    INFO = E.info
    DATE = E.date
    ABSTRACT = E.abstract
    PARA = E.para
    LINK = E.link
    META = E.meta
    NAME = E.name
    VALUE = E.value
    PHRASE = E.phrase
    REVHISTORY = E.revhistory
    REVISION = E.revision
    REVDESCRIPTION = E.revdescription

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

    revhistory_element = REVHISTORY(
        **{"{http://www.w3.org/XML/1998/namespace}id": "rh-edge-support-matrix"}
    )
    for release in data:
        date = convert_date_format(release["AvailabilityDate"])
        description = f"Added SUSE Edge {release["Version"]}"
        revhistory_element.append(
            REVISION(DATE(date), REVDESCRIPTION(PARA(description)))
        )

    root = ARTICLE(
        TITLE("SUSE Edge support matrix"),
        INFO(
            DATE(now),
            ABSTRACT(
                PARA(
                    "The following tables describe the individual components that make up the SUSE Edge releases, including the version, the Helm chart version (if applicable), and from where the released artifact can be pulled in the binary format. this information is also provided for processing in JSON format."
                ),
                PARA(
                    LINK(
                        "https://documentation.suse.com/suse-edge/",
                        **{
                            "{http://www.w3.org/1999/xlink}href": "https://documentation.suse.com/suse-edge/"
                        },
                    )
                ),
            ),
            META(
                "SUSE Edge support matrix",
                name="title",
                **{"{http://www.w3.org/2005/11/its}translate": "yes"},
            ),
            META(
                "Products & Solutions",
                name="series",
                **{"{http://www.w3.org/2005/11/its}translate": "no"},
            ),
            META(
                "A complete list of components for all SUSE Edge releases",
                name="description",
                **{"{http://www.w3.org/2005/11/its}translate": "yes"},
            ),
            META(
                "List of components for all SUSE Edge releases",
                name="social-descr",
                **{"{http://www.w3.org/2005/11/its}translate": "yes"},
            ),
            META(
                PHRASE("Implementation"),
                name="task",
                **{"{http://www.w3.org/2005/11/its}translate": "no"},
            ),
        ),
        version="5.2",
        **{
            "{http://www.w3.org/XML/1998/namespace}id": "article-installation",
            "{http://www.w3.org/XML/1998/namespace}lang": "en",
        },
    )
    return root


def create_sect1_xml(data):
    """
    Creates a <sect1> XML structure from the provided data.

    Args:
        data (dict): The data dictionary containing version information.

    Returns:
        lxml.etree._Element: The <sect1> element.
    """

    E = ElementMaker(
        namespace="http://docbook.org/ns/docbook",
        nsmap={
            None: "http://docbook.org/ns/docbook",
            "xlink": "http://www.w3.org/1999/xlink",
            "xml": "http://www.w3.org/XML/1998/namespace",
        },
    )

    SECT1 = E.sect1
    TITLE = E.title
    PARA = E.para
    LINK = E.link
    INFORMALTABLE = E.informaltable
    TGROUP = E.tgroup
    COLSPEC = E.colspec
    THEAD = E.thead
    ROW = E.row
    ENTRY = E.entry
    TBODY = E.tbody

    title = f"Release {data["Version"]}"
    # Extract version and remove dots for xml:id
    version = data.get("Version", "Unknown")
    sect1_id = "edge-" + version.replace(".", "")
    json_link = "TBD"

    root = SECT1(
        TITLE(f"Release {version}"),
        PARA(
            LINK(
                "Download as JSON",
                **{"{http://www.w3.org/1999/xlink}href": data.get("URL", "#")},
            )
        ),
        INFORMALTABLE(
            TGROUP(
                COLSPEC(colnum="1", colname="1", colwidth="20*"),
                COLSPEC(colnum="2", colname="2", colwidth="15*"),
                COLSPEC(colnum="3", colname="3", colwidth="15*"),
                COLSPEC(colnum="4", colname="4", colwidth="50*"),
                THEAD(
                    ROW(
                        ENTRY(PARA("Name")),
                        ENTRY(PARA("Version")),
                        ENTRY(PARA("Helm Chart Version")),
                        ENTRY(PARA("Artifact Location (URL/Image)")),
                    )
                ),
                TBODY(
                    *[
                        create_row_from_component(E, component_name, component_data)
                        for component_name, component_data in data.get(
                            "Data", {}
                        ).items()
                    ]
                ),
                cols="4",
            )
        ),
        **{"{http://www.w3.org/XML/1998/namespace}id": sect1_id},
    )

    return root


def create_row_from_component(E, component_name, component_data):
    """
    Creates a <tbody> <row> element for a component.

    Args:
        E (ElementMaker): The ElementMaker instance.
        component_name (str): The name of the component.
        component_data (dict): The component's data.

    Returns:
        lxml.etree._Element: The <tbody> <row> element.
    """

    ROW = E.row
    ENTRY = E.entry
    PARA = E.para

    name = component_name
    version = component_data.get("Version", "N/A")
    helm_chart_version = component_data.get("Helm Chart Version", "N/A")
    artifact_location = component_data.get("Artifact Location (URL/Image)", "")

    # Handle Artifact Location (URL/Image) - Parse HTML-like strings
    artifact_elements = []
    if artifact_location:
        # Simple HTML-like tag parsing (very basic, adjust if needed)
        for part in re.split(r"(<[^>]+>)", artifact_location):
            if part.startswith("<a"):
                match = re.search(r'href="([^"]+)"', part)
                if match:
                    href = match.group(1)
                    text = re.sub(r"<[^>]+>", "", part)  # Remove tags
                    artifact_elements.append(
                        PARA(
                            E.link(text, **{"{http://www.w3.org/1999/xlink}href": href})
                        )
                    )
            elif part and not part.startswith("<"):
                for subpart in part.split("<br/>"):
                    artifact_elements.append(PARA(subpart))

    return ROW(
        ENTRY(PARA(name)),
        ENTRY(PARA(version)),
        ENTRY(PARA(helm_chart_version)),
        ENTRY(*artifact_elements),
    )


def save_json(data):
    """Saves a json file per release with the actual content"""
    for release in data:
        try:
            with open(f"{release['Version']}.json", "w", encoding="utf-8") as f:
                json.dump(release, f, indent=2)
        except IOError as e:
            print(f"Error saving JSON file: {e}")


def save_xml(data):
    root = create_xml_with_elementmaker(data)
    for release in data:
        # Generate and inject sect1 sections
        root.append(create_sect1_xml(release))

    # Convert the XML tree to a string
    declaration = '<?xml version="1.0" encoding="utf-8"?>\n'
    stylesheet_pi = '<?xml-stylesheet href="urn:x-suse:xslt:profiling:docbook50-profile.xsl" type="text/xml" title="Profiling step"?>\n'
    doctype = "<!DOCTYPE article>\n"
    xml_string = etree.tostring(root, encoding="utf-8", pretty_print=True).decode(
        "utf-8"
    )

    output_file = "output.xml"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(declaration + stylesheet_pi + doctype + xml_string)
    except IOError as e:
        print(f"Error writing to {output_file}: {e}")
    except Exception as e:
        print(f"An unexpected error occured: {e}")


def generate_html(template_file, output_file, data):
    """
    Generates HTML from a Jinja template and data.

    Args:
        template_file: Path to the Jinja template file.
        output_file: Path to the output HTML file.
        data: Dictionary containing data to render the template.

    Returns:
        The path of the generated HTML file, or an empty string on error.
    """
    try:
        with open(template_file, "r", encoding="utf-8") as file:
            template_content = file.read()

        template = Template(template_content)
        generation_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        rendered_html = template.render(data=data, generation_time=generation_time)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        return output_file

    except IOError as e:
        print(f"Error generating HTML: {e}")
        return ""
    except Exception as e:
        print(f"An unexpected error occurred during HTML generation: {e}")
        return ""


if __name__ == "__main__":
    data = get_all_releases_data()
    save_json(data)
    save_xml(data)
    generate_html("template.html.j2", "index.html", data)
