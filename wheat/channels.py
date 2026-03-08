"""
Intelligence Channels — How data flows into the fields.

Each channel is a reusable data pipeline that can feed multiple fields.
Fields subscribe to channels. Channels produce signals. The daily runner
routes signals to the right fields.

Channel Types:
  PUBLIC_RECORDS  — Government databases, FOIA/CORA responses
  REVIEWS         — Google, Yelp, BBB consumer reviews
  NEWS            — Local news RSS feeds, press releases
  COMMUNITY       — Direct reports from residents
  SOCIAL          — Nextdoor, local Facebook groups, Reddit
  REGULATORY      — State/federal enforcement actions, complaints
  COURT           — Court filings, judgments, liens
  API             — Structured data from government APIs

Each channel has:
  - name: Human-readable identifier
  - channel_type: One of the types above
  - sources: List of specific URLs, feeds, or databases
  - fields: Which fields this channel feeds into
  - frequency: How often to check (daily, weekly, realtime)
  - parser: How to extract signals from raw data
"""

import json
import os
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
CHANNELS_PATH = os.path.join(PROJECT_ROOT, "channels.json")
INTAKE_DIR = os.path.join(PROJECT_ROOT, "intake")


def load_channels():
    """Load channel definitions."""
    if not os.path.exists(CHANNELS_PATH):
        return get_default_channels()
    with open(CHANNELS_PATH, "r") as f:
        return json.load(f)


def save_channels(channels):
    with open(CHANNELS_PATH, "w") as f:
        json.dump(channels, f, indent=2)


def get_default_channels():
    """Default channel configuration for Englewood CO automotive accountability."""
    return {
        "google_reviews_auto": {
            "name": "Google Reviews — Auto Businesses",
            "channel_type": "REVIEWS",
            "sources": [
                "Google Maps API — auto dealers in Englewood CO",
                "Google Maps API — auto repair shops in Englewood CO",
                "Google Maps API — tow companies in Englewood CO",
                "Google Maps API — tint/exhaust shops in Englewood CO"
            ],
            "fields": ["used_car_dealers", "auto_repair", "tow_companies", "exhaust_noise", "window_tint"],
            "frequency": "daily",
            "description": "Scrape recent Google reviews for auto businesses, flag negative reviews mentioning fraud, overcharging, damage, illegal practices"
        },
        "yelp_bbb_complaints": {
            "name": "Yelp & BBB — Consumer Complaints",
            "channel_type": "REVIEWS",
            "sources": [
                "Yelp API — auto category in Englewood CO",
                "BBB complaint search — auto businesses in CO"
            ],
            "fields": ["used_car_dealers", "auto_repair", "tow_companies", "dealer_financing"],
            "frequency": "daily",
            "description": "Monitor Yelp and BBB for new complaints against auto businesses"
        },
        "cfpb_auto_lending": {
            "name": "CFPB — Auto Lending Complaints",
            "channel_type": "REGULATORY",
            "sources": [
                "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/ — product=Vehicle loan, state=CO"
            ],
            "fields": ["dealer_financing", "auto_insurance"],
            "frequency": "daily",
            "description": "Query CFPB complaint database for auto lending complaints in Colorado"
        },
        "fmcsa_safer": {
            "name": "FMCSA SAFER — Carrier Safety",
            "channel_type": "PUBLIC_RECORDS",
            "sources": [
                "https://safer.fmcsa.dot.gov — carriers in Englewood/Arapahoe County",
                "FMCSA SMS (Safety Measurement System) — inspection results"
            ],
            "fields": ["fleet_compliance", "commercial_trucking"],
            "frequency": "weekly",
            "description": "Check FMCSA for carrier safety records, violations, and inspection results for operators in the area"
        },
        "cdot_crash_data": {
            "name": "CDOT — Crash & Fatality Data",
            "channel_type": "PUBLIC_RECORDS",
            "sources": [
                "CDOT crash data portal — Englewood/Arapahoe County",
                "CDOT fatality reports"
            ],
            "fields": ["school_zone_safety", "pedestrian_cyclist", "road_intersection_safety", "fleet_compliance"],
            "frequency": "weekly",
            "description": "Pull crash data to identify dangerous locations, patterns, and entities involved"
        },
        "co_dmv_records": {
            "name": "Colorado DMV — Registration & Licensing",
            "channel_type": "PUBLIC_RECORDS",
            "sources": [
                "CO DMV dealer license registry",
                "CO DMV commercial vehicle registration"
            ],
            "fields": ["title_registration", "used_car_dealers", "fleet_compliance", "auto_insurance"],
            "frequency": "weekly",
            "description": "Check dealer licensing status, commercial vehicle registration, insurance verification"
        },
        "co_puc_towing": {
            "name": "CO PUC — Towing & TNC",
            "channel_type": "REGULATORY",
            "sources": [
                "Colorado PUC tow carrier registration database",
                "CO PUC TNC compliance records"
            ],
            "fields": ["tow_companies", "rideshare_delivery"],
            "frequency": "weekly",
            "description": "Check PUC registration status for tow companies and TNC compliance"
        },
        "local_news_rss": {
            "name": "Local News — Englewood/South Denver",
            "channel_type": "NEWS",
            "sources": [
                "Englewood Herald RSS",
                "Denver Post — Englewood section",
                "9News — traffic/safety",
                "CBS4 Denver — consumer reports",
                "Westword — consumer issues"
            ],
            "fields": ["all"],
            "frequency": "daily",
            "description": "Monitor local news for automotive safety stories, enforcement actions, consumer complaints, legislative changes"
        },
        "city_311": {
            "name": "Englewood 311 — Service Requests",
            "channel_type": "PUBLIC_RECORDS",
            "sources": [
                "City of Englewood 311 system",
                "Englewood city council agendas and minutes"
            ],
            "fields": ["road_intersection_safety", "pedestrian_cyclist", "exhaust_noise", "school_zone_safety"],
            "frequency": "weekly",
            "description": "Track 311 requests related to road safety, noise complaints, signage, and infrastructure"
        },
        "community_intake": {
            "name": "Community Reports — Direct Intake",
            "channel_type": "COMMUNITY",
            "sources": [
                "Web form submissions",
                "Email intake (reports@...)",
                "Photo/video submissions"
            ],
            "fields": ["all"],
            "frequency": "realtime",
            "description": "Direct reports from Englewood residents — the most valuable channel"
        },
        "nextdoor_social": {
            "name": "Nextdoor & Social Media",
            "channel_type": "SOCIAL",
            "sources": [
                "Nextdoor — Englewood neighborhoods",
                "Reddit r/Englewood, r/Denver",
                "Local Facebook community groups"
            ],
            "fields": ["all"],
            "frequency": "daily",
            "description": "Monitor social channels for safety complaints, patterns, and community sentiment"
        },
        "court_records": {
            "name": "Court Records — Arapahoe County",
            "channel_type": "COURT",
            "sources": [
                "Arapahoe County District Court — civil filings",
                "Arapahoe County Court — small claims",
                "CO judicial branch case search"
            ],
            "fields": ["used_car_dealers", "tow_companies", "dealer_financing", "auto_repair"],
            "frequency": "weekly",
            "description": "Monitor court filings for lawsuits involving auto businesses — reveals patterns of behavior"
        },
        "co_ag_consumer": {
            "name": "CO Attorney General — Consumer Protection",
            "channel_type": "REGULATORY",
            "sources": [
                "CO AG consumer complaint database",
                "CO AG enforcement actions",
                "CO Auto Dealer Board disciplinary actions"
            ],
            "fields": ["used_car_dealers", "auto_repair", "dealer_financing", "tow_companies"],
            "frequency": "weekly",
            "description": "Monitor AG complaints and enforcement actions against auto businesses"
        },
        "aircare_emissions": {
            "name": "AirCare Colorado — Emissions",
            "channel_type": "PUBLIC_RECORDS",
            "sources": [
                "AirCare Colorado emissions testing data",
                "CDPHE air quality complaints"
            ],
            "fields": ["emissions_environmental"],
            "frequency": "weekly",
            "description": "Emissions testing failures and air quality complaints"
        },
        "shop_social_media": {
            "name": "Auto Shop Social Media",
            "channel_type": "SOCIAL",
            "sources": [
                "Instagram/TikTok — local auto shops",
                "Facebook pages — exhaust/tint shops in Englewood area"
            ],
            "fields": ["exhaust_noise", "window_tint", "emissions_environmental"],
            "frequency": "daily",
            "description": "Shops that ADVERTISE illegal modifications are the prime targets — they profit from noncompliance. Monitor social media for shops advertising DPF deletes, illegal tint levels, muffler deletes."
        }
    }


def get_channels_for_field(field_id):
    """Get all channels that feed into a specific field."""
    channels = load_channels()
    return {
        cid: cdata for cid, cdata in channels.items()
        if field_id in cdata.get("fields", []) or "all" in cdata.get("fields", [])
    }


def get_fields_for_channel(channel_id):
    """Get all fields that a channel feeds into."""
    channels = load_channels()
    channel = channels.get(channel_id)
    if not channel:
        return []
    if "all" in channel.get("fields", []):
        from wheat.paths import load_projects
        return list(load_projects().keys())
    return channel.get("fields", [])


def process_intake(report_data):
    """Process a community intake report and route to appropriate field(s)."""
    os.makedirs(INTAKE_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(INTAKE_DIR, f"report_{timestamp}.json")

    report_data["received_at"] = datetime.now().isoformat()
    report_data["status"] = "pending"

    with open(report_file, "w") as f:
        json.dump(report_data, f, indent=2)

    # Route to field based on category
    category_to_field = {
        "dangerous_driving": "fleet_compliance",
        "commercial_vehicle": "fleet_compliance",
        "tow_company": "tow_companies",
        "used_car_dealer": "used_car_dealers",
        "auto_repair": "auto_repair",
        "noise_exhaust": "exhaust_noise",
        "school_zone": "school_zone_safety",
        "pedestrian_cyclist": "pedestrian_cyclist",
        "parking_booting": "parking_booting",
        "window_tint": "window_tint",
        "registration_plates": "title_registration",
        "emissions": "emissions_environmental",
        "intersection_road": "road_intersection_safety",
        "insurance": "auto_insurance",
        "dealer_financing": "dealer_financing",
        "rideshare_delivery": "rideshare_delivery",
    }

    category = report_data.get("category", "")
    target_field = category_to_field.get(category, "fleet_compliance")

    print(f"  Intake received: {report_data.get('description', 'No description')[:80]}")
    print(f"  Routed to field: {target_field}")

    return {"report_file": report_file, "target_field": target_field}


def channel_status_report():
    """Generate a status report of all channels."""
    channels = load_channels()
    report = []
    for cid, cdata in channels.items():
        report.append(
            f"  {cdata['name']}\n"
            f"    Type: {cdata['channel_type']} | Freq: {cdata['frequency']}\n"
            f"    Feeds: {', '.join(cdata['fields'])}\n"
            f"    Sources: {len(cdata['sources'])}"
        )
    return "\n".join(report)
