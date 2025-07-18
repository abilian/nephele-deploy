#!/usr/bin/env python3

"""
This script checks if specific repositories (from the BXL-demo) are present in the Docker registry catalog.
"""

import requests


def my_callback():
    res = requests.get("http://localhost:5000/v2/_catalog")
    json = res.json()
    for repo in ["custom-vo", "image-detection", "noise-reduction"]:
        assert repo in json["repositories"], f"Repository {repo} not found in catalog"
