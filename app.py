import argparse
import logging
from dataclasses import dataclass

import pandas as pd
from playwright.sync_api import sync_playwright, ElementHandle, Page
from playwright._impl._api_types import TimeoutError

PROFESIA_BASE_URL = "https://www.profesia.sk"
PROFESIA_SEARCH_URL = "https://www.profesia.sk/praca/?search_anywhere="

logging.basicConfig(filename="./logs.txt",
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

@dataclass
class Job:
    title: str
    min_salary: int
    max_salary: int
    employer: str
    url: str
    location: str


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="Profesia scraper",
        description="Scrapes profesia for specific keyword and let's you filter entries",
    )
    parser.add_argument(
        "-k",
        "--keywords",
        nargs="+",
        required=True,
        type=str,
        help="Keywords used to search profesia (list)",
    )
    parser.add_argument(
        "-min", "--min_salary", type=int, help="Min monthly salary in Euros"
    )
    parser.add_argument(
        "-max", "--max_salary", type=int, help="Max monthly salary in Euros"
    )
    parser.add_argument(
        "-all",
        "--all",
        nargs="+",
        type=str,
        help="Title must contain all these words",
    )
    parser.add_argument(
        "-any",
        "--any_words",
        nargs="+",
        type=str,
        help="Title must contain at least one of these words",
    )
    parser.add_argument(
        "-none",
        "--none_words",
        nargs="+",
        type=str,
        help="Title must contain none of these words",
    )
    parser.add_argument(
        "-b", "--browser", type=bool, help="Whether browser should be visible"
    )
    parsed_args = parser.parse_args()
    keywords = parsed_args.keywords
    all_words = parsed_args.all or []
    any_words = parsed_args.any_words or []
    bad_words = parsed_args.none_words or []
    min_expected_salary = parsed_args.min_salary or 0
    max_expected_salary = parsed_args.max_salary or 99999999999
    with_browser = parsed_args.browser or False
    print("Starting requesting jobs")
    jobs = _scrape_profesia(keywords, with_browser)
    filtered_jobs, filtered_out_jobs = _filter_jobs(
        jobs, all_words, any_words, bad_words, min_expected_salary, max_expected_salary
    )
    jobs_df = pd.DataFrame(filtered_jobs)
    jobs_df.to_csv("./jobs.csv", index=False)
    print(
        f"Exported {len(filtered_jobs)} jobs into jobs.csv, filtered out: {filtered_out_jobs} jobs"
    )


def _filter_jobs(
        jobs: list[Job],
        all_words: list[str],
        any_words: list[str],
        bad_words: list[str],
        expected_min_salary: int,
        expected_max_salary: int,
) -> tuple[list[Job], int]:
    filtered_jobs: list[Job] = []
    filtered_out = 0
    for job in jobs:
        if (
                _contains_all_filter_words(job.title, all_words)
                and _contains_any_word(job.title, any_words)
                and not _contains_any_word(job.title, bad_words)
                and _filter_by_salary(
            job.min_salary, job.max_salary, expected_min_salary, expected_max_salary
        )
        ):
            filtered_jobs.append(job)
        else:
            filtered_out += 1
    return filtered_jobs, filtered_out


def _format_keywords(keywords: list[str]) -> str:
    result = ""
    for index, keyword in enumerate(keywords):
        is_last = index == len(keywords) - 1
        extender = "" if is_last else "%2C+"
        result += f"{keyword}{extender}"
    return result


def _format_job_url(url_ending: str) -> str:
    return f"{PROFESIA_BASE_URL}{url_ending}"


def _extract_salaries(salary_text: str) -> tuple[int, int]:
    if not salary_text:
        return 0, 0
    bad_words = ["hod", "Kč"]
    if any(
            bad_word in salary_text for bad_word in bad_words
    ):  # TODO add per hour extracting, conversion of czech crowns
        return 0, 0
    to_be_replaced_definitions = {"EUR": "", "/mesiac": "", "Od": "", "Do": "", " ": ""}
    replaced = salary_text
    for to_be_replaced, to_replace_with in to_be_replaced_definitions.items():
        replaced = replaced.replace(to_be_replaced, to_replace_with)

    if "-" not in replaced:
        both = int(replaced)
        return both, both
    else:
        split_ranges = replaced.split("-")
        min_salary = int(split_ranges[0])
        max_salary = int(split_ranges[1])
        return min_salary, max_salary


def _get_text_from_inner_selector(element: ElementHandle, selector: str) -> str:
    try:
        return element.query_selector(selector).text_content()
    except AttributeError:
        logging.warning(f"Could not parse single text field")
        return ""


def _contains_any_word(title: str, any_words: list[str]) -> bool:
    title_lowercase = title.lower()
    return any(single_word.lower() in title_lowercase for single_word in any_words)


def _contains_all_filter_words(title: str, filters: list[str]) -> bool:
    title_lowercase = title.lower()
    return all(single_filter.lower() in title_lowercase for single_filter in filters)


def _filter_by_salary(
        min_salary: int, max_salary: int, expected_min_salary: int, expected_max_salary: int
) -> bool:
    return min_salary >= expected_min_salary and max_salary <= expected_max_salary


def _scrape_profesia(keywords: list[str], with_browser: bool) -> list[Job]:
    formatted_keywords = _format_keywords(keywords)
    query_url = f"{PROFESIA_SEARCH_URL}{formatted_keywords}"
    jobs: list[Job] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not with_browser)
        page = browser.new_page()
        page.goto(query_url)
        cookies = page.query_selector("text=Povoliť Všetko")
        if cookies:
            cookies.click(timeout=5000)
        while True:
            try:
                jobs.extend(_scrape_single_page(page))
                page.click("a.next", timeout=10000)
            except AttributeError as e:
                logging.error(f"Attribute error :{e}")
                if "click" in str(e):
                    break
            except TimeoutError:
                break
            except Exception as f:
                logging.error(f"Error while scraping {f}")
                break
        browser.close()
    return jobs


def _parse_single_job(job_listing: ElementHandle) -> Job:
    title_component = job_listing.query_selector("h2 > a")
    title = title_component.text_content()
    url_ending = title_component.get_attribute("href")
    url = _format_job_url(url_ending)
    employer = _get_text_from_inner_selector(job_listing, "span.employer")
    location = _get_text_from_inner_selector(job_listing, "span.job-location")
    salary = _get_text_from_inner_selector(job_listing, "span.green").strip()
    min_salary, max_salary = _extract_salaries(salary)
    return Job(
        title=title,
        min_salary=min_salary,
        max_salary=max_salary,
        employer=employer,
        url=url,
        location=location,
    )


def _scrape_single_page(page: Page) -> list[Job]:
    page_jobs: list[Job] = []
    loc = page.query_selector_all("li.list-row")
    for job_listing in loc:
        try:
            job = _parse_single_job(job_listing)
            if job:
                page_jobs.append(job)
        except Exception as e:
            logging.error(f"Error scraping single job {e}")
    return page_jobs


if __name__ == "__main__":
    main()
