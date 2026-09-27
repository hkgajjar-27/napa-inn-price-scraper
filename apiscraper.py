import requests
import re
import json
from datetime import date, timedelta


# =========================================================
# API CONFIGURATION
# =========================================================

BASE_URL = (
    "https://secure.thinkreservations.com/"
    "napainn/reservations/availability"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Rsc": "1",
    "Next-Url": "/legacy/napainn/reservations/availability",
}


# =========================================================
# API REQUEST
# =========================================================

def get_api_response(check_in, check_out, adults):
    """
    Request availability/pricing data directly from the
    ThinkReservations availability data endpoint.

    Parameters
    ----------
    check_in : str
        Format: YYYY-MM-DD

    check_out : str
        Format: YYYY-MM-DD

    adults : int
        Number of adults
    """

    params = {
        "startDate": check_in,
        "endDate": check_out,
        "numberOfAdults": adults,
    }

    response = requests.get(
        BASE_URL,
        params=params,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    return response.text


# =========================================================
# NORMALIZE RSC RESPONSE
# =========================================================

def normalize_response(response_text):
    """
    The endpoint returns a Next.js/RSC response rather than
    plain JSON.

    Convert escaped JSON quotes into normal quotes so that
    regex-based extraction is easier.
    """

    text = response_text

    text = text.replace('\\"', '"')

    return text


# =========================================================
# EXTRACT 90-DAY CALENDAR AVAILABILITY
# =========================================================

def extract_calendar_rows(response_text):
    """
    Extract calendarRows from the RSC response.

    The response contains data similar to:

        calendarRows: [
            {
                name: "1 - Oak Room",
                dailyAvailabilities: [
                    {
                        date: "2026-10-05",
                        isAvailable: true
                    }
                ]
            }
        ]

    Returns:

        [
            {
                "room_name": "...",
                "daily_availability": {
                    "2026-10-05": True,
                    "2026-10-06": False
                }
            }
        ]
    """

    text = normalize_response(response_text)

    rooms = []

    room_pattern = re.compile(
        r'"name":"([^"]+)"'
        r'.{0,1000}?'
        r'"dailyAvailabilities":\[(.*?)\]',
        re.DOTALL,
    )

    matches = room_pattern.findall(text)

    for room_name, availability_block in matches:

        daily_availability = {}

        availability_pattern = re.compile(
            r'"date":"(\d{4}-\d{2}-\d{2})"'
            r',"isAvailable":(true|false)'
        )

        availability_matches = availability_pattern.findall(
            availability_block
        )

        for day, available in availability_matches:

            daily_availability[day] = (
                available == "true"
            )

        if daily_availability:

            rooms.append(
                {
                    "room_name": room_name,
                    "daily_availability": daily_availability,
                }
            )

    return rooms


# =========================================================
# EXTRACT PRICE FOR A ONE-NIGHT STAY
# =========================================================

def extract_one_night_prices(response_text):
    """
    Extract the applicable room price from a one-night
    availability response.

    For a one-night request, roomPricesPerDay contains
    the nightly price.

    Multiple rate types can exist, so we collect the
    available roomPricesPerDay values and use the lowest
    applicable daily price.
    """

    text = normalize_response(response_text)

    prices = {}

    # Split response into room/unit sections.
    sections = re.split(
        r'(?="unitName":")',
        text
    )

    for section in sections:

        room_match = re.search(
            r'"unitName":"([^"]+)"',
            section
        )

        if not room_match:
            continue

        room_name = room_match.group(1)

        price_matches = re.findall(
            r'"roomPricesPerDay":\[\s*'
            r'([0-9]+(?:\.[0-9]+)?)'
            r'\s*\]',
            section
        )

        # The previous pattern only catches a single value.
        # Try the general array form as well.
        array_matches = re.findall(
            r'"roomPricesPerDay":\[(.*?)\]',
            section,
            re.DOTALL,
        )

        candidate_prices = []

        # Handle arrays such as:
        # [275]
        # [316.25]
        # [316.25,316.25]
        for array_text in array_matches:

            numbers = re.findall(
                r'[0-9]+(?:\.[0-9]+)?',
                array_text
            )

            for number in numbers:

                try:
                    candidate_prices.append(
                        float(number)
                    )
                except ValueError:
                    pass

        # Fallback to lowestRate if roomPricesPerDay
        # could not be extracted.
        if not candidate_prices:

            lowest_rate_match = re.search(
                r'"lowestRate":'
                r'([0-9]+(?:\.[0-9]+)?)',
                section
            )

            if lowest_rate_match:

                candidate_prices.append(
                    float(lowest_rate_match.group(1))
                )

        if candidate_prices:

            prices[room_name] = min(
                candidate_prices
            )

    return prices


# =========================================================
# GET PRICES FOR ONE DATE
# =========================================================

def get_prices_for_date(target_date, adults):
    """
    Request a one-night stay for a specific date.

    Example:

        check-in  = 2026-10-20
        check-out = 2026-10-21

    This gives us the nightly price for that date.
    """

    check_in = target_date

    check_out = (
        date.fromisoformat(target_date)
        + timedelta(days=1)
    ).isoformat()

    response_text = get_api_response(
        check_in,
        check_out,
        adults,
    )

    return extract_one_night_prices(
        response_text
    )


# =========================================================
# BUILD 90-DAY DATASET
# =========================================================

def scrape_90_days(
    start_date=None,
    adults=2,
    number_of_days=90,
):
    """
    Scrape room availability and nightly price
    for the next number_of_days.

    Parameters
    ----------
    start_date : str or None
        Starting date in YYYY-MM-DD format.

        If None, today's date is used.

    adults : int
        Number of adults.

    number_of_days : int
        Number of days to collect.

    Returns
    -------
    list

        Example:

        [
            {
                "date": "2026-10-20",
                "room_name": "5 - Turret Suite",
                "available": True,
                "price": 275.0
            }
        ]
    """

    # -----------------------------------------------------
    # Determine start date
    # -----------------------------------------------------

    if start_date is None:

        start = date.today()

    else:

        start = date.fromisoformat(
            start_date
        )


    # -----------------------------------------------------
    # Determine end date
    # -----------------------------------------------------

    end = start + timedelta(
        days=number_of_days
    )


    # -----------------------------------------------------
    # First API request
    #
    # Get the calendar availability data.
    # -----------------------------------------------------

    calendar_response = get_api_response(
        start.isoformat(),
        end.isoformat(),
        adults,
    )


    # -----------------------------------------------------
    # Extract daily availability
    # -----------------------------------------------------

    calendar_rooms = extract_calendar_rows(
        calendar_response
    )


    # -----------------------------------------------------
    # Convert availability into easy lookup
    # -----------------------------------------------------

    availability_lookup = {}

    for room in calendar_rooms:

        room_name = room["room_name"]

        for day, available in room[
            "daily_availability"
        ].items():

            availability_lookup[
                (day, room_name)
            ] = available


    # -----------------------------------------------------
    # Get room names
    # -----------------------------------------------------

    room_names = sorted(
        {
            room["room_name"]
            for room in calendar_rooms
        }
    )


    # -----------------------------------------------------
    # Collect daily prices
    #
    # One request per date.
    # -----------------------------------------------------

    price_lookup = {}

    current_date = start

    while current_date < end:

        current_date_string = (
            current_date.isoformat()
        )

        print(
            f"Getting prices for "
            f"{current_date_string}..."
        )

        try:

            daily_prices = get_prices_for_date(
                current_date_string,
                adults,
            )

            for room_name, price in daily_prices.items():

                price_lookup[
                    (
                        current_date_string,
                        room_name,
                    )
                ] = price

        except requests.RequestException as error:

            print(
                f"Price request failed for "
                f"{current_date_string}: {error}"
            )

        current_date += timedelta(days=1)


    # -----------------------------------------------------
    # Build final dataset
    # -----------------------------------------------------

    results = []

    current_date = start

    while current_date < end:

        day_string = current_date.isoformat()

        for room_name in room_names:

            available = availability_lookup.get(
                (
                    day_string,
                    room_name,
                ),
                False,
            )

            price = price_lookup.get(
                (
                    day_string,
                    room_name,
                )
            )

            results.append(
                {
                    "date": day_string,
                    "room_name": room_name,
                    "available": available,
                    "price": price,
                }
            )

        current_date += timedelta(days=1)


    return results


# =========================================================
# EXISTING STREAMLIT ROOM SEARCH
# =========================================================

def extract_rooms(response_text):
    """
    Extract room-level availability and lowest price
    for the currently selected stay.

    This function is kept for the existing Streamlit app.
    """

    rooms = []

    text = normalize_response(
        response_text
    )

    pattern = re.compile(
        r'"unitName":"([^"]+)"'
        r'.{0,15000}?'
        r'"status":"([^"]+)"'
        r',"lowestRate":'
        r'([0-9]+(?:\.[0-9]+)?)',
        re.DOTALL,
    )

    matches = pattern.findall(
        text
    )

    seen = set()

    for room_name, status, price in matches:

        if room_name in seen:
            continue

        seen.add(room_name)

        rooms.append(
            {
                "room_name": room_name,
                "available": status == "AVAILABLE",
                "status": status,
                "lowest_price": float(price),
            }
        )

    rooms.sort(
        key=lambda room: (
            not room["available"],
            room["lowest_price"]
            if room["lowest_price"] is not None
            else float("inf"),
        )
    )

    return rooms


# =========================================================
# STREAMLIT SEARCH FUNCTION
# =========================================================

def scrape_rooms(
    check_in,
    check_out,
    adults,
):
    """
    Main function used by the current Streamlit app.

    Values come from:

        check_in  -> calendar
        check_out -> calendar
        adults    -> adults selector
    """

    response_text = get_api_response(
        check_in,
        check_out,
        adults,
    )

    rooms = extract_rooms(
        response_text
    )

    return rooms


# =========================================================
# SAVE 90-DAY DATA AS JSON
# =========================================================

def save_90_days_json(
    data,
    filename="napa_inn_90_days.json",
):
    """
    Save the 90-day dataset as JSON.
    """

    with open(
        filename,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
        )


# =========================================================
# SAVE 90-DAY DATA AS CSV
# =========================================================

def save_90_days_csv(
    data,
    filename="napa_inn_90_days.csv",
):
    """
    Save the 90-day dataset as CSV.
    """

    import csv

    fieldnames = [
        "date",
        "room_name",
        "available",
        "price",
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            data
        )


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    print(
        "Starting 90-day API extraction..."
    )

    results = scrape_90_days(
        adults=2,
        number_of_days=90,
    )

    print(
        f"\nTotal records: {len(results)}"
    )

    print(
        "\nFirst 20 records:\n"
    )

    for row in results[:20]:

        print(
            row["date"],
            "|",
            row["room_name"],
            "|",
            (
                "AVAILABLE"
                if row["available"]
                else "NOT AVAILABLE"
            ),
            "|",
            row["price"],
        )

    # -----------------------------------------------------
    # Save files
    # -----------------------------------------------------

    save_90_days_json(
        results
    )

    save_90_days_csv(
        results
    )

    print(
        "\nSaved:"
    )

    print(
        "napa_inn_90_days.json"
    )

    print(
        "napa_inn_90_days.csv"
    )