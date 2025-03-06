#!/usr/bin/env python3
import re, json, datetime
import requests
from bs4 import BeautifulSoup
from jinja2 import Template


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
            continue #skip non dict items
        if "Name" in item:
            name = item["Name"]
            result[name] = item
            result[name].pop("Name")
        else:
            print("Item missing 'Name' key: %s", item)
    return result


def get_release_data(url):
    """ Retrieves release data from a given URL. """
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

                if not components_section:
                    print(f"No components section found for {release_title} in {url}")
                    continue

                release_url = f"{url}#{components_section['id']}"

                tables = get_components_versions_tables_from_section(components_section)

                if not tables:
                    print(f"No matching tables found in section {release_title} in {url}")
                    releases_data.append({"Version": release_version, "URL": release_url, "Data": []}) #append empty data
                    continue

                all_table_data = [] #create a list to store data from all tables
                for table in tables:
                    table_data = extract_data_from_table(table)
                    if table_data:
                        all_table_data.extend(table_data)

                releases_data.append({"Version": release_version, "URL": release_url, "Data": all_table_data})

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
                        processed_data = get_dicts_by_name(release["Data"])
                        if processed_data:
                            all_releases.append({
                                "Version": version,
                                "URL": url,
                                "Data": processed_data,
                            })

            except Exception as e:
                print(f"Error processing URL {product_url}: {e}")

    return all_releases

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
        with open(template_file, 'r', encoding='utf-8') as file:
            template_content = file.read()

        template = Template(template_content)
        generation_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        rendered_html = template.render(data=data,generation_time=generation_time)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(rendered_html)

        return output_file

    except IOError as e:
        print(f"Error generating HTML: {e}")
        return ""
    except Exception as e:
        print(f"An unexpected error occurred during HTML generation: {e}")
        return ""

def save_json(data):
    """ Saves a json file per release with the actual content """
    for release in data:
        try:
            with open(f"{release['Version']}.json", 'w', encoding='utf-8') as f:
                json.dump(release, f, indent=2)
        except IOError as e:
            print(f"Error saving JSON file: {e}")

if __name__ == "__main__":
    data=get_all_releases_data()
    save_json(data)
    generate_html('template.html.j2','index.html',data)