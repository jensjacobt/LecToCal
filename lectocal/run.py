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

import argparse
import getpass
import sys
from . import gauth
from . import lectio
from . import lesson
from . import gcalendar


def _get_arguments():
    parser = argparse.ArgumentParser(description="Scrapes a Lectio schedule "
                                     "and syncs it to Google Calendar.")
    parser.add_argument("school_id",
                        type=int,
                        help="ID of the school user belongs to in Lectio.")
    parser.add_argument("user_type",
                        choices=["student", "teacher"],
                        help="User type in Lectio. "
                        "(options: student, teacher)")
    parser.add_argument("user_id",
                        type=int,
                        help="User's ID in Lectio.")
    parser.add_argument("--credentials",
                        default="storage.json",
                        help="Path to the file storing the Google "
                        "OAuth credentials. (default: storage.json)")
    parser.add_argument("--calendar",
                        default="Lectio",
                        help="Name to use for the calendar inside "
                        "Google Calendar. (default: Lectio)")
    parser.add_argument("--login",
                        default="",
                        type=str,
                        help="The username from a Lectio login.")
    parser.add_argument("--weeks",
                        type=int,
                        default=4,
                        help="Number of weeks to parse the schedule for. "
                        "(default: 4)")
    parser.add_argument('--showtop',
                        default=False,
                        dest='show_top',
                        action='store_true',
                        help="If set, sync events from the Lectio's header to Google Calendar.")
    parser.add_argument('--showcancelled',
                        default=False,
                        dest='show_cancelled',
                        action='store_true',
                        help="If set, sync cancelled events to Google Calendar.")

    return parser.parse_args()


def main():
    arguments = _get_arguments()

    try:
        if(arguments.login):
            login = arguments.login
        else:
            login = input("Lectio username: ")
        password = getpass.getpass(prompt="Lectio password: ")
    except:
        print("\nLogin cancelled")
        sys.exit()

    google_credentials = gauth.get_credentials(arguments.credentials)
    if not gcalendar.has_calendar(google_credentials, arguments.calendar):
        gcalendar.create_calendar(google_credentials, arguments.calendar)

    lectio_schedule = lectio.get_schedule(arguments.school_id,
                                          arguments.user_type,
                                          arguments.user_id,
                                          arguments.weeks,
                                          arguments.show_top,
                                          arguments.show_cancelled,
                                          login,
                                          password)

    google_schedule = gcalendar.get_schedule(google_credentials,
                                             arguments.calendar,
                                             arguments.weeks)

    if not lesson.schedules_are_identical(lectio_schedule, google_schedule):
        gcalendar.update_calendar_with_schedule(google_credentials,
                                                arguments.calendar,
                                                google_schedule,
                                                lectio_schedule)


if __name__ == "__main__":
    main()
