# Copyright 2016 Philip Hansen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import re
import requests
from lxml import html
from . import lesson


USER_TYPE = {"student": "elev", "teacher": "laerer"}
LESSON_STATUS = {None: "normal", "Ændret!": "changed", "Aflyst!": "cancelled"}
URL_TEMPLATE = "https://www.lectio.dk/lectio/{0}/SkemaNy.aspx?type={1}&{1}id={2}&week={3}"
LOGIN_URL_TEMPLATE = "https://www.lectio.dk/lectio/{0}/login.aspx"
SPACER = " " + u"\u2022" + " "
cookies = None


class UserDoesNotExistError(Exception):
    """ Attempted to get a non-existing user from Lectio. """


class CookiesNotSet(Exception):
    """ Cookies not set. Login before you retrieve calendar pages. """


class IdNotFoundInLinkError(Exception):
    """ All lessons with a link should include an ID. """


class InvalidStatusError(Exception):
    """ Lesson status can only take the values Ændret!, Aflyst! and None. """


class InvalidTimeLineError(Exception):
    """ The line doesn't include any valid formatting of time. """


class InvalidLocationError(Exception):
    """ The line doesn't include any location. """


class InvalidRessourcesError(Exception):
    """ The line doesn't include any ressources. """


class InvalidGroupsError(Exception):
    """ The line doesn't include any groups. """


def _login(school_id, login, password):
    # Start requests session
    session = requests.Session()

    login_url = LOGIN_URL_TEMPLATE.format(school_id)

    # Get eventvalidation key
    result = session.get(login_url)
    tree = html.fromstring(result.text)
    authenticity_token = list(
        set(tree.xpath("//input[@name='__EVENTVALIDATION']/@value")))[0]

    # Create payload
    payload = {
        "m$Content$username": login,
        "m$Content$password": password,
        "m$Content$passwordHidden": password,
        "__EVENTVALIDATION": authenticity_token,
        "__EVENTTARGET": "m$Content$submitbtn2",
        "__EVENTARGUMENT": "",
        "LectioPostbackId": ""
    }

    # Perform login
    result = session.post(login_url, data=payload,
                          headers=dict(referer=login_url))

    return session.cookies


def _get_user_page(school_id, user_type, user_id, week=""):
    global cookies

    # Start requests session
    session = requests.Session()

    # Get cookie
    if cookies == None:
        raise CookiesNotSet()
    session.cookies.update(cookies)

    # Scrape url
    url = URL_TEMPLATE.format(school_id, USER_TYPE[user_type], user_id, week)
    response = session.get(url, allow_redirects=False)

    return response


def _get_lectio_weekformat_with_offset(offset):
    today = datetime.date.today()
    future_date = today + datetime.timedelta(weeks=offset)
    week_number = "{0:02d}".format(future_date.isocalendar()[1])
    year_number = str(future_date.isocalendar()[0])
    lectio_week = week_number + year_number
    return lectio_week


def _get_id_from_link(link):
    match = re.search(
        r"(?:absid|ProeveholdId|outboundCensorID|aftaleid)=(\d+)", link)
    if match is None:
        return None
    return match.group(1)


def _get_complete_link(link):
    return "https://www.lectio.dk" + link.split("&prevurl=", 1)[0]


def _is_status_line(line):
    match = re.search(r"Ændret!|Aflyst!", line)
    return match is not None


def _get_status_from_line(line):
    try:
        return LESSON_STATUS[line]
    except KeyError:
        raise InvalidStatusError("Line: '{}' has no valid status".format(line))


def _is_location_line(line):
    match = re.search(r"Lokaler?: ", line)
    return match is not None


def _get_location_from_line(line):
    match = re.search(r"Lokaler?: (.*)", line)
    if match is None:
        raise InvalidLocationError("No location found in line: '{}'"
                                   .format(line))
    return match.group(1)


def _is_groups_line(line):
    return line.startswith("Hold: ")


def _get_groups_from_line(line):
    match = re.search(r"Hold: (.*)", line)
    if match is None:
        raise InvalidGroupsError("No groups found in line: '{}'"
                                 .format(line))
    return match.group(1)


def _is_ressources_line(line):
    return line.startswith("Ressourcer: ")


def _get_ressources_from_line(line):
    match = re.search(r"Ressourcer: (.*)", line)
    if match is None:
        raise InvalidRessourcesError("No ressources found in line: '{}'"
                                     .format(line))
    return match.group(1)


def _is_time_line(line):
    # Search for one of the following formats:
    # 14/3-2016 Hele dagen
    # 14/3-2016 15:20 til 16:50
    # 8/4-2016 17:30 til 9/4-2016 01:00
    # 7/12-2015 10:00 til 11:30
    # 17/12-2015 10:00 til 11:30
    match = re.search(r"\d{1,2}/\d{1,2}-\d{4} (?:Hele dagen|\d{2}:\d{2} til "
                      r"(?:\d{1,2}/\d{1,2}-\d{4} )?\d{2}:\d{2})", line)
    return match is not None


def _get_date_from_match(match):
    if match:
        return datetime.datetime.strptime(match, "%d/%m-%Y").date()
    else:
        return None


def _get_time_from_match(match):
    if match:
        return datetime.datetime.strptime(match, "%H:%M").time()
    else:
        return None


def _get_time_from_line(line):
    # Extract the following information in capture groups:
    # 1 - start date
    # 2 - start time
    # 3 - end date
    # 4 - end time
    match = re.search(r"(\d{1,2}/\d{1,2}-\d{4})(?: (\d{2}:\d{2}) til "
                      r"(\d{1,2}/\d{1,2}-\d{4})? ?(\d{2}:\d{2}))?", line)
    if match is None:
        raise InvalidTimeLineError("No time found in line: '{}'".format(line))

    start_date = _get_date_from_match(match.group(1))
    start_time = _get_time_from_match(match.group(2))

    is_top = False
    if start_time:
        start = datetime.datetime.combine(start_date, start_time)
    else:
        start = start_date
        is_top = True

    end_date = _get_date_from_match(match.group(3))
    end_time = _get_time_from_match(match.group(4))

    if not end_date:
        end_date = start_date

    if end_time:
        end = datetime.datetime.combine(end_date, end_time)
    else:
        end = end_date

    return start, end, is_top


def _add_line_to_text(line, text):
    if text != "":
        text += "\n"
    text += line
    return text


def _append_section_to_summary(section, summary):
    spacer = SPACER if summary else ""
    summary += spacer + section
    return summary


def _prepend_section_to_summary(section, summary):
    spacer = SPACER if summary else ""
    summary = section + spacer + summary
    return summary


def _extract_lesson_info(title):
    summary = description = event_title = groups = ressources = ""
    status = start_time = end_time = location = None
    lines = title.splitlines()
    header_section = True
    is_top = False
    offset = 0

    # Find status and event title (if present) and offset
    if len(lines) >= 2:
        line = lines[0]
        if _is_status_line(line):
            status = _get_status_from_line(line)
            line = lines[1]
            offset += 1
        if not _is_time_line(line):
            event_title = line
            offset += 1

    # Get info from all lines
    for line in lines[offset:]:
        if header_section:
            if line == '':
                header_section = False
                continue
            elif _is_time_line(line):
                start_time, end_time, is_top = _get_time_from_line(line)
            elif _is_location_line(line):
                location = _get_location_from_line(line)
            elif _is_groups_line(line):
                groups = _get_groups_from_line(line)
            elif _is_ressources_line(line):
                ressources = _get_ressources_from_line(line)
            else:
                summary = _append_section_to_summary(line, summary)
        else:
            description = _add_line_to_text(line, description)

    # Remove extra text in the summary
    summary = summary.replace("Lærere: ", "")
    summary = re.sub(r"Lærer: [^(]*\(([^)]*)\)", r"\1", summary)

    # Construct summary and description
    if ressources:
        description = "Ressoucer: " + ressources + "\n\n" + description
    if location:
        summary = _append_section_to_summary(location, summary)
    if groups:
        summary = _prepend_section_to_summary(groups, summary)
        if groups.find("Alle") == -1:
            description = event_title + "\n\n" + description
        else:
            summary = _prepend_section_to_summary(event_title, summary)
    else:
        summary = _prepend_section_to_summary(event_title, summary)

    if description == "":  # needed for comparison
        description = None

    return summary, status, start_time, end_time, location, description, is_top


def _parse_element_to_lesson(element, show_top, show_cancelled):
    link = element.get("href")
    id = None
    if link:
        id = _get_id_from_link(link)
        link = _get_complete_link(link)
    info = element.get("data-additionalinfo")
    summary, status, start_time, end_time, location, description, is_top = \
        _extract_lesson_info(info)

    if not show_top and is_top:
        return None
    elif not show_cancelled and status == "cancelled":
        return None
    else:
        return lesson.Lesson(id, summary, status, start_time, end_time, location, description, link)


def _parse_page_to_lessons(page, show_top, show_cancelled):
    tree = html.fromstring(page)
    # Find all a elements with class s2skemabrik in page
    lesson_elements = tree.xpath("//a[contains(concat("
                                 "' ', normalize-space(@class), ' '),"
                                 "' s2skemabrik ')]")
    lessons = []
    for element in lesson_elements:
        lesson = _parse_element_to_lesson(element, show_top, show_cancelled)
        if lesson is not None:
            lessons.append(lesson)
    return lessons


def _retreive_week_schedule(school_id, user_type, user_id, week, show_top, show_cancelled):
    r = _get_user_page(school_id, user_type, user_id, week=week)
    schedule = _parse_page_to_lessons(r.content, show_top, show_cancelled)
    return schedule


def _filter_for_duplicates(schedule):
    filtered_schedule = []
    for lesson in schedule:
        if lesson not in filtered_schedule:
            filtered_schedule.append(lesson)
    return filtered_schedule


def _retreive_user_schedule(school_id, user_type, user_id, n_weeks, show_top, show_cancelled):
    schedule = []
    for week_offset in range(n_weeks + 1):
        week = _get_lectio_weekformat_with_offset(week_offset)
        week_schedule = _retreive_week_schedule(
            school_id, user_type, user_id, week, show_top, show_cancelled)
        schedule += week_schedule
    filtered_schedule = _filter_for_duplicates(schedule)
    return filtered_schedule


def _user_exists(school_id, user_type, user_id, login, password):
    global cookies

    # Login and save cookie
    cookies = _login(school_id, login, password)

    # Open page
    r = _get_user_page(school_id, user_type, user_id)

    return r.status_code == requests.codes.ok


def get_schedule(school_id, user_type, user_id, n_weeks, show_top, show_cancelled, login, password):
    if not _user_exists(school_id, user_type, user_id, login, password):
        raise UserDoesNotExistError("Couldn't find user - school: {}, "
                                    "type: {}, id: {}, login: {} - in Lectio.".format(
                                        school_id, user_type, user_id, login))
    return _retreive_user_schedule(school_id, user_type, user_id, n_weeks, show_top, show_cancelled)
