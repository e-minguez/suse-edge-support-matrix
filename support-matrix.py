#!/usr/bin/env python3
import re, json
import requests
from bs4 import BeautifulSoup


def get_release_sections(url):
    """
    Gets all sections with IDs matching the patterns:
        'id-release-X-Y-Z' or 'release-notes-X-Y-Z'
    """
    try:
        response = requests.get(url,timeout=30)
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
    result = {}
    for item in data:
        if "Name" in item:
            name = item["Name"]
            result[name] = item
    return result


def get_release_data(url):
    release_sections = get_release_sections(url)
    if release_sections:
        releases_data = []
        for section in release_sections:
            # Release version is there as "Release X.Y.Z"
            release = section["data-id-title"].split()[1]
            components = get_components_versions_subsection(section)
            if components:
                # Release URL can be crafted
                release_url = f"{url}#{components['id']}"
                tables = get_components_versions_tables_from_section(components)
                if tables:
                    for table in tables:
                        data = extract_data_from_table(table)
                else:
                    print(
                        f"No matching tables found in section {section['data-id-title']}"
                    )
            releases_data.append({"Version": release, "URL": release_url, "Data": data})
        return releases_data
    else:
        print("No release sections found.")


def get_urls(docsurl):
    try:
        urls = []
        response = requests.get(docsurl,timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        edge_docs = soup.find("div", attrs={"data-product-family": "SUSE Edge"})
        edge_docs_urls = json.loads(edge_docs["data-supported-versions"])
        for i in edge_docs_urls:
            urls.append(
                f"https://documentation.suse.com/suse-edge/{i['name']}/html/edge/id-release-notes.html"
            )
        return urls

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == "__main__":

    urls = get_urls("https://documentation.suse.com/en-us/?tab=products")
    for url in urls:
        releases_data = get_release_data(url)
        for release_data in releases_data:
            print(release_data["Version"])
            print(release_data["URL"])
            data = get_dicts_by_name(release_data["Data"])
            print(data)
