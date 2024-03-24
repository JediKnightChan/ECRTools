import io
import re
import time

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

import boto3
import json
import os
import traceback

from common.discord_api import DiscordWorker

MATCHES_CREATED_CHANNEL_ID = os.getenv('MATCHES_CREATED_CHANNEL_ID')
MATCHES_ONLINE_S3_DIR = "ecr-online/match-online"

# Connecting to S3 Object Storage
s3_session = boto3.session.Session()
s3 = s3_session.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ru-central1"
)


def upload_content_to_s3(content, s3_key):
    s3.put_object(Bucket='ecr-analytics', Key=s3_key, Body=content)


def get_file_from_s3(s3_key):
    obj_response = s3.get_object(Bucket='ecr-analytics', Key=s3_key)
    content = obj_response['Body'].read()
    return content


def json_response(dict_, status_code=200):
    print("Returning response", status_code, dict_)
    return {
        'statusCode': status_code,
        'headers': {"Content-Type": "application/json"},
        'body': json.dumps(dict_)
    }


def build_online_image_for_dt(dt):
    """Add raw online data to dict of today matches if player amount increased"""

    s3_file = f"{MATCHES_ONLINE_S3_DIR}/{dt.year}/{dt.year}-{dt.month}-{dt.day}.json"
    try:
        data = json.loads(get_file_from_s3(s3_file))
    except Exception as e:
        raise ValueError(f"S3 file not found: {s3_file}")

    start_times = [datetime.utcfromtimestamp(float(match["match_creation_ts"])) for match in data.values()]
    end_times = [datetime.utcfromtimestamp(float(match["latest_match_update_ts"])) for match in data.values()]
    player_amounts = [int(match["player_amount"]) for match in data.values()]
    labels = [
        f"{match['region']}_{match['map'].replace(' ', '_')}_{match['mission'].replace(' ', '_')}_{match['owner_display_name'].replace(' ', '_')}"
        for match in data.values()]

    today = start_times[0].date()
    today = datetime(today.year, today.month, today.day, 0, 0, 0)

    bin_width_mins = 1
    time_intervals = [today + timedelta(minutes=i) for i in range(0, 1440, bin_width_mins)]

    # Initialize lists to store data for plotting
    time_bins = []
    matches_player_counts_and_colors = []

    # Define a list of colors for each match (you can customize this list)
    cmap = plt.get_cmap('inferno', len(start_times))
    match_colors_list = [cmap(j) for j in range(len(start_times))]

    # Iterate over the time intervals
    for i in range(len(time_intervals) - 1):
        start_bin = time_intervals[i]
        end_bin = time_intervals[i + 1]

        this_bin_matches_player_counts_and_colors = [(players, match_color, label) for
                                                     start, end, players, match_color, label in
                                                     zip(start_times, end_times, player_amounts, match_colors_list,
                                                         labels) if not (start_bin > end or end_bin < start)]

        time_bins.append(start_bin)
        matches_player_counts_and_colors.append(this_bin_matches_player_counts_and_colors)

    # print([(f"{t.hour:02d}:{t.minute:02d}", [c[0] for c in z]) for t, z in zip(time_bins, matches_player_counts_and_colors)])

    colors_to_draw_labels = [i[1] for i in sorted(zip(player_amounts, match_colors_list), reverse=True)][:5]

    colors_drawn = []

    # Create the plot
    plt.style.use('seaborn-v0_8')
    plt.figure(figsize=(10, 6))
    for time, counts in zip(time_bins, matches_player_counts_and_colors):
        bottom = 0
        for i, (count, color, label) in enumerate(counts):
            final_label = None
            if color not in colors_drawn and color in colors_to_draw_labels:
                final_label = label
                colors_drawn.append(color)
            plt.bar(time, count, bottom=bottom, width=timedelta(minutes=bin_width_mins), color=color, label=final_label)
            bottom += count

    # Customize the plot
    plt.xlabel("Time (UTC)")
    plt.ylabel("Player Amount")
    plt.title(f"Peak Online by Matches on {dt.strftime('%d/%m/%y')} (Total Matches: {len(start_times)})")
    plt.grid(axis="y", linestyle="--", alpha=0.6)

    # Set the x-axis limits to display time from 0:00 to 24:00
    plt.xlim(today, today + timedelta(days=1))

    # Format the x-axis to display time in hours and minutes
    plt.gca().xaxis.set_major_locator(mdates.MinuteLocator(interval=60))
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    plt.yticks(range(0, max([sum([c[0] for c in k]) for k in matches_player_counts_and_colors]) + 10, 2))
    plt.legend()
    plt.xticks(rotation=45)  # Rotate x-axis labels for better readability

    # Save the plot as a BytesIO object
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    return buffer


def handler(event, context):
    dw = DiscordWorker()

    ts = float(event.API_GET("ts", 0))
    if ts == 0:
        ts = time.time() - 3600 * 24
    dt = datetime.utcfromtimestamp(ts)
    image_buffer = build_online_image_for_dt(dt)
    dw.send_message(MATCHES_CREATED_CHANNEL_ID, dw.build_message("", ""),
                    files={'file': ('plot.png', image_buffer, 'image/png')})


if __name__ == '__main__':
    handler({"ts": time.time()}, {})
