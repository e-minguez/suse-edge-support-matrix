# SUSE Edge Support Matrix

This repository contains a script that generates an HTML page displaying the support matrix for SUSE Edge. The support matrix shows the versions of various components (like SLE Micro, SUSE Manager, Rancher, K3s/RKE2, etc.) supported in each SUSE Edge release.

## How it works

1. The script scrapes the SUSE Edge documentation pages to extract information about supported components and their versions.
2. It then generates an HTML page using Jinja2 templates, displaying the data in an organized table format.
3. A GitHub Actions workflow runs the script hourly to keep the support matrix up-to-date.

As a bonus, there is a GitHub Actions workflow that builds the container as well just in case it needs to be executed manually.

## Viewing the support matrix

The generated support matrix is available here: https://eduardominguez.es/suse-edge-support-matrix/

## Contributions

Contributions to enhance the functionality or accuracy of this project are welcome. Users are encouraged to submit issues or pull requests via the GitHub repository.

## License

This project is distributed under the terms of the MIT License.