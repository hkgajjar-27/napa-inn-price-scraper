import streamlit as st
from datetime import date, timedelta

from apiscraper import scrape_rooms


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Napa Inn Room Search",
    page_icon="🏨",
    layout="wide"
)


# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown(
    """
    <style>

    /* Main page */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Title */
    .main-title {
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .sub-title {
        font-size: 16px;
        color: #666;
        margin-bottom: 25px;
    }

    /* Search box */
    .search-box {
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e5e5e5;
        background-color: #fafafa;
        margin-bottom: 25px;
    }

    /* Result header */
    .result-header {
        font-size: 22px;
        font-weight: 600;
        margin-top: 25px;
        margin-bottom: 15px;
    }

    /* Room rows */
    .room-row {
        padding: 15px 10px;
        border-bottom: 1px solid #eeeeee;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# ROOM DETAIL PAGES
# =========================================================

ROOM_DETAIL_BASE = "https://www.napainn.com/guestrooms"

ROOM_DETAIL_PAGES = {
    "1 - Oak Room": "oak-room",
    "2 - Tower Room": "tower-room",
    "3 - Victorian Room": "victorian-room",
    "4 - Chesney Suite": "chesney-suite",
    "5 - Turret Suite": "turret-suite",
    "6 - Madeline's Suite": "madeline%E2%80%99s-suite",
    "7 - Angelina's Garden- ADA": (
        "angelina%E2%80%99s-garden-cottage-accessible"
    ),
    "8 - Garden Cottage": "garden-cottage",
    "9 - Lady Helen's Room": "lady-helens-room",
    "10 - Roman Suite": "roman-suite",
    "11 - Simeon's Quarters": "simeons-quarters",
    "12 - Miss Tessa's Room": "miss-tessas-room",
    "14 - William's Hideaway": "williams-hideaway",
    "15 - Gable Room": "gable-room",
    "16 - Kirtley's Retreat": "kirtleys-retreat",
}


def get_room_detail_url(room_name):
    """
    Return the Napa Inn individual room page.
    """

    slug = ROOM_DETAIL_PAGES.get(room_name)

    if slug is None:
        return ROOM_DETAIL_BASE

    return f"{ROOM_DETAIL_BASE}/{slug}"


# =========================================================
# PAGE HEADER
# =========================================================

st.markdown(
    '<div class="main-title">🏨 Napa Inn & Spa</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'Search available rooms and compare nightly prices.'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# SEARCH SECTION
# =========================================================

st.markdown("### Search Rooms")


# =========================================================
# DATE SELECTION
# =========================================================

today = date.today()

max_date = today + timedelta(days=90)

date_range = st.date_input(
    "Check-in → Check-out",
    value=(today, today + timedelta(days=1)),
    min_value=today,
    max_value=max_date,
    format="DD-MM-YYYY",
    key="stay_dates"
)


# =========================================================
# GET SELECTED DATES
# =========================================================

check_in = None
check_out = None

if isinstance(date_range, (tuple, list)):

    if len(date_range) >= 1:
        check_in = date_range[0]

    if len(date_range) >= 2:
        check_out = date_range[1]


# =========================================================
# GUESTS
# =========================================================

col1, col2, col3 = st.columns([1, 1, 4])

with col1:

    adults = st.number_input(
        "Adults",
        min_value=1,
        max_value=10,
        value=2,
        step=1,
        key="adults"
    )


# =========================================================
# SEARCH BUTTON
# =========================================================

search_button = st.button(
    "🔍 Search Available Rooms",
    use_container_width=True
)


# =========================================================
# SEARCH LOGIC
# =========================================================

if search_button:

    # -----------------------------------------------------
    # Validate dates
    # -----------------------------------------------------

    if check_in is None or check_out is None:

        st.warning(
            "Please select both check-in and check-out dates."
        )

        st.stop()


    if check_out <= check_in:

        st.warning(
            "Check-out date must be after the check-in date."
        )

        st.stop()


    # -----------------------------------------------------
    # Convert dates to string
    # -----------------------------------------------------

    check_in_str = check_in.strftime("%Y-%m-%d")
    check_out_str = check_out.strftime("%Y-%m-%d")


    # -----------------------------------------------------
    # Call API scraper
    # -----------------------------------------------------

    with st.spinner("Searching available rooms..."):

        try:

            rooms = scrape_rooms(
                check_in_str,
                check_out_str,
                adults
            )

        except Exception as e:

            st.error(
                f"Unable to retrieve room availability: {e}"
            )

            st.stop()


    # =====================================================
    # NO DATA
    # =====================================================

    if not rooms:

        st.warning(
            "There is no availability for the dates you selected. "
            "Please search for availability on different dates."
        )

        st.stop()


    # =====================================================
    # FILTER AVAILABLE ROOMS
    # =====================================================

    available_rooms = [
        room
        for room in rooms
        if room.get("available", False)
    ]


    available_count = len(available_rooms)


    # =====================================================
    # NO AVAILABLE ROOMS
    # =====================================================

    if available_count == 0:

        st.warning(
            "There is no availability for the dates you selected. "
            "Please search for availability on different dates."
        )

        st.stop()


    # =====================================================
    # SORT BY PRICE
    # =====================================================

    available_rooms.sort(
        key=lambda room: (
            room.get("lowest_price")
            if room.get("lowest_price") is not None
            else float("inf")
        )
    )


    # =====================================================
    # RESULT SUMMARY
    # =====================================================

    st.markdown(
        '<div class="result-header">Available Rooms</div>',
        unsafe_allow_html=True
    )

    st.success(
        f"{available_count} rooms available"
    )


    # =====================================================
    # TABLE HEADER
    # =====================================================

    header_col1, header_col2, header_col3, header_col4 = st.columns(
        [4, 2, 2, 1]
    )

    with header_col1:
        st.markdown("**Room Name**")

    with header_col2:
        st.markdown("**Availability**")

    with header_col3:
        st.markdown("**Price / Night**")

    with header_col4:
        st.markdown("**Room Details**")


    # =====================================================
    # ROOM RESULTS
    # =====================================================

    for room in available_rooms:

        room_name = room.get(
            "room_name",
            "Unknown Room"
        )

        lowest_price = room.get(
            "lowest_price"
        )


        # -------------------------------------------------
        # Format price
        # -------------------------------------------------

        if lowest_price is not None:

            try:

                price_text = (
                    f"${float(lowest_price):,.2f}"
                )

            except (ValueError, TypeError):

                price_text = str(lowest_price)

        else:

            price_text = "N/A"


        # -------------------------------------------------
        # Room detail URL
        # -------------------------------------------------

        room_url = get_room_detail_url(
            room_name
        )


        # -------------------------------------------------
        # Create row
        # -------------------------------------------------

        col1, col2, col3, col4 = st.columns(
            [4, 2, 2, 1]
        )


        with col1:

            st.write(room_name)


        with col2:

            st.write("Available")


        with col3:

            st.write(price_text)


        with col4:

            st.link_button(
                "View",
                room_url,
                use_container_width=True
            )