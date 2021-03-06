import pandas as pd
import numpy as np
from datetime import datetime

from constants import (
    VIALINK_REQUIRED_COLUMNS_DISASTER,
    TWO32_HELP_REQUIRED_COLUMNS,
    TWO32_HELP_CALLS_KEY,
    VIALINK_DISASTER_KEY,
    HANGUP_VALUES,
)
from utils import (
    explode_needs,
    get_lat,
    get_lng,
    replacements,
)

pd.options.mode.chained_assignment = None


def cleanup(dfs):
    ### Cleanup for All COVID Calls dashboard

    # step 1
    # select required columns from VIA LINK’s Disaster Form
    # pretty sure the distaster form is "Uncleaned data type 1 VIA LINK"
    vialink1_df = dfs[VIALINK_DISASTER_KEY][VIALINK_REQUIRED_COLUMNS_DISASTER]

    # step 2
    # select required columns from 232-Help’s Disaster Form
    two32_help_df = dfs[TWO32_HELP_CALLS_KEY][TWO32_HELP_REQUIRED_COLUMNS]

    # step 3
    # Create age ranges from date of birth
    # use ranges 0-5, 6-12, 13-17, 18-24, 25-40, 41-59, 60+.
    now = datetime.now()
    bins = [0, 5, 13, 18, 25, 41, 60, 150]
    labels = ["0-5", "6-12", "13-17", "18-24", "25-40", "41-59", "60+"]
    dob = pd.to_datetime(
        two32_help_df["Client Information - Date of Birth"], errors="coerce"
    )
    years_old = (now - dob).astype("timedelta64[Y]")
    age_range = pd.cut(years_old, bins=bins, labels=labels, right=False, include_lowest=True)
    AGE_RANGE_LEY = "Client Information - Age Group"
    two32_help_df[AGE_RANGE_LEY] = age_range
    two32_help_df.loc[two32_help_df[AGE_RANGE_LEY] == "0-5", AGE_RANGE_LEY] = None
    # remove original Date of Birth column
    two32_help_df.drop(columns=["Client Information - Date of Birth"], inplace=True)

    # step 4
    # add "Data From" column
    vialink1_df["Data From"] = "VIA LINK"
    two32_help_df["Data From"] = "232-HELP"

    # step 5
    # add data to master spreadsheet
    # first merge "Call Outcome - What concerns/needs were identified" from 232-HELP
    # into "Concerns/Needs - Concerns/Needs"
    two32_help_df.rename(
        columns={
            "Call Outcome - What concerns/needs were identified?": "Concerns/Needs - Concerns/Needs"
        },
        inplace=True,
    )

    # new steps
    # cleanup invalid values
    vialink1_df["Contact Source - Program "].replace(
        to_replace=datetime(2001, 2, 1, 0, 0), value=np.nan, inplace=True
    )

    # then combine data
    master_df = pd.concat([vialink1_df, two32_help_df], join="outer", ignore_index=True)

    # step 6
    # add lat/lon columns
    master_df["Latitude"] = master_df["PostalCode"].apply(get_lat)
    master_df["Longitude"] = master_df["PostalCode"].apply(get_lng)

    # step 7
    # first put the values from "Needs - Basic Needs Requested" into "Concerns/Needs - Concerns/Needs"
    cn = "Concerns/Needs - Concerns/Needs"
    master_df["all_needs"] = master_df[[cn, "Needs - Basic Needs Requested"]].apply(
        lambda x: "; ".join(x[x.notnull()]), axis=1
    )
    master_df.drop(columns=[cn, "Needs - Basic Needs Requested"], inplace=True)
    master_df.rename(columns={"all_needs": cn}, inplace=True)
    master_df = explode_needs(master_df, cn)

    # step 8
    # cleanup Concerns/Needs
    master_df[cn] = master_df[cn].str.strip()
    master_df.replace(to_replace=replacements, value=None, inplace=True)

    # remove hangups
    master_df = master_df[~master_df[cn].isin(HANGUP_VALUES)]
    master_df = master_df[~master_df["Client Information - Call Type"].isin(HANGUP_VALUES)]
    master_df = master_df[~master_df["Client Information - Call Outcome"].isin(HANGUP_VALUES)]
    master_df = master_df[~master_df["Call Outcome - What was the outcome of this call?"].isin(HANGUP_VALUES)]

    return master_df
