import boto3
import datetime
import gspread
import json
import os
from google.oauth2.service_account import Credentials

def lambda_handler(event, context):
    # Initialize AWS Cost Explorer client (must be us-east-1)
    ce = boto3.client('ce', region_name='us-east-1')

    today = datetime.date.today()

    # Calculate previous full month range
    # Example: if today is March → we fetch February
    start = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    end = today.replace(day=1)

    # Request monthly cost grouped by AWS account
    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': str(start),
            'End': str(end)
        },
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'}]
    )

    # Load Google credentials from environment variable
    creds_dict = json.loads(os.environ['GOOGLE_CREDS'])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    # Authorize Google Sheets client
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    # Open target spreadsheet
    sheet = client.open_by_key(os.environ['SPREADSHEET_ID']).sheet1

    # --- Load existing data from sheet ---
    existing = sheet.get_all_values()
    existing_set = set()

    # Build a set of existing (Month, Account) to avoid duplicates
    if len(existing) > 1:
        for row in existing[1:]:
            existing_set.add((row[0], row[1]))  # (Month, Account)

    # --- Prepare new rows ---
    new_rows = []

    for result in response['ResultsByTime']:
        month = result['TimePeriod']['Start']  # format: YYYY-MM-01

        for group in result['Groups']:
            account = group['Keys'][0]
            cost = group['Metrics']['UnblendedCost']['Amount']

            key = (month, account)

            # Add only if this (month, account) is not already in the sheet
            if key not in existing_set:
                new_rows.append([month, account, round(float(cost), 2)])

    # --- Append new rows to Google Sheet ---
    for row in new_rows:
        sheet.append_row(row)

    return "OK"
