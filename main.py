#!/usr/bin/env python3

"""
Peltast is a starter script for quickly building static websites.
See the README for full details and instructions.
"""


# Standard libraries
import argparse
from datetime import datetime
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

# Third-party libraries
from jinja2 import Environment, FileSystemLoader
import markdown
from typogrify.filters import typogrify
import yaml

# Local modules
from modules.watchdog import start_watching


# Configurations

# Change directories as needed.
# Note that `expanduser` is necessary for Linux/Docker.
BUILDER_DIRECTORY = Path.cwd()
CONTENT_DIRECTORY = Path.cwd() / "content"
SITE_DIRECTORY = Path.cwd() / "public"


# Functions for gathering content data


def verify_yaml_data(file, file_data):
    for key in ["page"]:
        if not file_data.get(key):
            print(f"Error: {file.name}")
            print(f"Details: YAML has no {key} defined.")
            sys.exit(1)


def json_debug_dump(data):
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)

    def dump_object_to_json(obj, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(obj, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
        print("Created content_data.json for debugging.")

    dump_object_to_json(data, "content_data.json")


def gather_content_data(args):
    content_data = []
    for file in CONTENT_DIRECTORY.glob("**/*.md"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                file_string = f.read()
            yaml_part, markdown_part = file_string.split("---", 2)[1:]
            file_data = yaml.safe_load(yaml_part)
            verify_yaml_data(file, file_data)
            file_data["url"] = file.name.rsplit(".", 1)[0]
            file_data["title"] = typogrify(
                html.unescape(
                    file_data.get("title") or file_data["url"].replace("-", " ").title()
                )
            )
            file_data["html"] = typogrify(markdown.markdown(markdown_part))
            content_data.append(file_data)
        except Exception as e:
            print(f"Error: {file}")
            print(f"Details: {str(e)}.")
            sys.exit(1)
    (
        json_debug_dump(content_data) if args.watch else None
    )  # Useful for testing; triggered along with watchdog
    return content_data


# Functions for building pages


def remove_and_recreate_site_directory():
    shutil.rmtree(SITE_DIRECTORY, ignore_errors=True)
    os.makedirs(SITE_DIRECTORY)


def start_jinja2():
    templates_directory = BUILDER_DIRECTORY / "templates"
    jinja_environment = Environment(loader=FileSystemLoader(templates_directory))
    template = jinja_environment.get_template("base.html")
    return template


def build_pages(content_data):
    remove_and_recreate_site_directory()
    template = start_jinja2()
    for page in content_data:
        output_html = template.render(
            content_template=f"{page['page']}.html",
            page=page,
            posts=content_data,
            now=datetime.now(),  # To automatically update the footer's year
        )
        output_path = SITE_DIRECTORY / f"{page['url']}.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_html)


# Functions: Tailwind CSS


def build_tailwind_css():
    try:
        tailwind_cmd = [
            "npx",
            "tailwindcss",
            "-i",
            "input.css",
            "-o",
            "public/styles.css",
            "--content",
            f"{SITE_DIRECTORY}/**/*.html",
        ]
        subprocess.run(
            tailwind_cmd,
            cwd=BUILDER_DIRECTORY,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error building Tailwind CSS: {e}")
        sys.exit(1)


# Functions: Move assets


def move_assets():
    # Images
    content_images_directory = CONTENT_DIRECTORY / "images"
    site_images_directory = SITE_DIRECTORY / "images"
    os.makedirs(site_images_directory, exist_ok=True)
    for image in content_images_directory.glob("*"):
        shutil.copy(image, site_images_directory)


# Functions: Other


def parse_args():
    parser = argparse.ArgumentParser(description="Peltast")
    parser.add_argument(
        "-w",
        "--watch",
        "--watchdog",
        action="store_true",
        help="Watch for changes and rebuild the site automatically",
    )
    parser.add_argument(
        "--triggered-by-watchdog",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def start_browser_sync():
    try:
        browser_sync_cmd = (
            f"cd {BUILDER_DIRECTORY} && browser-sync start --config bs-config.mjs"
        )
        applescript_cmd = browser_sync_cmd.replace('"', '\\"')
        if sys.platform == "darwin":  # macOS
            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    'tell application "Terminal" to do script "'
                    + applescript_cmd
                    + '"',
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except subprocess.CalledProcessError as e:
        print(f"Error starting BrowserSync: {e}")
        sys.exit(1)


# Main


def main():

    start_time = time.time()

    args = parse_args()

    content_data = gather_content_data(args)

    build_pages(content_data)  # Annihilates the previous site directory.

    build_tailwind_css()  # Must happen after "build" in case Markdown has styles.

    move_assets()  # Everything other than HTML pages.

    print(
        f"Done! Build time: {"{:.0f}".format((time.time() - start_time) * 1000)} ms\n"
    )

    if args.watch and not args.triggered_by_watchdog:
        start_browser_sync()

    if args.watch:
        start_watching(
            BUILDER_DIRECTORY,
            CONTENT_DIRECTORY,
            [sys.argv[0]] + sys.argv[1:] + ["--triggered-by-watchdog"],
        )


if __name__ == "__main__":
    main()
